"""Enhanced Due Diligence checklist — the trigger list a real AML policy runs
(PEP? sanctioned? high-risk jurisdiction? complex structure?), answered from
whatever the graph actually shows, with "not available" stated plainly rather
than guessed wherever the data needed isn't something a public source carries.
"""
from typing import Optional

STRUCTURAL_KINDS = {"circular_ownership", "nominee_hub", "deep_layering", "shared_address"}
JURISDICTION_KINDS = {"high_risk_jurisdiction", "fatf_jurisdiction"}


def _finding_titles(findings: list, kinds: set, node_id: Optional[str] = None) -> list:
    out = []
    for f in findings:
        if f.get("kind") not in kinds:
            continue
        if node_id and node_id not in (f.get("nodes") or []):
            continue
        out.append(f["title"])
    return out


def build_checklist(report: dict) -> list:
    """Returns an ordered list of {question, answer, basis} rows."""
    subject = report["subject"]
    findings = report.get("findings", [])
    node_id = subject.get("id")
    flags = set(subject.get("flags") or [])

    rows = []

    if flags & {"sanctioned", "crime", "wanted"}:
        rows.append({
            "question": "Is the subject sanctioned, criminally listed, or wanted?",
            "answer": "Yes",
            "basis": f"Recorded flags: {', '.join(sorted(flags & {'sanctioned', 'crime', 'wanted'}))}.",
        })
    else:
        rows.append({
            "question": "Is the subject sanctioned, criminally listed, or wanted?",
            "answer": "No",
            "basis": "No such flag recorded in the sources searched.",
        })

    if flags & {"pep", "pep_associate"}:
        rows.append({
            "question": "Is the subject a PEP or a close associate of one?",
            "answer": "Yes",
            "basis": "Recorded as politically exposed or a close associate in the sources searched.",
        })
    else:
        rows.append({
            "question": "Is the subject a PEP or a close associate of one?",
            "answer": "No",
            "basis": "No such flag recorded in the sources searched.",
        })

    juris_hits = _finding_titles(findings, JURISDICTION_KINDS, node_id) or \
        [f["title"] for f in findings if f.get("kind") in JURISDICTION_KINDS]
    rows.append({
        "question": "Is the subject registered or located in a high-risk or "
                     "FATF-flagged jurisdiction?",
        "answer": "Yes" if juris_hits else "No",
        "basis": "; ".join(juris_hits) if juris_hits
                 else f"Jurisdiction on record: {subject.get('jurisdiction_label') or subject.get('country_label') or 'none recorded'}.",
    })

    structural_hits = _finding_titles(findings, STRUCTURAL_KINDS, node_id) or \
        [f["title"] for f in findings if f.get("kind") in STRUCTURAL_KINDS]
    rows.append({
        "question": "Does the ownership or control structure show signs of "
                     "complexity or concealment (circular ownership, nominee "
                     "patterns, brass-plate addresses)?",
        "answer": "Yes" if structural_hits else "No",
        "basis": "; ".join(structural_hits) if structural_hits
                 else "No structural finding recorded for this entity.",
    })

    rows.append({
        "question": "Is the subject's business a designated high-risk type "
                     "(real estate, precious metals/stones, art & antiques, "
                     "money service business, VASP)?",
        "answer": "Not available from current sources",
        "basis": "OpenSanctions and OpenCorporates do not classify entities by "
                 "business activity in a way this tool can read — confirm from "
                 "the client's own registration or KYC file.",
    })
    rows.append({
        "question": "Is the subject a non-resident, or otherwise outside the "
                     "jurisdiction where the business relationship is being formed?",
        "answer": "Not available from current sources",
        "basis": "Residency is a KYC fact, not something a public registry or "
                 "sanctions list carries — confirm from the client's own file.",
    })
    rows.append({
        "question": "Has any transaction or activity involving the subject "
                     "been flagged as suspicious?",
        "answer": "Not available from current sources",
        "basis": "This tool has no transaction data — confirm against the "
                 "firm's own monitoring and STR/SAR records.",
    })

    return rows
