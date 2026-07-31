"""Country and jurisdiction lookup, generated from ISO 3166 (see frontend/data/reference.json)."""
import json
from functools import lru_cache
from pathlib import Path

_DATA = Path(__file__).resolve().parent / "frontend" / "data" / "reference.json"
_RISK_DATA = Path(__file__).resolve().parent / "frontend" / "data" / "country_risk.json"


@lru_cache(maxsize=1)
def _load() -> dict:
    try:
        return json.loads(_DATA.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"countries": [], "jurisdictions": []}


@lru_cache(maxsize=1)
def _load_risk() -> dict:
    try:
        return json.loads(_RISK_DATA.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"countries": {}, "fatf": {}, "uaeiec": {}}


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


def country_risk(code) -> dict:
    """Country-level AML risk data: a 0-100 score (higher = lower risk), a banded
    0-10 risk score, and FATF / UAE targeted-financial-sanctions flags.

    Sourced from a client-supplied AML risk-rating workbook, not invented here —
    see risk_data_meta() for the list this was built from and when it was last
    updated. Empty dict for a code the workbook doesn't cover.
    """
    if not code:
        return {}
    key = str(code).strip().lower().split("_")[0]
    return _load_risk().get("countries", {}).get(key, {})


def fatf_marking(code):
    """'black_list' for FATF Call for Action, 'grey_list' for Increased
    Monitoring, None otherwise. The one place this mapping lives, so the
    graph detector, the client risk-rating rows, and the "Screen this name"
    results all agree on what counts as which list.
    """
    tag = country_risk(code).get("fatf")
    if tag == "FATF HRC":
        return "black_list"
    if tag == "FATF JUIM":
        return "grey_list"
    return None


def risk_data_meta() -> dict:
    """Provenance for country_risk(): source description and FATF/UN list update dates."""
    data = _load_risk()
    return {
        "source": data.get("source", ""),
        "fatf_last_update": data.get("fatf_last_update"),
        "uaeiec_last_update": data.get("uaeiec_last_update"),
    }
