"""Individual client risk rating — the ELIVA workbook's own weighted rubric.

Digitizes the exact scoring model a real MLRO runs in Excel today (nationality,
birth/residence/work-location country risk, sanctions/PEP screening outcome,
employment, payment mode and source of funds — each weighted, summed and
rescaled to a 0-100 Low/Medium/High outcome) so a UBOgraph report can produce
the same number.

Employment, payment mode and source of funds are KYC facts no public source
carries — OpenSanctions and OpenCorporates have no idea how a client is paid
or where their salary comes from. Those stay manual inputs. Nationality and
the sanctions/PEP screening outcome are NOT manual: nationality is a graph
fact and screening comes straight from the entity's own risk_flags, because
letting a user override either would defeat the point of screening at all.
"""
import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

from reference import country_label, country_risk

_DATA = Path(__file__).resolve().parent / "frontend" / "data" / "client_risk_rubric.json"

# The workbook's own screening-outcome labels (kept verbatim, including its
# double space in "relevant  lists", so _lookup() matches the source data).
_ADVERSE = {"sanctioned", "crime", "wanted", "sanction_linked", "debarred"}
_PEP = {"pep", "pep_associate"}


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
        "employment_industry": [row["label"] for row in r.get("employment_industry", [])],
        "employment_type": [row["label"] for row in r.get("employment_type", [])],
        "source_of_funds": [row["label"] for row in r.get("source_of_funds", [])],
        "mode_of_payment": [row["label"] for row in r.get("mode_of_payment", [])],
        "weights": r.get("weights", {}),
        "source": r.get("source", ""),
    }


def screening_outcome_for(risk_flags) -> str:
    """Map a node's OpenSanctions-derived flags onto the workbook's own screening
    categories, worst signal first. Not user-editable — this is what screening
    actually found, not a guess to override."""
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
    return {"criterion": criterion, "selected": label, "score": info.get("band_score")}


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
) -> dict:
    """Score one client the way the ELIVA workbook does: each factor's raw 0-10
    score times its fixed weight, summed, then multiplied by 10 to land on the
    workbook's 0-100 Low(0-25)/Medium(26-50)/High(51-100) scale.

    Country arguments take ISO codes; the rest take the workbook's own labels
    (see options() for the exact strings a dropdown should offer).
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
    }
