"""Reference library of "reason for reporting" red-flag codes, for the goAML
export — a standard STR/SAR typology (funnel accounts, structuring, shell
companies, TFS-related indicators and the like), not anything specific to one
firm's cases. Lets a reporting officer pick a recognised code instead of
writing the reason from scratch every time, and carries the code's own label
into the goAML draft so the FIU-facing wording matches the taxonomy they
already use.
"""
import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

_DATA = Path(__file__).resolve().parent / "frontend" / "data" / "reporting_reasons.json"


@lru_cache(maxsize=1)
def _load() -> dict:
    try:
        return json.loads(_DATA.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"source": "", "reasons": []}


def list_reasons(query: Optional[str] = None) -> list:
    """All reason codes, or those whose code/description match `query`
    (case-insensitive substring)."""
    reasons = _load().get("reasons", [])
    if not query:
        return reasons
    needle = query.strip().lower()
    return [
        r for r in reasons
        if needle in r["code"].lower() or needle in r["description"].lower()
    ]


def get_reason(code: Optional[str]) -> Optional[dict]:
    if not code:
        return None
    code = code.strip().upper()
    for r in _load().get("reasons", []):
        if r["code"] == code:
            return r
    return None


def source() -> str:
    return _load().get("source", "")
