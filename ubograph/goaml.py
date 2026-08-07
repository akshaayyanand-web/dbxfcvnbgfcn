"""A starting-point goAML XML draft, built from a report already on screen.

Important limit, stated up front rather than discovered later: this is NOT
validated against the UAE FIU's actual goAML XSD schema — that schema isn't
published anywhere this tool can read it from, so this fills in the fields a
person/entity report clearly has (name, DOB, nationality, ID numbers, address,
the reason a report is being considered) into a plausible, human-readable XML
shape, and leaves the rest as clearly-marked blanks. Treat the output as a
draft to open inside goAML and complete, not a validated submission — it will
very likely need re-keying into goAML's own web form or import format either
way.
"""
import xml.etree.ElementTree as ET
from typing import Optional

import reasons as reasons_ref
from tz import now_dubai

REPORT_TYPES = {
    "STR": "Suspicious Transaction Report",
    "SAR": "Suspicious Activity Report",
}


def _sub(parent, tag, text=None):
    el = ET.SubElement(parent, tag)
    if text not in (None, ""):
        el.text = str(text)
    return el


def build_xml(report: dict, reason: str = "", reason_code: Optional[str] = None,
              report_type: str = "STR") -> bytes:
    subject = report["subject"]
    is_person = subject.get("type") == "person"
    report_type = report_type if report_type in REPORT_TYPES else "STR"

    root = ET.Element("report")
    root.set("draft", "true")
    root.set("note", "Starting point only — not validated against the goAML XSD. Complete in goAML.")

    header = _sub(root, "report_header")
    _sub(header, "generated_by", "Sanctions+")
    _sub(header, "generated_at", now_dubai().strftime("%Y-%m-%dT%H:%M:%S+04:00"))
    _sub(header, "report_type", report_type)
    _sub(header, "report_type_label", REPORT_TYPES[report_type])

    matched_reason = reasons_ref.get_reason(reason_code)
    if matched_reason:
        _sub(header, "reason_code", matched_reason["code"])
        _sub(header, "reason_code_label", matched_reason["description"])
    _sub(header, "reason_for_report", reason or "FILL IN: why this report is being considered")

    entity = _sub(root, "reporting_entity")
    _sub(entity, "name", "FILL IN: your firm's registered name")
    _sub(entity, "license_number", "FILL IN")

    subj_el = _sub(root, "subject")
    subj_el.set("kind", "person" if is_person else "legal_entity")
    if is_person:
        person = _sub(subj_el, "person")
        _sub(person, "full_name", subject.get("name"))
        _sub(person, "date_of_birth", subject.get("birth_date"))
        _sub(person, "nationality", subject.get("country_label"))
    else:
        legal = _sub(subj_el, "legal_entity")
        _sub(legal, "name", subject.get("name"))
        _sub(legal, "incorporation_jurisdiction", subject.get("jurisdiction_label"))
        _sub(legal, "registration_number", subject.get("reg_number"))

    identifiers = _sub(subj_el, "identifiers")
    dossier = report.get("dossier") or {}
    id_rows = []
    for group in dossier.get("groups", []):
        if group.get("title") == "Identifiers":
            id_rows = group.get("rows", [])
    if id_rows:
        for row in id_rows:
            for value in row["values"]:
                id_el = _sub(identifiers, "identifier")
                _sub(id_el, "type", row["label"])
                _sub(id_el, "value", value)
    else:
        _sub(identifiers, "identifier_note", "No passport/national ID/registration number on record.")

    address_el = _sub(subj_el, "address", None)
    for group in dossier.get("groups", []):
        if group.get("title") == "Contact & address":
            for row in group.get("rows", []):
                if row["label"] == "Address":
                    for value in row["values"]:
                        _sub(address_el, "full_address", value)

    flags_el = _sub(root, "flags")
    for flag in subject.get("flags") or []:
        _sub(flags_el, "flag", flag)

    findings_el = _sub(root, "findings")
    for finding in report.get("findings", []):
        f_el = _sub(findings_el, "finding")
        f_el.set("severity", finding.get("severity", ""))
        _sub(f_el, "title", finding.get("title"))
        _sub(f_el, "detail", finding.get("detail"))

    _sub(root, "narrative", " ".join(report.get("narrative", [])))

    xml_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return xml_bytes


MATCH_REPORT_TYPES = {
    "CNMR": "Confirmed Name Match Report",
    "PNMR": "Partial Name Match Report",
}


def build_match_xml(screened_name: str, match: dict, report_type: str = "PNMR") -> bytes:
    """A goAML draft for a single sanctions/PEP screening hit — the Confirmed
    or Partial Name Match Report a DNFBP files against the Targeted Financial
    Sanctions (TFS) regime once a name match is identified, separate from a
    full STR/SAR. UAE TFS guidance calls for this within five days of
    identifying the match, alongside any funds-freeze taken in the meantime —
    this only drafts the report, it doesn't track or enforce that deadline.
    """
    report_type = report_type if report_type in MATCH_REPORT_TYPES else "PNMR"

    root = ET.Element("report")
    root.set("draft", "true")
    root.set("note", "Starting point only — not validated against the goAML XSD. Complete in goAML.")

    header = _sub(root, "report_header")
    _sub(header, "generated_by", "Sanctions+")
    _sub(header, "generated_at", now_dubai().strftime("%Y-%m-%dT%H:%M:%S+04:00"))
    _sub(header, "report_type", report_type)
    _sub(header, "report_type_label", MATCH_REPORT_TYPES[report_type])
    _sub(header, "filing_note",
         "UAE TFS guidance: report a confirmed or partial name match through goAML "
         "within 5 days of identifying it, alongside any funds-freeze action taken.")

    screened = _sub(root, "screened_name")
    _sub(screened, "name_searched", screened_name)

    matched = _sub(root, "matched_record")
    _sub(matched, "name", match.get("name"))
    if match.get("score") is not None:
        _sub(matched, "match_score_pct", round(match["score"] * 100, 1))
    _sub(matched, "country", match.get("country"))
    if match.get("fatf_marking"):
        _sub(matched, "fatf_marking", match["fatf_marking"])
    if match.get("sanctioning_bodies"):
        _sub(matched, "sanctioning_bodies", ", ".join(match["sanctioning_bodies"]))

    flags_el = _sub(root, "flags")
    for flag in match.get("flags") or []:
        _sub(flags_el, "flag", flag)

    _sub(root, "action_taken", "FILL IN: funds frozen / relationship declined / under review")

    xml_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return xml_bytes
