""""Download All" — one investigation package instead of downloading each
document separately: the full screening report, the EDD checklist, a
standalone risk assessment, a plain-text evidence/source list, and an audit
trail extract, bundled into a single ZIP.

A ZIP rather than one merged PDF: the documents are already independently
useful (a bank might only want the risk assessment; an auditor might only
want the audit trail), and a ZIP keeps each one a clean, individually
paginated PDF rather than mid-document page breaks stitched from separate
ReportLab flows.
"""
import re
import zipfile
from io import BytesIO
from typing import List, Optional

import db
import edd as edd_module
import pdf as pdf_renderer
from tz import format_dubai_from_epoch


def _safe_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", name or "entity").strip("_") or "entity"


def _evidence_and_sources_txt(report: dict) -> str:
    subject = report["subject"]
    lines = [
        "SANCTIONS+ — EVIDENCE & SOURCE REFERENCES",
        f"Subject: {subject.get('name')}",
        f"Generated: {report.get('generated_at')}",
        "",
        f"Sources checked: {', '.join(report.get('sources_used') or subject.get('sources') or []) or 'none configured'}",
        "",
    ]
    if subject.get("source_urls"):
        lines.append("Source URLs:")
        lines += [f"  - {url}" for url in subject["source_urls"]]
        lines.append("")

    media = report.get("media")
    if media and media.get("available") and media.get("findings"):
        lines.append("Open-web research findings (unverified — not a registry source):")
        for item in media["findings"]:
            lines.append(f"  - {item.get('claim')}")
            attribution = " / ".join(x for x in [item.get("source_title"), item.get("source_url")] if x)
            if attribution:
                lines.append(f"      {attribution}")
        lines.append("")

    if not subject.get("source_urls") and not (media and media.get("findings")):
        lines.append("No individually attributable source URLs on record for this subject.")
    return "\n".join(lines)


def _audit_trail_csv(subject_name: str, limit: int = 500) -> str:
    rows = db.recent_activity(limit)
    matching = [r for r in rows if subject_name and subject_name.lower() in (r.get("detail") or "").lower()]
    lines = ["timestamp,action,detail"]
    for row in matching:
        timestamp = format_dubai_from_epoch(row["at"])
        detail = (row.get("detail") or "").replace('"', "'")
        lines.append(f'"{timestamp}","{row["action"]}","{detail}"')
    if not matching:
        lines.append('"","", "No activity log entries reference this subject by name."')
    return "\n".join(lines)


def build_zip(report: dict, analyst_comments: Optional[str] = None,
              edd_rows: Optional[List[dict]] = None) -> bytes:
    """Everything Download All promises, as one ZIP: the screening report,
    the EDD checklist, a standalone risk assessment, an evidence/source
    list, and an audit trail extract — generated fresh every time from the
    same report structure the on-screen view and every other document use,
    so nothing in the bundle can disagree with what was actually screened.
    """
    subject = report["subject"]
    filename_base = _safe_filename(subject.get("name"))
    edd_rows = edd_rows if edd_rows is not None else edd_module.build_checklist(report)

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            f"01_Screening_Report_{filename_base}.pdf",
            pdf_renderer.render(report, analyst_comments=analyst_comments),
        )
        zf.writestr(
            f"02_Risk_Assessment_{filename_base}.pdf",
            pdf_renderer.render_auto_risk_assessment(report, analyst_comments),
        )
        zf.writestr(
            f"03_EDD_Report_{filename_base}.pdf",
            pdf_renderer.render_edd_checklist(report, edd_rows),
        )
        zf.writestr(
            f"04_Evidence_and_Sources_{filename_base}.txt",
            _evidence_and_sources_txt(report),
        )
        zf.writestr(
            f"05_Audit_Trail_{filename_base}.csv",
            _audit_trail_csv(subject.get("name") or ""),
        )
    return buffer.getvalue()
