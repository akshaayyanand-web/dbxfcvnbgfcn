"""Renders a report dict (from report.build_report) into a PDF."""
import io
import re
from typing import List, Optional

from report import auto_risk_assessment
from tz import format_dubai

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
    "black_list": colors.HexColor("#111111"),
    "grey_list": colors.HexColor("#767267"),
}
RATING_COLOUR = {
    "Low": BAND_COLOUR["green"], "Medium": BAND_COLOUR["orange"],
    "High": BAND_COLOUR["red"], "Critical": colors.HexColor("#111111"),
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
        # FATF's own black/grey list gets a literal black/grey marking here
        # too, instead of borrowing the red/orange severity colour that
        # would read as "this entity is sanctioned".
        band = finding.get("marking") or severity_band.get(finding.get("severity"), "green")
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


def _auto_risk_assessment_flow(assessment: dict, styles) -> List:
    """The automatic risk assessment every downloaded report now carries,
    derived from this entity's own screening result — see
    report.auto_risk_assessment(). Distinct from the manual client
    risk-rating worksheet rendered by _risk_rating_flow() below, which is a
    separate form the user fills in by hand."""
    if not assessment:
        return []
    rating = assessment["overall_rating"]
    chip = Table(
        [[Paragraph(
            f'<font color="white"><b>{rating.upper()} RISK '
            f'— {_clean(assessment.get("risk_score"))} / 100</b></font>', styles["small"],
        )]],
        colWidths=[62 * mm],
    )
    chip.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), RATING_COLOUR.get(rating, MUTED)),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    flow = [
        Paragraph("Risk Assessment", styles["h2"]),
        Paragraph(
            "Generated automatically from this entity's own screening result — "
            "not a separate form.", styles["small"],
        ),
        chip, Spacer(1, 8),

        Paragraph("<b>Risk factors identified</b>", styles["body"]),
    ]
    for factor in assessment["risk_factors"]:
        flow.append(Paragraph(f"• {_clean(factor)}", styles["body"]))

    flow.append(Paragraph("<b>Screening results</b>", styles["body"]))
    flow.append(Paragraph(_clean(assessment["screening_results"]), styles["body"]))

    flow.append(Paragraph("<b>Recommended actions</b>", styles["body"]))
    for action in assessment["recommended_actions"]:
        flow.append(Paragraph(f"• {_clean(action)}", styles["body"]))

    flow.append(Paragraph("<b>Analyst comments</b>", styles["body"]))
    flow.append(Paragraph(_clean(assessment["analyst_comments"]), styles["body"]))

    flow.append(Paragraph(
        f"<font size='8' color='#6B645A'>Risk assessment generated "
        f"{_clean(assessment['generated_at'])}</font>", styles["body"]))
    return flow


def _signature_block(styles) -> List:
    """Prepared By / Reviewed By / Approved By placeholders for every official
    compliance document this platform generates. Nothing here is pre-filled —
    each is a blank line for the actual reviewing officer to complete, by hand
    or through the firm's own sign-off process; this tool has no reviewer
    identity to put here and must not invent one.
    """
    rows = [[
        Paragraph(f"<b>{role}:</b> _______________________________", styles["cell"]),
        Paragraph("<b>Date:</b> ________________", styles["cell"]),
    ] for role in ("Prepared By", "Reviewed By", "Approved By")]
    table = Table(rows, colWidths=[105 * mm, 55 * mm])
    table.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 16), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (0, -1), 0),
    ]))
    return [
        Spacer(1, 10),
        HRFlowable(width="100%", color=LINE, spaceAfter=6),
        Paragraph("Signatures", styles["h2"]),
        Paragraph(
            "This document is a lead for a human reviewer, not a self-certifying "
            "record — it is not considered complete for a compliance file until "
            "signed off below.", styles["small"],
        ),
        table,
    ]


def _risk_matrix_table(matrix: list, current_band: Optional[str], styles) -> Table:
    """Where the score actually landed, in the context of the full scale —
    a reviewer can see at a glance how close a Medium is to High, for
    example, not just the final label."""
    header = ["Band", "Score range", ""]
    data = [[Paragraph(_clean(h), styles["cellhead"]) for h in header]]
    for entry in matrix:
        marker = "◄ this result" if entry["band"] == current_band else ""
        data.append([
            Paragraph(_clean(entry["label"]), styles["cell"]),
            Paragraph(_clean(entry["range"]), styles["cell"]),
            Paragraph(f"<b>{_clean(marker)}</b>", styles["cell"]),
        ])
    table = Table(data, colWidths=[35 * mm, 35 * mm, 40 * mm], repeatRows=1)
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, LINE),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    for index, entry in enumerate(matrix, start=1):
        style.append(("BACKGROUND", (0, index), (0, index), BAND_COLOUR.get(entry["band"], MUTED)))
        style.append(("TEXTCOLOR", (0, index), (0, index), colors.white))
    table.setStyle(TableStyle(style))
    return table


def _risk_rating_flow(rating: dict, styles) -> List:
    """The client risk-rating worksheet, only when the caller supplied one —
    a separate, manual score computed in the browser, not derived from the
    graph above it."""
    if not rating or not rating.get("rows"):
        return []
    band_colour = {"low": "green", "medium": "orange", "high": "red"}
    band_label = {"low": "LOW RISK", "medium": "MEDIUM RISK", "high": "HIGH RISK"}
    flow = [
        Paragraph("Client risk rating", styles["h2"]),
        Paragraph(
            "A separate, manual worksheet using the same weighted rubric as a real "
            "client AML risk-rating spreadsheet — not derived from the graph above.",
            styles["small"],
        ),
    ]
    subject_rows = [
        ("Subject", rating.get("subject_name")),
        ("Screening reference", rating.get("screening_reference")),
    ]
    subject_rows = [(label, value) for label, value in subject_rows if value]
    if subject_rows:
        data = [
            [Paragraph(_clean(label), styles["cellhead"]), Paragraph(_clean(value), styles["cell"])]
            for label, value in subject_rows
        ]
        table = Table(data, colWidths=[45 * mm, None])
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (0, -1), 0),
        ]))
        flow += [table, Spacer(1, 6)]
    if rating.get("band"):
        chip = Table(
            [[Paragraph(
                f'<font color="white"><b>{band_label[rating["band"]]} '
                f'— {_clean(rating["score"])} / 100</b></font>', styles["small"],
            )]],
            colWidths=[62 * mm],
        )
        chip.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), BAND_COLOUR.get(band_colour[rating["band"]], MUTED)),
            ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        flow += [chip, Spacer(1, 6)]
    else:
        flow.append(Paragraph("Incomplete — not every field was selected.", styles["small"]))

    marking_label = {"black_list": "BLACK LIST", "grey_list": "GREY LIST"}
    marking_colour = {"black_list": "#111111", "grey_list": "#767267"}
    header = ["Criterion", "Selected", "Score", "Weight", "Weighted"]
    data = [[Paragraph(_clean(h), styles["cellhead"]) for h in header]]
    for row in rating["rows"]:
        selected = _clean(row.get("selected") or "—")
        marking = row.get("marking")
        if marking:
            selected += (f' <font color="{marking_colour[marking]}">'
                         f'<b>[{marking_label[marking]}]</b></font>')
        data.append([
            Paragraph(_clean(row["criterion"]), styles["cell"]),
            Paragraph(selected, styles["cell"]),
            Paragraph(_clean(row.get("score") if row.get("score") is not None else "—"), styles["cell"]),
            Paragraph(_clean(row.get("weight") if row.get("weight") is not None else "—"), styles["cell"]),
            Paragraph(_clean(row.get("weighted_score") if row.get("weighted_score") is not None else "—"),
                      styles["cell"]),
        ])
    table = Table(data, colWidths=[42 * mm, 48 * mm, 18 * mm, 18 * mm, 22 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, LINE),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    flow.append(table)
    if rating.get("missing"):
        flow.append(Paragraph(f"Not yet scored: {_clean(', '.join(rating['missing']))}.", styles["small"]))
    flow.append(Paragraph(f"Source: {_clean(rating.get('source'))}", styles["small"]))

    if rating.get("risk_matrix"):
        flow.append(Spacer(1, 8))
        flow.append(Paragraph("<b>Risk matrix</b>", styles["body"]))
        flow.append(_risk_matrix_table(rating["risk_matrix"], rating.get("band"), styles))

    if rating.get("reasoning"):
        flow.append(Paragraph("<b>Reasoning</b>", styles["body"]))
        flow.append(Paragraph(_clean(rating["reasoning"]), styles["body"]))

    if rating.get("mitigation"):
        flow.append(Paragraph("<b>Mitigation recommendations</b>", styles["body"]))
        for item in rating["mitigation"]:
            flow.append(Paragraph(f"• {_clean(item)}", styles["body"]))

    flow.append(Paragraph("<b>Compliance notes</b>", styles["body"]))
    flow.append(Paragraph(_clean(rating.get("compliance_notes") or "None recorded."), styles["body"]))

    meta_rows = [
        ("Date generated", format_dubai()),
        ("Prepared by", rating.get("prepared_by") or "Not recorded"),
        ("Review status", rating.get("review_status")),
    ]
    data = [
        [Paragraph(_clean(label), styles["cellhead"]), Paragraph(_clean(value), styles["cell"])]
        for label, value in meta_rows if value
    ]
    table = Table(data, colWidths=[45 * mm, None])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (0, -1), 0),
    ]))
    flow += [Spacer(1, 8), table]
    return flow


def _dossier_flow(report: dict, styles) -> List:
    """Full source detail: what each list actually records about the subject."""
    dossier = report.get("dossier")
    flow = []
    if not dossier:
        if report.get("dossier_error"):
            flow.append(Paragraph("Source detail", styles["h2"]))
            flow.append(Paragraph(_clean(report["dossier_error"]), styles["small"]))
        return flow

    flow.append(Paragraph("Source detail", styles["h2"]))
    lists = " · ".join(d.get("title") or d.get("name") for d in dossier.get("datasets") or [])
    flow.append(Paragraph(f"<b>Listed on:</b> {_clean(lists) or 'no dataset recorded'}",
                          styles["body"]))
    if (dossier.get("record_count") or 1) > 1:
        flow.append(Paragraph(
            f"Combined from {dossier['record_count']} source records "
            f"({_clean(', '.join(dossier.get('record_ids') or []))}). Values appearing on "
            "more than one list are stated once.", styles["small"]))
    if dossier.get("last_change"):
        flow.append(Paragraph(
            f"Source last changed {_clean(dossier['last_change'])} · first seen "
            f"{_clean(dossier.get('first_seen') or 'unknown')}", styles["small"]))

    for group in dossier.get("groups") or []:
        flow.append(Paragraph(_clean(group["title"]), styles["h2"]))
        data = [
            [Paragraph(_clean(row["label"]), styles["cellhead"]),
             Paragraph("<br/>".join(_clean(v) for v in row["values"]), styles["cell"])]
            for row in group["rows"]
        ]
        table = Table(data, colWidths=[45 * mm, None])
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 0), (-1, -2), 0.25, LINE),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (0, -1), 0),
        ]))
        flow.append(table)

    for index, sanction in enumerate(dossier.get("sanctions") or []):
        heading = "Sanction records" if index == 0 else None
        if heading:
            flow.append(Paragraph(heading, styles["h2"]))
        rows = [
            ("Authority", sanction.get("authority")),
            ("Programme", sanction.get("program")),
            ("Reason", sanction.get("reason")),
            ("Provisions", ", ".join(sanction.get("provisions") or [])),
            ("Status", sanction.get("status")),
            ("Listed", sanction.get("listing_date")),
            ("Start date", sanction.get("start_date")),
            ("End date", sanction.get("end_date")),
            ("Authority ref.", sanction.get("authority_id")),
            ("UNSC ID", sanction.get("unsc_id")),
            ("List", ", ".join(d.get("title") or d.get("name")
                               for d in sanction.get("datasets") or [])),
            ("Source", sanction.get("source_url")),
        ]
        data = [
            [Paragraph(_clean(label), styles["cellhead"]), Paragraph(_clean(value), styles["cell"])]
            for label, value in rows if value
        ]
        if not data:
            continue
        table = Table(data, colWidths=[38 * mm, None])
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOX", (0, 0), (-1, -1), 0.4, LINE),
            ("LINEBEFORE", (0, 0), (0, -1), 3, BAND_COLOUR["red"]),
            ("LINEBELOW", (0, 0), (-1, -2), 0.25, LINE),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (0, -1), 7),
        ]))
        flow += [table, Spacer(1, 7)]

    relationships = dossier.get("relationships") or []
    if relationships:
        flow.append(Paragraph("Recorded relationships", styles["h2"]))
        data = [[Paragraph(_clean(h), styles["cellhead"])
                 for h in ("Type", "Role", "Party", "Period")]]
        for relationship in relationships:
            period = " – ".join(
                x for x in [relationship.get("start_date"), relationship.get("end_date")] if x
            )
            data.append([
                Paragraph(_clean(relationship.get("kind")), styles["cell"]),
                Paragraph(_clean(relationship.get("role") or "—"), styles["cell"]),
                Paragraph(_clean(relationship.get("name")), styles["cell"]),
                Paragraph(_clean(period or "—"), styles["cell"]),
            ])
        table = Table(data, colWidths=[28 * mm, 40 * mm, 62 * mm, 30 * mm], repeatRows=1)
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 0), (-1, 0), 0.6, LINE),
            ("LINEBELOW", (0, 1), (-1, -1), 0.25, LINE),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (0, -1), 0),
        ]))
        flow.append(table)
    return flow


def render(report: dict, risk_rating: dict = None, analyst_comments: Optional[str] = None) -> bytes:
    styles = _styles()
    subject = report["subject"]
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
        title=f"Due diligence report — {subject.get('name')}",
        author="Sanctions+",
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
    ]
    for note in subject.get("notes") or []:
        colour = "#b45309" if "weak match" in note.lower() else "#666666"
        flow.append(Paragraph(f'<font color="{colour}">{_clean(note)}</font>', styles["small"]))
    flow += [
        HRFlowable(width="100%", color=LINE, spaceBefore=4, spaceAfter=2),

        Paragraph("Identifying details", styles["h2"]),
        _facts_table(subject, styles),

    ]
    flow += _dossier_flow(report, styles)
    flow.append(Paragraph("Assessment", styles["h2"]))
    for paragraph in report.get("narrative", []):
        flow.append(Paragraph(_clean(paragraph), styles["body"]))

    if report.get("findings"):
        flow.append(Paragraph("Findings", styles["h2"]))
        flow += _findings_block(report["findings"], styles)

    # Automatic — derived from this entity's own screening result, on every
    # report, not only when a manual client risk-rating workbook was filled
    # in separately (that one follows right after, when supplied).
    flow += _auto_risk_assessment_flow(auto_risk_assessment(report, analyst_comments), styles)

    flow += _risk_rating_flow(risk_rating, styles)

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
    flow += _signature_block(styles)

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(20 * mm, 12 * mm, f"Sanctions+ · {subject.get('name')}")
        canvas.drawRightString(A4[0] - 20 * mm, 12 * mm, f"page {document.page}")
        canvas.restoreState()

    doc.build(flow, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()


def render_edd_checklist(report: dict, rows: List[dict]) -> bytes:
    """The Enhanced Due Diligence checklist as its own PDF, so it can sit in a
    client file alongside the main report rather than only living on screen."""
    styles = _styles()
    subject = report["subject"]
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
        title=f"EDD checklist — {subject.get('name')}",
        author="Sanctions+",
    )
    answer_colour = {"Yes": BAND_COLOUR["red"], "No": BAND_COLOUR["green"]}
    flow = [
        Paragraph("Enhanced Due Diligence Checklist", styles["title"]),
        Paragraph(
            f"{_clean(subject.get('name'))} · generated {format_dubai()}",
            styles["sub"],
        ),
        Paragraph(
            "Each answer is sourced from this entity's record where the data exists. "
            "“Not available” means this tool has no source for that fact — it must be "
            "confirmed from the client's own file, not treated as a “no”.",
            styles["small"],
        ),
        HRFlowable(width="100%", color=LINE, spaceBefore=4, spaceAfter=8),
    ]
    for row in rows:
        colour = answer_colour.get(row["answer"], MUTED)
        table = Table(
            [[
                "",
                Paragraph(
                    f'<b>{_clean(row["question"])}</b><br/>'
                    f'<font color="#{colour.hexval()[2:]}"><b>{_clean(row["answer"])}</b></font>'
                    f'<br/><font size="9">{_clean(row["basis"])}</font>',
                    styles["cell"],
                ),
            ]],
            colWidths=[3 * mm, None],
        )
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), colour),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (1, 0), (1, 0), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        flow += [table, Spacer(1, 6)]

    flow.append(Spacer(1, 8))
    flow.append(HRFlowable(width="100%", color=LINE, spaceAfter=6))
    flow.append(Paragraph(
        "A lead for a human reviewer, not a compliance determination — sign-off on the "
        "business relationship remains a judgement call for the compliance officer.",
        styles["small"],
    ))
    flow += _signature_block(styles)

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(20 * mm, 12 * mm, f"Sanctions+ · EDD checklist · {subject.get('name')}")
        canvas.drawRightString(A4[0] - 20 * mm, 12 * mm, f"page {document.page}")
        canvas.restoreState()

    doc.build(flow, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()


def render_mou_draft(report: dict, role: str = "purchaser") -> bytes:
    """A resale MOU draft with the searched entity pre-filled as buyer or
    seller — everything else (price, property, dates) is left blank for the
    lawyer to complete. Modeled loosely on a standard UAE resale MOU; it is a
    starting draft, not a substitute for the firm's own reviewed template."""
    styles = _styles()
    subject = report["subject"]
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
        title="Memorandum of Understanding (draft)",
        author="Sanctions+",
    )
    blank = "……………………………………………"
    seller = _clean(subject.get("name")) if role == "seller" else blank
    purchaser = _clean(subject.get("name")) if role == "purchaser" else blank

    def field_row(label, value):
        return Table(
            [[Paragraph(_clean(label), styles["cellhead"]), Paragraph(value, styles["cell"])]],
            colWidths=[55 * mm, None],
        )

    flow = [
        Paragraph("Memorandum of Understanding", styles["title"]),
        Paragraph(
            f"DRAFT — generated {format_dubai()}. "
            f"{_clean(subject.get('name'))} pre-filled as {role}; every other field is a "
            "placeholder for the acting lawyer to complete and review before use.",
            styles["sub"],
        ),
        HRFlowable(width="100%", color=LINE, spaceBefore=4, spaceAfter=8),

        Paragraph("Schedule A — Parties", styles["h2"]),
        field_row("Seller", f"{seller}, holder of EID No. {blank}"),
        Spacer(1, 4),
        field_row("Purchaser", f"{purchaser}, holder of EID No. {blank}"),
        Spacer(1, 4),
        field_row("Broker", blank),
        Spacer(1, 10),

        Paragraph("Schedule B — Property", styles["h2"]),
        field_row("Location", blank),
        Spacer(1, 3), field_row("Developer", blank),
        Spacer(1, 3), field_row("Project / unit number", blank),
        Spacer(1, 3), field_row("Unit type / size", blank),
        Spacer(1, 10),

        Paragraph("Schedule C — Purchase price & fees", styles["h2"]),
        field_row("Original price", blank),
        Spacer(1, 3), field_row("Net selling price", blank),
        Spacer(1, 3), field_row("Security deposit", blank),
        Spacer(1, 3), field_row("Agency fee", blank),
        Spacer(1, 10),

        Paragraph("Schedule D — Signatures", styles["h2"]),
        Paragraph(f"Seller: {blank}&nbsp;&nbsp;&nbsp; Date: {blank}", styles["body"]),
        Paragraph(f"Purchaser: {blank}&nbsp;&nbsp;&nbsp; Date: {blank}", styles["body"]),
        Paragraph(f"Broker: {blank}&nbsp;&nbsp;&nbsp; Date: {blank}", styles["body"]),

        Spacer(1, 10),
        HRFlowable(width="100%", color=LINE, spaceAfter=6),
        Paragraph(
            "This draft is a starting point only. It has not been reviewed by counsel, "
            "carries no legal terms beyond the schedules above, and must be completed "
            "and checked against the firm's own approved template before use.",
            styles["small"],
        ),
    ]

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(20 * mm, 12 * mm, "Sanctions+ · MOU draft")
        canvas.drawRightString(A4[0] - 20 * mm, 12 * mm, f"page {document.page}")
        canvas.restoreState()

    doc.build(flow, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()


def render_auto_risk_assessment(report: dict, analyst_comments: Optional[str] = None) -> bytes:
    """The automatic risk assessment (see report.auto_risk_assessment) as its
    own standalone PDF — the same section already embedded in the full
    report, broken out separately for the "Download All" investigation
    package, where it's expected as its own file."""
    styles = _styles()
    subject = report["subject"]
    assessment = auto_risk_assessment(report, analyst_comments)
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
        title=f"Risk Assessment — {subject.get('name')}",
        author="Sanctions+",
    )
    flow = [
        Paragraph(_clean(subject.get("name")), styles["title"]),
        Paragraph(
            f"Risk Assessment · generated {_clean(assessment['generated_at'])}"
            + (" · SAMPLE DATA, NOT A REAL RECORD" if report.get("demo_mode") else ""),
            styles["sub"],
        ),
        HRFlowable(width="100%", color=LINE, spaceBefore=4, spaceAfter=2),
    ]
    flow += _auto_risk_assessment_flow(assessment, styles)
    flow += _signature_block(styles)

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(20 * mm, 12 * mm, f"Sanctions+ · Risk Assessment · {subject.get('name')}")
        canvas.drawRightString(A4[0] - 20 * mm, 12 * mm, f"page {document.page}")
        canvas.restoreState()

    doc.build(flow, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()


def render_risk_rating(rating: dict) -> bytes:
    """A standalone PDF for the Risk Assessment tab's worksheet — independent
    of any entity, search, or report, exactly like the tab itself."""
    styles = _styles()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
        title="Client Risk Rating",
        author="Sanctions+",
    )
    flow = [
        Paragraph("Client Risk Rating", styles["title"]),
        Paragraph(
            f"Generated {format_dubai()} · "
            "standalone worksheet, not tied to any search or entity",
            styles["sub"],
        ),
        HRFlowable(width="100%", color=LINE, spaceBefore=4, spaceAfter=2),
    ]
    flow += _risk_rating_flow(rating, styles)
    flow += _signature_block(styles)

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(20 * mm, 12 * mm, "Sanctions+ · Client Risk Rating")
        canvas.drawRightString(A4[0] - 20 * mm, 12 * mm, f"page {document.page}")
        canvas.restoreState()

    doc.build(flow, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
