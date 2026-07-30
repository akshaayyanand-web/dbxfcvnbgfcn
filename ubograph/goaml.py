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
from datetime import datetime
from typing import Optional


def _sub(parent, tag, text=None):
    el = ET.SubElement(parent, tag)
    if text not in (None, ""):
        el.text = str(text)
    return el


def build_xml(report: dict, reason: str = "") -> bytes:
    subject = report["subject"]
    is_person = subject.get("type") == "person"

    root = ET.Element("report")
    root.set("draft", "true")
    root.set("note", "Starting point only — not validated against the goAML XSD. Complete in goAML.")

    header = _sub(root, "report_header")
    _sub(header, "generated_by", "Sanctions+")
    _sub(header, "generated_at", datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))
    _sub(header, "report_type", "STR")  # Suspicious Transaction Report — adjust if this is an SAR
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
