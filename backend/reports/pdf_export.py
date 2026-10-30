"""Render a structured report (report_generator) to PDF, JSON and CSV files."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.platypus import Image, ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle  # noqa: E402

# Design-system colours (light theme) for print.
INK, MUTED, SUBTLE, LINE, SURFACE = "#0d1116", "#3a414b", "#5f6773", "#dfe3e8", "#f3f5f7"
CLASS_STYLE = {"measured": ("#0a63b8", "-"), "image_derived": ("#0a63b8", "-"), "calculated": ("#3a414b", "-"), "predicted": ("#4c6a00", "--"),
               "simulated": ("#5f6773", ":")}
COMPARE = ["#0a63b8", "#c2410c", "#6941c6", "#0b6f80", "#4c6a00"]


def _figure_png(block: dict) -> bytes | None:
    series = [s for s in block.get("series", []) if s.get("points")]
    if not series:
        return None
    fig, ax = plt.subplots(figsize=(6.4, 2.6), dpi=160)
    for i, s in enumerate(series):
        color, ls = CLASS_STYLE.get(s.get("class"), (INK, "-"))
        if len(series) > 1:
            color = COMPARE[i % len(COMPARE)]
        xs, ys = zip(*s["points"])
        ax.plot(xs, ys, ls, color=color, lw=1.4, label=s.get("name"))
    ax.set_xlabel(block.get("x", ""), color=SUBTLE, fontsize=8)
    ax.set_ylabel(block.get("y", ""), color=SUBTLE, fontsize=8)
    ax.tick_params(colors=SUBTLE, labelsize=7)
    ax.grid(True, color=LINE, lw=0.6)
    for sp in ax.spines.values():
        sp.set_color(LINE)
    if len(series) > 1:
        ax.legend(fontsize=7, frameon=False)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue()


def _esc(x) -> str:
    return (str(x) if x is not None else "—").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_pdf(report: dict, path: Path) -> None:
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Title"], fontName="Helvetica", fontSize=20, leading=24, textColor=INK, alignment=0)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=12, leading=16, textColor=INK, spaceBefore=10)
    body = ParagraphStyle("b", parent=ss["BodyText"], fontName="Helvetica", fontSize=9, leading=13, textColor=MUTED)
    small = ParagraphStyle("s", parent=body, fontSize=7.5, leading=10, textColor=SUBTLE)
    story = [Paragraph(_esc(report["title"]), h1),
             Paragraph(f"Generated {_esc(report['generated_at'][:19].replace('T', ' '))} UTC by Flame in Freefall · "
                       f"report schema {_esc(report['schema'])}", small), Spacer(1, 6 * mm)]
    for sec in report["sections"]:
        story.append(Paragraph(_esc(sec["title"]), h2))
        for b in sec["blocks"]:
            t = b["type"]
            if t == "p":
                story.append(Paragraph(_esc(b["text"]), body))
            elif t == "list":
                story.append(ListFlowable([ListItem(Paragraph(_esc(x), body)) for x in b["items"]], bulletType="bullet",
                                          leftIndent=10, bulletFontSize=6))
            elif t in ("kv", "table"):
                rows = [[Paragraph(_esc(c), body) for c in r] for r in b["rows"]]
                if t == "table":
                    rows.insert(0, [Paragraph(f"<b>{_esc(c)}</b>", small) for c in b["columns"]])
                    if b.get("title"):
                        story.append(Paragraph(_esc(b["title"]), small))
                widths = [55 * mm, 115 * mm] if t == "kv" else None
                tbl = Table(rows, colWidths=widths, repeatRows=1 if t == "table" else 0)
                style = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor(LINE)), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                         ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]
                if t == "table":
                    style.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(SURFACE)))
                else:
                    style.append(("BACKGROUND", (0, 0), (0, -1), colors.HexColor(SURFACE)))
                tbl.setStyle(TableStyle(style))
                story.append(tbl)
            elif t == "figure":
                png = _figure_png(b)
                story.append(Paragraph(_esc(b.get("title")), small))
                if png:
                    story.append(Image(io.BytesIO(png), width=165 * mm, height=67 * mm))
                else:
                    story.append(Paragraph("No data points for this figure.", body))
            story.append(Spacer(1, 2 * mm))
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                            bottomMargin=16 * mm, title=report["title"], author="Flame in Freefall")
    doc.build(story)


def write_report_files(report: dict, out_dir: Path, measurements: list[dict] | None) -> list[str]:
    """Write report.json, report.pdf and (with measurements) measurements.csv. Returns the formats written."""
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(json.dumps(report, indent=1, default=str))
    render_pdf(report, out_dir / "report.pdf")
    formats = ["json", "pdf"]
    if measurements:
        cols = [k for k in measurements[0].keys() if k != "contour_px"]
        with open(out_dir / "measurements.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            for m in measurements:
                row = dict(m)
                if isinstance(row.get("warnings"), list):
                    row["warnings"] = "; ".join(row["warnings"])
                w.writerow(row)
        formats.append("csv")
    return formats
