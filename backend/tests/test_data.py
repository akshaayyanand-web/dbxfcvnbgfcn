"""Offline tests for the NASA PSI client (no network access needed)."""

from __future__ import annotations

import pytest

from backend.data import psi_client
from backend.data.psi_client import PSIError, PSIFile, list_files, summarise

RECORD = {
    "accession": "PSI-23",
    "doi": "10.60555/k57n-p030",
    "licenseIdentifier": "CC0-1.0",
    "added": [
        {"file_name": "19254H1_data.csv", "file_size": 2071918.0, "version": 1, "restricted": False,
         "remote_path": "/Home/psi-data/PSI-23/Raw Data/19254H1_data.csv"},
        {"file_name": "clip.mp4", "file_size": 100.0, "version": 1, "restricted": True,
         "remote_path": "/Home/psi-data/PSI-23/Raw Data/clip.mp4"},
    ],
    "experimentalTable": [
        {"file_name": "table.csv", "file_size": 2456, "version": 1, "restricted": False,
         "remote_path": "/Home/psi-data/PSI-23/Experimental table/table.csv"},
        # duplicate entry (same name and version) must be listed once
        {"file_name": "table.csv", "file_size": 2456, "version": 1, "restricted": False,
         "remote_path": "/Home/psi-data/PSI-23/Experimental table/table.csv"},
    ],
    "title": "unused",
}


def test_list_files_parses_categories_and_deduplicates():
    files = list_files(RECORD)
    assert [f.file_name for f in files] == ["table.csv", "19254H1_data.csv", "clip.mp4"]
    table = files[0]
    assert table.category == "Experimental table" and table.accession == "PSI-23" and table.extension == ".csv"


def test_summarise_counts_bytes_and_restrictions():
    s = summarise(RECORD)
    assert s["Raw Data .csv"] == {"files": 1, "bytes": 2071918, "restricted": 0}
    assert s["Raw Data .mp4"]["restricted"] == 1
    assert list(s)[0] == "Raw Data .csv"  # sorted by size


def test_download_refuses_restricted_and_oversized(tmp_path):
    restricted = PSIFile("PSI-23", "clip.mp4", 1, 100, "Raw Data", "", True)
    with pytest.raises(PSIError, match="restricted"):
        psi_client.download(restricted, tmp_path)
    huge = PSIFile("PSI-23", "big.zip", 1, 10**12, "Raw Data", "", False)
    with pytest.raises(PSIError, match="raise max_bytes"):
        psi_client.download(huge, tmp_path)


def test_download_rejects_non_https_signed_url(tmp_path, monkeypatch):
    monkeypatch.setattr(psi_client, "_get", lambda url, timeout=60: b'"file:///etc/passwd"')
    f = PSIFile("PSI-23", "a.csv", 1, 10, "Raw Data", "", False)
    with pytest.raises(PSIError, match="Unexpected download URL"):
        psi_client.download(f, tmp_path)


def test_invalid_accession():
    with pytest.raises(ValueError):
        psi_client.investigation("../etc")


def test_acme_catalogue_is_complete():
    assert set(psi_client.ACME_ACCESSIONS) == {"PSI-10", "PSI-20", "PSI-21", "PSI-22", "PSI-23", "PSI-159"}
