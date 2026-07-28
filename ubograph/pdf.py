"""Renders a report dict (from report.build_report) into a PDF."""
import io
import re
from typing import List

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

BAND_COLOUR = {
    "red": colors.HexColor("#A5321F"),
    "orange": colors.HexColor("#B07407"),
    "green": colors.HexColor("#4F6B44"),
}
INK = colors.HexColor("#1C1A17")
MUTED = colors.HexColor("#6B645A")
LINE = colors.HexColor("#DDD6C9")


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("t", parent=base["Title"], fontName="Times-Bold",
                                fontSize=20, leading=24, textColor=INK, spaceAfter=2),
        "sub": ParagraphStyle("s", parent=base["Normal"], fontName="Helvetica",
                              fontSize=9, textColor=MUTED, spaceAfter=10),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName="Helvetica-Bold",
                             fontSize=10.5, leading=13, textColor=MUTED,
                             spaceBefore=15, spaceAfter=6, keepWithNext=True),
        "body": ParagraphStyle("b", parent=base["Normal"], fontName="Times-Roman",
                               fontSize=10.5, leading=15, textColor=INK,
                               alignment=TA_JUSTIFY, spaceAfter=7),
        "small": ParagraphStyle("sm", parent=base["Normal"], fontName="Helvetica",
                                fontSize=8, leading=11, textColor=MUTED, spaceAfter=4),
        "cell": ParagraphStyle("c", parent=base["Normal"], fontName="Times-Roman",
                               fontSize=9, leading=12, textColor=INK),
        "cellhead": ParagraphStyle("ch", parent=base["Normal"], fontName="Helvetica-Bold",
                                   fontSize=8, leading=10, textColor=MUTED),
        "mono": ParagraphStyle("m", parent=base["Normal"], fontName="Courier",
                               fontSize=8.5, leading=11, textColor=INK),
    }


def _clean(value) -> str:
    """Escape for reportlab's mini-HTML and keep it on one logical line."""
    text = "" if value is None else str(value)
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return re.sub(r"\s+", " ", text).strip()


def _band_chip(band: str, style) -> Table:
    label = {"red": "HIGH RISK", "orange": "ELEVATED RISK", "green": "NO FLAGS FOUND"}.get(
        band, band.upper()
    )
    chip = Table([[Paragraph(f'<font color="white"><b>{label}</b></font>', style)]],
                 colWidths=[42 * mm])
    chip.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BAND_COLOUR.get(band, MUTED)),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return chip


def _facts_table(subject: dict, styles) -> Table:
    rows = [
        ("Type", (subject.get("type") or "").title()),
        ("Nationality / country", subject.get("country_label")),
        ("Date of birth", subject.get("birth_date")),
        ("Jurisdiction", subject.get("jurisdiction_label")),
        ("Registration number", subject.get("reg_number")),
        ("Status", subject.get("status")),
        ("Also known as", " · ".join(subject.get("aliases") or [])),
        ("Risk flags", ", ".join(subject.get("flags") or []) or "none recorded"),
        ("Risk score", f"{subject.get('risk_score')} / 100"),
        ("Sources", ", ".join(subject.get("sources") or [])),
    ]
    data = [
        [Paragraph(_clean(label), styles["cellhead"]), Paragraph(_clean(value), styles["cell"])]
        for label, value in rows if value
    ]
    table = Table(data, colWidths=[45 * mm, None])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -2), 0.25, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (0, -1), 0),
    ]))
    return table


def _affiliation_table(entries: List[dict], styles) -> Table:
    header = ["", "Entity", "Role", "Stake", "Jurisdiction", "Period"]
    data = [[Paragraph(_clean(h), styles["cellhead"]) for h in header]]
    for entry in entries:
        period = " – ".join(x for x in [entry.get("start_date"), entry.get("end_date")] if x)
        data.append([
            "",
            Paragraph(_clean(entry.get("name")), styles["cell"]),
            Paragraph(_clean(entry.get("detail_role") or entry.get("role")), styles["cell"]),
            Paragraph(_clean(entry.get("share")), styles["cell"]),
            Paragraph(_clean(entry.get("jurisdiction")), styles["cell"]),
            Paragraph(_clean(period or "no dates recorded"), styles["cell"]),
        ])
    table = Table(data, colWidths=[4 * mm, 52 * mm, 32 * mm, 15 * mm, 40 * mm, 28 * mm],
                  repeatRows=1)
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, LINE),
        ("LINEBELOW", (1, 1), (-1, -1), 0.25, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (0, -1), 0),
    ]
    for index, entry in enumerate(entries, start=1):
        style.append(("BACKGROUND", (0, index), (0, index),
                      BAND_COLOUR.get(entry.get("band"), MUTED)))
    table.setStyle(TableStyle(style))
    return table


def _findings_block(findings: List[dict], styles) -> List:
    flow = []
    severity_band = {"high": "red", "medium": "orange", "low": "green"}
    for finding in findings:
        band = severity_band.get(finding.get("severity"), "green")
        row = Table(
            [[
                "",
                Paragraph(
                    f'<b>{_clean(finding.get("title"))}</b><br/>'
                    f'<font size="9">{_clean(finding.get("detail"))}</font>',
                    styles["cell"],
                ),
            ]],
            colWidths=[3 * mm, None],
        )
        row.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), BAND_COLOUR.get(band, MUTED)),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (1, 0), (1, 0), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        flow += [row, Spacer(1, 5)]
    return flow


def render(report: dict) -> bytes:
    styles = _styles()
    subject = report["subject"]
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
        title=f"Due diligence report — {subject.get('name')}",
        author="UBOgraph",
    )

    flow = [
        Paragraph(_clean(subject.get("name")), styles["title"]),
        Paragraph(
            f"Beneficial ownership &amp; risk report · generated {_clean(report['generated_at'])}"
            + (" · SAMPLE DATA, NOT A REAL RECORD" if report.get("demo_mode") else ""),
            styles["sub"],
        ),
        _band_chip(subject.get("risk_band", "green"), styles["small"]),
        Spacer(1, 6),
        Paragraph(_clean(subject.get("band_reason")), styles["body"]),
        HRFlowable(width="100%", color=LINE, spaceBefore=4, spaceAfter=2),

        Paragraph("Identifying details", styles["h2"]),
        _facts_table(subject, styles),

        Paragraph("Assessment", styles["h2"]),
    ]
    for paragraph in report.get("narrative", []):
        flow.append(Paragraph(_clean(paragraph), styles["body"]))

    if report.get("findings"):
        flow.append(Paragraph("Findings", styles["h2"]))
        flow += _findings_block(report["findings"], styles)

    affiliations = report.get("affiliations", {})
    if affiliations.get("current"):
        flow.append(Paragraph("Current affiliations", styles["h2"]))
        flow.append(_affiliation_table(affiliations["current"], styles))
    # Rendered even when empty: "none recorded" is a finding a reader needs to
    # see stated, not infer from a missing section.
    flow.append(Paragraph("Previous affiliations", styles["h2"]))
    flow.append(
        _affiliation_table(affiliations["previous"], styles)
        if affiliations.get("previous")
        else Paragraph("None recorded as ended.", styles["body"])
    )
    if affiliations.get("current") or affiliations.get("previous"):
        flow.append(Spacer(1, 3))
        flow.append(Paragraph(_clean(report.get("end_date_note")), styles["small"]))

    if report.get("controllers"):
        flow.append(Paragraph("Controlled by", styles["h2"]))
        for controller in report["controllers"]:
            flow.append(Paragraph(
                f"{_clean(controller['name'])} — {_clean(controller['role'])}"
                + (f" ({_clean(controller['share'])})" if controller.get("share") else ""),
                styles["body"],
            ))

    if report.get("ownership_paths"):
        flow.append(Paragraph("Ownership route", styles["h2"]))
        for path in report["ownership_paths"]:
            flow.append(Paragraph(_clean(" → ".join(path.get("path") or [])), styles["body"]))

    if report.get("identity_matches"):
        flow.append(Paragraph("Unresolved identity matches", styles["h2"]))
        flow.append(Paragraph(
            "These records resemble the subject but were NOT merged. Verify before "
            "treating them as the same person or company.", styles["small"]))
        for match in report["identity_matches"]:
            confidence = match.get("confidence")
            flow.append(Paragraph(
                f"{_clean(match.get('name'))} — similarity "
                f"{int((confidence or 0) * 100)}%", styles["body"]))

    media = report.get("media")
    if media and media.get("available") and (media.get("summary") or media.get("findings")):
        flow.append(Paragraph("Open-web research (unverified)", styles["h2"]))
        flow.append(Paragraph(
            "Retrieved by web search, not from a registry. Every claim must be "
            "checked against its source before use.", styles["small"]))
        if media.get("summary"):
            flow.append(Paragraph(_clean(media["summary"]), styles["body"]))
        for item in media.get("findings") or []:
            flow.append(Paragraph(
                f"• {_clean(item.get('claim'))} "
                f"<font size='8' color='#6B645A'>{_clean(item.get('source_title'))} "
                f"{_clean(item.get('date') or '')}</font>", styles["body"]))

    if subject.get("source_urls"):
        flow.append(Paragraph("Sources", styles["h2"]))
        for url in subject["source_urls"]:
            flow.append(Paragraph(_clean(url), styles["mono"]))

    flow.append(Spacer(1, 10))
    flow.append(HRFlowable(width="100%", color=LINE, spaceAfter=6))
    flow.append(Paragraph(_clean(report.get("disclaimer")), styles["small"]))

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(20 * mm, 12 * mm, f"UBOgraph · {subject.get('name')}")
        canvas.drawRightString(A4[0] - 20 * mm, 12 * mm, f"page {document.page}")
        canvas.restoreState()

    doc.build(flow, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
