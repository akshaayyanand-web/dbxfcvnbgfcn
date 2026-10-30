"""Client for NASA's Physical Sciences Informatics (PSI) repository with provenance records.

PSI (https://psi.nasa.gov) hosts the ACME investigations (PSI-10, -20, -21, -22,
-23, -159) under CC0-1.0. The web application talks to a JSON web service
("GEODE"); this module uses the same public endpoints:

* ``GET /geode-py/ws/repo/search?term=...&data_source=psi``    -> investigation search
* ``GET /geode-py/ws/repo/investigations/<accession>``           -> metadata + file list
* ``GET /geode-py/ws/studies/<accession>/download?file=...&version=...&redirect=false``
                                                                 -> pre-signed S3 URL

Every download writes a provenance record next to the file
(``<file>.provenance.json``) with source URLs, investigation DOI, licence,
retrieval time, size and SHA-256, so that no file can later be mistaken for
anything other than what it is.

The endpoints are undocumented internals of the PSI web app and may change;
failures raise ``PSIError`` with the HTTP status rather than returning partial data.
"""

from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

BASE_URL = "https://psi.nasa.gov"
ACME_ACCESSIONS = {
    "PSI-10": "ACME Flame Design",
    "PSI-20": "ACME Burning Rate Emulator (BRE)",
    "PSI-21": "ACME Coflow Laminar Diffusion Flame (CLD Flame)",
    "PSI-22": "ACME Electric-Field Effects on Laminar Diffusion Flames (E-FIELD Flames)",
    "PSI-23": "ACME Structure and Response of Spherical Diffusion Flames (s-Flame)",
    "PSI-159": "ACME Cool Flames Investigation with Gases (CFI-G)",
}
_TIMEOUT_S = 60
_CHUNK = 1 << 20


class PSIError(RuntimeError):
    """A PSI request failed or returned unexpected content."""


@dataclass(frozen=True)
class PSIFile:
    accession: str
    file_name: str
    version: int
    size_bytes: int
    category: str          # e.g. "Raw Data", "Experimental table", "Reference Data"
    remote_path: str
    restricted: bool

    @property
    def extension(self) -> str:
        return Path(self.file_name).suffix.lower()


def _get(url: str, timeout: float = _TIMEOUT_S) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "flame-in-freefall/0.1 (research)"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        raise PSIError(f"HTTP {exc.code} for {url}") from exc
    except urllib.error.URLError as exc:
        raise PSIError(f"Cannot reach {url}: {exc.reason}") from exc


def search(term: str, size: int = 50) -> list[dict]:
    """Investigation search; returns the ``_source`` records."""
    q = urllib.parse.urlencode({"term": term, "data_source": "psi", "size": size})
    data = json.loads(_get(f"{BASE_URL}/geode-py/ws/repo/search?{q}"))
    return [h["_source"] for h in data.get("hits", {}).get("hits", [])]


def investigation(accession: str) -> dict:
    """Full investigation record (metadata and file lists)."""
    if not accession.startswith("PSI-") or not accession[4:].isdigit():
        raise ValueError(f"Invalid PSI accession: {accession!r}")
    return json.loads(_get(f"{BASE_URL}/geode-py/ws/repo/investigations/{accession}", timeout=180))


def list_files(record: dict) -> list[PSIFile]:
    """All file entries of an investigation record, de-duplicated by (name, version)."""
    seen: dict[tuple[str, int], PSIFile] = {}
    for value in record.values():
        if not (isinstance(value, list) and value and isinstance(value[0], dict) and "file_name" in value[0]):
            continue
        for f in value:
            parts = f.get("remote_path", "").split("/")
            key = (f["file_name"], int(f.get("version") or 1))
            seen[key] = PSIFile(
                accession=record.get("accession", ""),
                file_name=f["file_name"],
                version=key[1],
                size_bytes=int(f.get("file_size") or 0),
                category=parts[4] if len(parts) > 5 else "",
                remote_path=f.get("remote_path", ""),
                restricted=bool(f.get("restricted")),
            )
    return sorted(seen.values(), key=lambda x: (x.category, x.file_name))


def download(f: PSIFile, dest_dir: str | Path, record: dict | None = None, max_bytes: int = 2 * 1024**3) -> Path:
    """Download one file with a provenance sidecar. Refuses restricted or oversized files."""
    if f.restricted:
        raise PSIError(f"{f.file_name} is marked restricted; not downloading.")
    if f.size_bytes > max_bytes:
        raise PSIError(f"{f.file_name} is {f.size_bytes} bytes (> {max_bytes}); raise max_bytes explicitly.")
    dest_dir = Path(dest_dir) / f.accession
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(f.file_name).name  # PSI names never contain directories; enforce it
    target = dest_dir / safe_name
    q = urllib.parse.urlencode({"file": f.file_name, "version": f.version, "redirect": "false"})
    api_url = f"{BASE_URL}/geode-py/ws/studies/{f.accession}/download?{q}"
    signed = _get(api_url).decode().strip().strip('"')
    if not signed.startswith("https://"):
        raise PSIError(f"Unexpected download URL for {f.file_name}: {signed[:80]!r}")

    sha = hashlib.sha256()
    size = 0
    tmp = target.with_suffix(target.suffix + ".part")
    req = urllib.request.Request(signed, headers={"User-Agent": "flame-in-freefall/0.1 (research)"})
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp, open(tmp, "wb") as out:
            while chunk := resp.read(_CHUNK):
                out.write(chunk)
                sha.update(chunk)
                size += len(chunk)
    except (urllib.error.URLError, OSError) as exc:
        tmp.unlink(missing_ok=True)
        raise PSIError(f"Download of {f.file_name} failed: {exc}") from exc
    if f.size_bytes and size != f.size_bytes:
        tmp.unlink(missing_ok=True)
        raise PSIError(f"Size mismatch for {f.file_name}: got {size}, catalogue says {f.size_bytes}.")
    tmp.replace(target)

    record = record or {}
    provenance = {
        "data_class": "direct_measurement_archive",
        "source": "NASA Physical Sciences Informatics (PSI)",
        "investigation": f.accession,
        "investigation_title": ACME_ACCESSIONS.get(f.accession, record.get("title")),
        "doi": record.get("doi"),
        "license": record.get("licenseIdentifier"),
        "file": asdict(f),
        "api_url": api_url,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "size_bytes": size,
        "sha256": sha.hexdigest(),
    }
    target.with_name(target.name + ".provenance.json").write_text(json.dumps(provenance, indent=2))
    return target


def summarise(record: dict) -> dict:
    """Counts and total size per (category, extension) for an investigation record."""
    out: dict[str, dict] = {}
    for f in list_files(record):
        key = f"{f.category or '-'} {f.extension or '-'}"
        entry = out.setdefault(key, {"files": 0, "bytes": 0, "restricted": 0})
        entry["files"] += 1
        entry["bytes"] += f.size_bytes
        entry["restricted"] += int(f.restricted)
    return dict(sorted(out.items(), key=lambda kv: -kv[1]["bytes"]))


if __name__ == "__main__":  # pragma: no cover - manual use
    import argparse

    parser = argparse.ArgumentParser(description="Inspect or download NASA PSI ACME files.")
    parser.add_argument("accession", choices=sorted(ACME_ACCESSIONS))
    parser.add_argument("--match", help="Download files whose name contains this text.")
    parser.add_argument("--category", help="Restrict --match to one category, e.g. 'Experimental table'.")
    parser.add_argument("--max-bytes", type=int, default=200 * 1024**2)
    parser.add_argument("--dest", default="data/raw")
    ns = parser.parse_args()
    rec = investigation(ns.accession)
    if not ns.match:
        print(json.dumps({"accession": ns.accession, "doi": rec.get("doi"), "license": rec.get("licenseIdentifier"),
                          "files": summarise(rec)}, indent=2))
    else:
        for item in list_files(rec):
            if ns.match not in item.file_name or (ns.category and item.category != ns.category):
                continue
            # PSI lists many raw files twice: as "<name>" and as "<accession>_<category>_<name>"
            # with identical sizes. Only the unprefixed copy is fetched to avoid duplicates.
            if item.category == "Raw Data" and item.file_name.startswith(f"{ns.accession}_"):
                continue
            if item.size_bytes > ns.max_bytes:
                print("skipped (too large)", item.file_name, item.size_bytes)
                continue
            print("downloaded", download(item, ns.dest, rec, ns.max_bytes))
