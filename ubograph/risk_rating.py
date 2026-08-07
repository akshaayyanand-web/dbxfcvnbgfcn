"""Individual client risk rating — a client-supplied AML workbook's weighted rubric.

Digitizes the exact scoring model a real MLRO runs in Excel today (nationality,
birth/residence/work-location country risk, sanctions/PEP screening outcome,
employment, payment mode and source of funds — each weighted, summed and
rescaled to a 0-100 Low/Medium/High outcome).

Standalone by design: every field, including nationality and the screening
outcome, is a plain manual selection — nothing here is looked up against a
searched entity automatically, so the worksheet works the same whether or not
anything has ever been searched for. screening_outcome_for() exists only to
back an explicit "Screen this name" button (see search.screen_name): a
deliberate, visible action, not something applied behind the scenes.
"""
import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

from reference import country_label, country_risk, fatf_marking, sanctioning_bodies

_DATA = Path(__file__).resolve().parent / "frontend" / "data" / "client_risk_rubric.json"


@lru_cache(maxsize=1)
def _rubric() -> dict:
    try:
        return json.loads(_DATA.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"weights": {}, "bands": {}, "source": ""}


def options() -> dict:
    """Dropdown option lists and weights, for the frontend to render the form."""
    r = _rubric()
    return {
        "screening_outcome": [row["label"] for row in r.get("screening_outcome", [])],
        "employment_industry": [row["label"] for row in r.get("employment_industry", [])],
        "employment_type": [row["label"] for row in r.get("employment_type", [])],
        "source_of_funds": [row["label"] for row in r.get("source_of_funds", [])],
        "mode_of_payment": [row["label"] for row in r.get("mode_of_payment", [])],
        "weights": r.get("weights", {}),
        "source": r.get("source", ""),
    }


_ADVERSE = {"sanctioned", "crime", "wanted", "sanction_linked", "debarred"}
_PEP = {"pep", "pep_associate"}


def screening_outcome_for(risk_flags) -> str:
    """Map sanctions/PEP flags found by a screening lookup onto the workbook's
    own screening-outcome labels, worst signal first. Used only by the "Screen
    this name" action — it fills the dropdown, it doesn't replace it."""
    flags = set(risk_flags or [])
    if flags & _ADVERSE:
        return "On relevant  lists"
    if flags & _PEP:
        return "PEP identified"
    if "leak" in flags:
        return "Negative News"
    return "Screened, PEP not identified, not on relevant lists"


def _lookup(table: str, label: Optional[str]) -> Optional[float]:
    if not label:
        return None
    for row in _rubric().get(table, []):
        if row["label"] == label:
            return row["score"]
    return None


def _country_row(criterion: str, code: Optional[str]) -> dict:
    info = country_risk(code) if code else {}
    label = info.get("name") or (country_label(code) if code else None)
    return {
        "criterion": criterion,
        "selected": label,
        "score": info.get("band_score"),
        "marking": fatf_marking(code) if code else None,
        # Independent of "marking" above — a country can be both FATF-listed
        # and sanctioned by one or more other bodies at once, and all of it
        # gets shown rather than collapsing to a single generic flag.
        "sanctioning_bodies": sanctioning_bodies(code) if code else [],
    }


_MITIGATION = {
    "low": [
        "Standard Customer Due Diligence is sufficient at this risk level.",
        "Review at the standard periodic interval for this risk band.",
    ],
    "medium": [
        "Apply Enhanced Due Diligence measures commensurate with the factors "
        "driving this score (see Reasoning above).",
        "Obtain and verify documented source of funds/wealth where not already held.",
        "Shorten the periodic review interval and document the sign-off rationale.",
    ],
    "high": [
        "Escalate to the MLRO / compliance officer before onboarding or continuing "
        "the relationship.",
        "Apply full Enhanced Due Diligence, including senior management approval.",
        "Consider whether the relationship should proceed at all, and document that "
        "decision.",
    ],
}


def _reasoning(rows: list, band: Optional[str]) -> str:
    """Plain-language explanation of what actually drove the score — which
    factors carried the most weight, not just the final number."""
    scored = [r for r in rows if r.get("weighted_score") is not None]
    if not scored or band is None:
        return "Not enough fields are complete yet to explain the score."
    top = sorted(scored, key=lambda r: r["weighted_score"], reverse=True)[:3]
    drivers = ", ".join(f"{r['criterion']} ({r['selected']})" for r in top if r["weighted_score"] > 0)
    band_label = {"low": "Low", "medium": "Medium", "high": "High"}.get(band, band)
    if not drivers:
        return f"Overall rating {band_label} — no single factor scored above zero."
    return f"Overall rating {band_label}, driven primarily by: {drivers}."


def rate(
    *,
    nationality: Optional[str] = None,
    country_of_birth: Optional[str] = None,
    country_of_residence: Optional[str] = None,
    business_work_location: Optional[str] = None,
    screening_outcome: Optional[str] = None,
    employment_type: Optional[str] = None,
    employment_industry: Optional[str] = None,
    mode_of_payment: Optional[str] = None,
    source_of_funds: Optional[str] = None,
    subject_name: Optional[str] = None,
    screening_reference: Optional[str] = None,
    compliance_notes: Optional[str] = None,
    prepared_by: Optional[str] = None,
    review_status: Optional[str] = None,
) -> dict:
    """Score one client the way the source workbook does: each factor's raw
    0-10 score times its fixed weight, summed, then multiplied by 10 to land
    on the workbook's 0-100 Low(0-25)/Medium(26-50)/High(51-100) scale.

    Country arguments take ISO codes; the rest take the workbook's own labels
    (see options() for the exact strings a dropdown should offer).

    subject_name/screening_reference/compliance_notes/prepared_by/
    review_status are optional record-keeping fields for the standalone
    downloadable PDF (subject details, a screening cross-reference, free-text
    compliance notes, who prepared it, and its review status) — none of them
    affect the score, and none are ever guessed or defaulted to a real name.
    """
    weights = _rubric().get("weights", {})
    rows = [
        _country_row("Customer's Nationality", nationality),
        _country_row("Country of Birth", country_of_birth),
        _country_row("Country of Residence", country_of_residence),
        _country_row("Business / Work Location", business_work_location),
        {"criterion": "Screening", "selected": screening_outcome,
         "score": _lookup("screening_outcome", screening_outcome)},
        {"criterion": "Employment Type", "selected": employment_type,
         "score": _lookup("employment_type", employment_type)},
        {"criterion": "Employment Industry", "selected": employment_industry,
         "score": _lookup("employment_industry", employment_industry)},
        {"criterion": "Mode of Payment", "selected": mode_of_payment,
         "score": _lookup("mode_of_payment", mode_of_payment)},
        {"criterion": "Source of Funds / Wealth", "selected": source_of_funds,
         "score": _lookup("source_of_funds", source_of_funds)},
    ]
    weight_keys = ("nationality", "country_of_birth", "country_of_residence",
                   "business_work_location", "screening", "employment_type",
                   "employment_industry", "mode_of_payment", "source_of_funds")
    for row, key in zip(rows, weight_keys):
        row["weight"] = weights.get(key)
        row["weighted_score"] = (
            round(row["score"] * row["weight"], 4)
            if row["score"] is not None and row["weight"] is not None else None
        )

    known = [r for r in rows if r["weighted_score"] is not None]
    missing = [r["criterion"] for r in rows if r["weighted_score"] is None]
    total = round(sum(r["weighted_score"] for r in known) * 10, 1) if known else None

    band = None
    if total is not None:
        band = "low" if total <= 25 else "medium" if total <= 50 else "high"

    return {
        "rows": rows,
        "score": total,
        "band": band,
        "complete": not missing,
        "missing": missing,
        "source": _rubric().get("source", ""),
        "risk_matrix": [
            {"band": "low", "label": "Low", "range": "0 – 25"},
            {"band": "medium", "label": "Medium", "range": "26 – 50"},
            {"band": "high", "label": "High", "range": "51 – 100"},
        ],
        "reasoning": _reasoning(rows, band),
        "mitigation": _MITIGATION.get(band, []),
        "subject_name": subject_name,
        "screening_reference": screening_reference,
        "compliance_notes": (compliance_notes or "").strip() or None,
        "prepared_by": (prepared_by or "").strip() or None,
        "review_status": review_status or "Draft — pending review",
    }
