"""Registry of server-side analysis samples (NASA PSI image sequences and a SYNTHETIC demo).

Samples are described in ``data/presets/samples.json`` with their provenance, the
measured calibration and a recommended analysis configuration. A NASA sample is
*available* only if its directory has been downloaded. The SYNTHETIC demo video is
generated on first use and is always labelled as simulated.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

from backend.vision.synthetic import SyntheticFlameSpec, write_synthetic_video

_LOCK = threading.Lock()


class SampleRegistry:
    def __init__(self, data_dir: Path, storage_dir: Path):
        self.data_dir = data_dir
        self.storage_dir = storage_dir
        path = data_dir / "presets" / "samples.json"
        self._samples = {s["id"]: s for s in json.loads(path.read_text())["samples"]} if path.exists() else {}

    def _source_path(self, s: dict) -> Path:
        if s.get("generated"):
            return self.storage_dir / "samples" / "SYNTHETIC_demo.mp4"
        return (self.data_dir / s["directory"]).resolve()

    def available(self, s: dict) -> bool:
        return bool(s.get("generated")) or self._source_path(s).is_dir()

    def list(self) -> list[dict]:
        out = []
        for s in self._samples.values():
            public = {k: v for k, v in s.items() if k not in ("directory",)}
            public["available"] = self.available(s)
            out.append(public)
        return out

    def get(self, sample_id: str) -> dict | None:
        return self._samples.get(sample_id)

    def resolve(self, sample_id: str) -> Path:
        """Filesystem path for analysis (internal only; never returned to clients)."""
        s = self._samples.get(sample_id)
        if s is None:
            raise KeyError(sample_id)
        path = self._source_path(s)
        if s.get("generated"):
            with _LOCK:
                if not path.exists():
                    write_synthetic_video(path, SyntheticFlameSpec())
            return path
        root = (self.data_dir / "raw").resolve()
        if root not in path.parents:
            raise KeyError(sample_id)  # registry entries must stay inside data/raw
        if not path.is_dir():
            raise FileNotFoundError(f"Sample {sample_id} is not downloaded. {s.get('download_hint', '')}")
        return path
