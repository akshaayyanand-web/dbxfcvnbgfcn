"""Country and jurisdiction lookup, generated from ISO 3166 (see frontend/data/reference.json)."""
import json
from functools import lru_cache
from pathlib import Path

_DATA = Path(__file__).resolve().parent / "frontend" / "data" / "reference.json"


@lru_cache(maxsize=1)
def _load() -> dict:
    try:
        return json.loads(_DATA.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"countries": [], "jurisdictions": []}


@lru_cache(maxsize=1)
def _country_names() -> dict:
    return {c["code"]: c["name"] for c in _load().get("countries", [])}


@lru_cache(maxsize=1)
def _jurisdiction_names() -> dict:
    return {j["code"]: j["name"] for j in _load().get("jurisdictions", [])}


def country_label(code) -> str:
    """'ae' -> 'United Arab Emirates'. Unknown codes come back as given."""
    if not code:
        return ""
    key = str(code).strip().lower()
    return _country_names().get(key) or _country_names().get(key.split("_")[0]) or str(code)


def jurisdiction_label(code) -> str:
    """'ae_du' -> 'United Arab Emirates — Dubai'."""
    if not code:
        return ""
    key = str(code).strip().lower()
    return _jurisdiction_names().get(key) or country_label(key)


def countries() -> list:
    return _load().get("countries", [])


def jurisdictions() -> list:
    return _load().get("jurisdictions", [])
