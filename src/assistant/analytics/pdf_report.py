"""PDF rendering for the export-safe analytics evidence report."""

from __future__ import annotations

from html import escape
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def build_analytics_report_pdf(markdown: str) -> bytes:
    """Render the existing analytics markdown report as a polished PDF."""

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=17 * mm,
        title="Analytics Evidence Report",
        author="AI Knowledge and Analytics Assistant",
    )
    styles = _styles()
    story = _story_from_markdown(markdown, styles)
    doc.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    return buffer.getvalue()


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ReportTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=25,
            textColor=colors.HexColor("#0f172a"),
            spaceAfter=10,
        ),
        "heading": ParagraphStyle(
            "ReportHeading",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=17,
            textColor=colors.HexColor("#0f172a"),
            spaceBefore=10,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "ReportBody",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#334155"),
            spaceAfter=5,
        ),
        "bullet": ParagraphStyle(
            "ReportBullet",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            leftIndent=12,
            firstLineIndent=-8,
            textColor=colors.HexColor("#334155"),
            spaceAfter=4,
        ),
        "table_header": ParagraphStyle(
            "ReportTableHeader",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=9.5,
            textColor=colors.white,
        ),
        "table_cell": ParagraphStyle(
            "ReportTableCell",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7.2,
            leading=9,
            textColor=colors.HexColor("#334155"),
        ),
    }


def _story_from_markdown(markdown: str, styles: dict[str, ParagraphStyle]) -> list:
    story: list = []
    table_lines: list[str] = []

    def flush_table() -> None:
        if table_lines:
            story.append(_table_from_lines(table_lines, styles))
            story.append(Spacer(1, 6))
            table_lines.clear()

    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if _is_table_line(line):
            table_lines.append(line)
            continue

        flush_table()
        if not line:
            story.append(Spacer(1, 3))
        elif line.startswith("# "):
            story.append(Paragraph(_inline(line[2:]), styles["title"]))
        elif line.startswith("## "):
            story.append(Paragraph(_inline(line[3:]), styles["heading"]))
        elif line.startswith("- "):
            story.append(Paragraph(f"- {_inline(line[2:])}", styles["bullet"]))
        else:
            story.append(Paragraph(_inline(line), styles["body"]))

    flush_table()
    return story


def _table_from_lines(lines: list[str], styles: dict[str, ParagraphStyle]) -> Table:
    rows = [_split_table_row(line) for line in lines if not _is_separator_row(line)]
    if not rows:
        rows = [["n/a"]]
    column_count = max(len(row) for row in rows)
    width = A4[0] - 36 * mm
    col_widths = [width / column_count for _ in range(column_count)]
    rendered = []
    for row_index, row in enumerate(rows):
        style = styles["table_header"] if row_index == 0 else styles["table_cell"]
        padded = [*row, *("" for _ in range(column_count - len(row)))]
        rendered.append([Paragraph(_inline(cell), style) for cell in padded])
    table = Table(rendered, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f8fafc")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d8dde6")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _split_table_row(line: str) -> list[str]:
    return [part.strip() for part in line.strip("|").split("|")]


def _is_table_line(line: str) -> bool:
    return line.startswith("|") and line.endswith("|") and "|" in line[1:-1]


def _is_separator_row(line: str) -> bool:
    parts = [part.strip() for part in line.strip("|").split("|")]
    return bool(parts) and all(part and set(part) <= {"-", ":"} for part in parts)


def _inline(value: str) -> str:
    return escape(value.replace("`", "")).replace("\n", " ")


def _page_footer(canvas, doc) -> None:  # type: ignore[no-untyped-def]
    canvas.saveState()
    canvas.setFillColor(colors.white)
    canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor("#667085"))
    canvas.drawString(18 * mm, 10 * mm, "AI Knowledge and Analytics Assistant - analytics evidence report")
    canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()
