"""Server-side Activity-view SVG renderer for the Enterprise Activity Model."""
# ruff: noqa: E501

from __future__ import annotations

import base64
import hashlib
from functools import lru_cache
from html import escape
from pathlib import Path

from .model import EamFinding, EamModel, EamNode

_BAND_COLOURS = {
    "green": "#22c55e",
    "amber": "#f59e0b",
    "red": "#ef4444",
}

_DOMAIN_ICON_FILES = {
    "ordering": "ordering.png",
    "receiving-returns-recalls": "receiving.png",
    "grir-invoice-reconciliation": "invoice.png",
    "stock-management": "stock-management.png",
    "trading": "trading.png",
    "ranging": "ranging.png",
    "sales": "sales.png",
    "business-day-management": "business.png",
    "site-closure": "site.png",
    "promotions": "promotions.png",
    "specials": "specials.png",
    "forecasting-replenishment": "forecast.png",
}

_DOMAIN_PREFIXES = {
    "ordering": "ORD",
    "receiving-returns-recalls": "REC",
    "grir-invoice-reconciliation": "INV",
    "stock-management": "STK",
    "trading": "TRD",
    "ranging": "RNG",
    "sales": "SAL",
    "business-day-management": "BDM",
    "site-closure": "SIT",
    "promotions": "PRO",
    "specials": "SPC",
    "forecasting-replenishment": "FOR",
}


def render_activity_svg(model: EamModel) -> str:
    """Render the EAM domain x lifecycle Activity view as deterministic SVG."""

    left = 220
    top = 380
    col_w = 230
    row_h = 190
    cell_pad = 14
    width = left + (len(model.lifecycle_stages) * col_w) + 56
    height = top + (len(model.domains) * row_h) + 218
    node_positions = _node_positions(model, left, top, col_w, row_h, cell_pad)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="Enterprise Activity Model">',
        _defs(),
        _background(width, height),
        _header(model, width),
        *_column_headers(model, left, top, col_w),
        *_row_headers(model, top, row_h),
        *_cells(model, left, top, col_w, row_h),
        *_edges(model, node_positions),
        *_clash_edges(model.findings, node_positions),
        *_nodes(model, node_positions),
        *_stage_strip(model, left, top + (len(model.domains) * row_h) + 36, col_w),
        _legend(width, height),
        "</svg>",
    ]
    return "\n".join(parts)


def _defs() -> str:
    return """<defs>
  <filter id="eam-shadow" x="-30%" y="-30%" width="160%" height="180%">
    <feDropShadow dx="0" dy="10" stdDeviation="10" flood-color="#020617" flood-opacity="0.48"/>
  </filter>
  <filter id="eam-card-glow" x="-35%" y="-35%" width="170%" height="190%">
    <feDropShadow dx="0" dy="0" stdDeviation="5" flood-color="#15f5b0" flood-opacity="0.22"/>
    <feDropShadow dx="0" dy="9" stdDeviation="8" flood-color="#020617" flood-opacity="0.46"/>
  </filter>
  <filter id="eam-amber-glow" x="-35%" y="-35%" width="170%" height="190%">
    <feDropShadow dx="0" dy="0" stdDeviation="5" flood-color="#f59e0b" flood-opacity="0.25"/>
    <feDropShadow dx="0" dy="9" stdDeviation="8" flood-color="#020617" flood-opacity="0.46"/>
  </filter>
  <filter id="eam-red-glow" x="-35%" y="-35%" width="170%" height="190%">
    <feDropShadow dx="0" dy="0" stdDeviation="5" flood-color="#ef4444" flood-opacity="0.28"/>
    <feDropShadow dx="0" dy="9" stdDeviation="8" flood-color="#020617" flood-opacity="0.46"/>
  </filter>
  <marker id="arrow-cyan" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto" markerUnits="strokeWidth">
    <path d="M0,0 L9,4.5 L0,9 z" fill="#38bdf8"/>
  </marker>
  <marker id="arrow-orange" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto" markerUnits="strokeWidth">
    <path d="M0,0 L9,4.5 L0,9 z" fill="#fb923c"/>
  </marker>
  <marker id="arrow-red" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto" markerUnits="strokeWidth">
    <path d="M0,0 L10,5 L0,10 z" fill="#ef4444"/>
  </marker>
</defs>"""


def _background(width: int, height: int) -> str:
    return f'<rect width="{width}" height="{height}" fill="#06121d"/>'


def _header(model: EamModel, width: int) -> str:
    cx = width / 2
    return _coverage_ring(model, cx, 160)


def _coverage_ring(model: EamModel, cx: float, cy: int) -> str:
    score = max(0, min(100, model.coverage.score))
    circumference = 2 * 3.14159 * 98
    progress = circumference * score / 100
    return f"""<g filter="url(#eam-card-glow)">
  <circle cx="{cx:.1f}" cy="{cy}" r="122" fill="#06121e" stroke="#284155" stroke-width="2"/>
  <circle cx="{cx:.1f}" cy="{cy}" r="98" fill="none" stroke="#173143" stroke-width="24"/>
  <circle cx="{cx:.1f}" cy="{cy}" r="98" fill="none" stroke="#46f2b6" stroke-width="24" stroke-linecap="round"
    stroke-dasharray="{progress:.1f} {circumference - progress:.1f}" transform="rotate(-90 {cx:.1f} {cy})"/>
  <circle cx="{cx:.1f}" cy="{cy}" r="68" fill="#071521" stroke="#102b3a"/>
  <text x="{cx:.1f}" y="{cy - 4}" text-anchor="middle" fill="#46f2b6" font-family="Inter, Arial, sans-serif" font-size="60" font-weight="900">{score}%</text>
  <text x="{cx:.1f}" y="{cy + 34}" text-anchor="middle" fill="#f8fafc" font-family="Inter, Arial, sans-serif" font-size="17" font-weight="800">EAM Coverage</text>
  <text x="{cx:.1f}" y="{cy + 150}" text-anchor="middle" fill="#b8c7d9" font-family="Inter, Arial, sans-serif" font-size="14">Breadth of evidenced knowledge</text>
</g>"""


def _column_headers(model: EamModel, left: int, top: int, col_w: int) -> list[str]:
    rows = [
        f'<rect x="24" y="{top - 50}" width="160" height="42" rx="8" fill="#0b1d2b" stroke="#6f8298" opacity="0.94"/>',
        f'<text x="104" y="{top - 24}" text-anchor="middle" fill="#f8fafc" font-family="Inter, Arial, sans-serif" '
        'font-size="13" font-weight="900">RETAIL DOMAIN</text>',
    ]
    for index, stage in enumerate(model.lifecycle_stages):
        x = left + (index * col_w)
        rows.append(
            f'<rect x="{x}" y="{top - 50}" width="{col_w - 10}" height="42" rx="8" fill="#0b1d2b" stroke="#6f8298" opacity="0.94"/>'
            f'<text x="{x + (col_w / 2) - 5:.1f}" y="{top - 24}" text-anchor="middle" fill="#f8fafc" '
            f'font-family="Inter, Arial, sans-serif" font-size="13" font-weight="900">{escape(stage.label).upper()}</text>'
        )
    return rows


def _row_headers(model: EamModel, top: int, row_h: int) -> list[str]:
    rows = []
    coverage_by_domain = {domain.domain_id: domain for domain in model.coverage.domains}
    for index, domain in enumerate(model.domains):
        y = top + (index * row_h)
        coverage = coverage_by_domain.get(domain.id)
        status = coverage.status if coverage else "uncovered"
        node_count = coverage.node_count if coverage else 0
        colour = _status_colour(status)
        rows.append(
            f'<g data-domain-id="{escape(domain.id)}">'
            f'<rect x="24" y="{y}" width="160" height="{row_h - 10}" rx="12" fill="#0a1d2c" stroke="#6f8298" opacity="0.95"/>'
            f'<image x="76" y="{y + 14}" width="56" height="56" preserveAspectRatio="xMidYMid meet" href="{_domain_icon(domain.id)}"/>'
        )
        for line_index, line in enumerate(_wrap_text(domain.label.upper().replace(" AND ", " & "), 18, 3)):
            rows.append(
                f'<text x="104" y="{y + 87 + (line_index * 15)}" text-anchor="middle" fill="#f8fafc" '
                f'font-family="Inter, Arial, sans-serif" font-size="13" font-weight="900">{escape(line)}</text>'
            )
        rows.append(f'<rect x="48" y="{y + row_h - 26}" width="112" height="6" rx="3" fill="#24384a"/>')
        rows.append(
            f'<rect x="48" y="{y + row_h - 26}" width="{max(16, min(112, 16 + (node_count * 16)))}" height="6" rx="3" fill="{colour}"/>'
        )
        rows.append("</g>")
    return rows


def _cells(model: EamModel, left: int, top: int, col_w: int, row_h: int) -> list[str]:
    rows = []
    for domain_index, domain in enumerate(model.domains):
        for stage_index, stage in enumerate(model.lifecycle_stages):
            x = left + (stage_index * col_w)
            y = top + (domain_index * row_h)
            cell = next(item for item in model.cells if item.domain_id == domain.id and item.lifecycle_id == stage.id)
            rows.append(
                f'<rect x="{x}" y="{y}" width="{col_w - 10}" height="{row_h - 10}" rx="12" '
                'fill="#0a1b2a" stroke="#42576b" opacity="0.82"/>'
            )
            if cell.is_gap:
                rows.append(
                    f'<rect x="{x + 8}" y="{y + 8}" width="{col_w - 26}" height="{row_h - 26}" rx="10" '
                    f'fill="#071421" stroke="#55697e" stroke-dasharray="6 6" opacity="0.54"/>'
                )
                rows.append(
                    f'<text x="{x + col_w / 2 - 6:.1f}" y="{y + row_h / 2 - 5:.1f}" text-anchor="middle" '
                    f'fill="#6f8298" font-family="Inter, Arial, sans-serif" font-size="11" font-weight="800">No evidence</text>'
                )
    return rows


def _node_positions(
    model: EamModel,
    left: int,
    top: int,
    col_w: int,
    row_h: int,
    cell_pad: int,
) -> dict[str, tuple[float, float, float, float]]:
    positions: dict[str, tuple[float, float, float, float]] = {}
    node_by_id = {node.id: node for node in model.nodes}
    for domain_index, domain in enumerate(model.domains):
        for stage_index, stage in enumerate(model.lifecycle_stages):
            cell = next(item for item in model.cells if item.domain_id == domain.id and item.lifecycle_id == stage.id)
            node_ids = [node_id for node_id in cell.node_ids if node_id in node_by_id]
            visible_node_ids = node_ids[:3]
            visible_count = len(visible_node_ids)
            if not visible_count:
                continue
            gap = 10
            available_h = row_h - (cell_pad * 2)
            node_h = (available_h - (gap * (visible_count - 1))) / visible_count
            for stack_index, node_id in enumerate(visible_node_ids):
                x = left + (stage_index * col_w) + cell_pad
                y = top + (domain_index * row_h) + cell_pad + (stack_index * (node_h + gap))
                positions[node_id] = (x, y, col_w - 42, node_h)
    return positions


def _nodes(model: EamModel, positions: dict[str, tuple[float, float, float, float]]) -> list[str]:
    rows = []
    node_by_id = {node.id: node for node in model.nodes}
    for cell in model.cells:
        hidden = max(0, len(cell.node_ids) - 3)
        for node_id in cell.node_ids[:3]:
            node = node_by_id[node_id]
            x, y, w, h = positions[node.id]
            colour = _BAND_COLOURS[node.confidence_band]
            title_font = 16 if h >= 120 else 13 if h >= 72 else 11
            line_h = title_font + 4
            chip_h = 20 if h >= 120 else 15 if h >= 72 else 11
            chip_font = 10 if h >= 120 else 8.5 if h >= 72 else 7
            title_y = y + title_font + 10
            chip_y = y + h - chip_h - 12
            title_room = max(1, int((chip_y - title_y - 6) // line_h) + 1)
            label_lines = _wrap_text(node.name, 24 if h >= 120 else 21, min(6, title_room))
            chip_gap = 6
            chip_w = (w - 22 - (chip_gap * 2)) / 3
            code = _node_code(node)
            filter_id = "eam-card-glow" if node.confidence_band == "green" else "eam-amber-glow" if node.confidence_band == "amber" else "eam-red-glow"
            rows.extend(
                [
                    f'<g data-node-id="{escape(node.id)}" filter="url(#{filter_id})">',
                    _node_title(node),
                    f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="8" fill="#071421" stroke="{colour}" stroke-width="1.9"/>',
                    f'<text x="{x + 11:.1f}" y="{title_y:.1f}" fill="#f8fafc" font-family="Inter, Arial, sans-serif" font-size="{title_font}" font-weight="900">{escape(code)}</text>',
                    *_node_label_lines(x + 11, title_y + line_h, line_h, title_font - 1, label_lines),
                    *_metric_chips(
                        x + 11,
                        chip_y,
                        chip_w,
                        chip_h,
                        chip_gap,
                        chip_font,
                        [f"{node.role_count} Roles", f"{node.system_count} Systems", f"{node.control_count} Controls"],
                    ),
                    "</g>",
                ]
            )
        if hidden:
            first_node = node_by_id[cell.node_ids[0]]
            x, y, w, _ = positions[first_node.id]
            rows.append(
                f'<text x="{x + w - 4:.1f}" y="{y + 178:.1f}" text-anchor="end" fill="#9fb1c5" '
                f'font-family="Inter, Arial, sans-serif" font-size="11" font-weight="800">+{hidden} more</text>'
            )
    return rows


def _edges(model: EamModel, positions: dict[str, tuple[float, float, float, float]]) -> list[str]:
    rows = []
    edge_count_by_node: dict[str, int] = {}
    for edge in model.edges:
        if edge.from_node_id not in positions or edge.to_node_id not in positions:
            continue
        if edge_count_by_node.get(edge.from_node_id, 0) >= 4 or edge_count_by_node.get(edge.to_node_id, 0) >= 4:
            continue
        edge_count_by_node[edge.from_node_id] = edge_count_by_node.get(edge.from_node_id, 0) + 1
        edge_count_by_node[edge.to_node_id] = edge_count_by_node.get(edge.to_node_id, 0) + 1
        x1, y1 = _centre(positions[edge.from_node_id])
        x2, y2 = _centre(positions[edge.to_node_id])
        colour = "#38bdf8" if edge.edge_type == "system" else "#fb923c"
        dash = ' stroke-dasharray="7 6"' if edge.edge_type == "system" else ""
        marker = "arrow-cyan" if edge.edge_type == "system" else "arrow-orange"
        mid_x = (x1 + x2) / 2
        path = f"M{x1:.1f},{y1:.1f} L{mid_x:.1f},{y1:.1f} L{mid_x:.1f},{y2:.1f} L{x2:.1f},{y2:.1f}"
        rows.append(
            f'<path data-edge-id="{escape(edge.id)}" d="{path}" fill="none" '
            f'stroke="{colour}" stroke-width="2.2" opacity="0.68" marker-end="url(#{marker})"{dash}/>'
        )
    return rows


def _clash_edges(findings: list[EamFinding], positions: dict[str, tuple[float, float, float, float]]) -> list[str]:
    rows = []
    for finding in findings:
        if finding.finding_type != "clash" or len(finding.node_ids) < 2:
            continue
        left, right = finding.node_ids[0], finding.node_ids[1]
        if left not in positions or right not in positions:
            continue
        x1, y1 = _centre(positions[left])
        x2, y2 = _centre(positions[right])
        mid_x = (x1 + x2) / 2
        rows.append(
            f'<polyline data-finding-id="{escape(finding.id)}" points="{x1:.1f},{y1:.1f} {mid_x - 10:.1f},{y1 - 10:.1f} '
            f'{mid_x + 10:.1f},{y2 + 10:.1f} {x2:.1f},{y2:.1f}" fill="none" stroke="#ef4444" stroke-width="3" '
            f'stroke-linecap="round" opacity="0.94" marker-end="url(#arrow-red)" filter="url(#eam-red-glow)"/>'
        )
        rows.append(
            f'<text x="{mid_x + 18:.1f}" y="{min(y1, y2) - 12:.1f}" fill="#ff5c5c" '
            'font-family="Inter, Arial, sans-serif" font-size="11" font-weight="900">CLASH</text>'
        )
    return rows


def _stage_strip(model: EamModel, left: int, y: int, col_w: int) -> list[str]:
    rows = [
        f'<text x="{left}" y="{y - 18}" fill="#f8fafc" font-family="Inter, Arial, sans-serif" font-size="14" '
        'font-weight="900">PER-STAGE COVERAGE</text>'
    ]
    for index, stage in enumerate(model.lifecycle_stages):
        cells = [cell for cell in model.cells if cell.lifecycle_id == stage.id]
        coverage = round((sum(1 for cell in cells if not cell.is_gap) / len(cells)) * 100) if cells else 0
        x = left + (index * col_w)
        rows.append(f'<rect x="{x}" y="{y}" width="{col_w - 20}" height="12" rx="6" fill="#12283a" stroke="#37516a"/>')
        rows.append(f'<rect x="{x}" y="{y}" width="{(col_w - 20) * coverage / 100:.1f}" height="12" rx="6" fill="#46f2b6"/>')
        rows.append(
            f'<text x="{x + (col_w / 2) - 10:.1f}" y="{y + 34}" text-anchor="middle" fill="#b8c7d9" '
            f'font-family="Inter, Arial, sans-serif" font-size="11" font-weight="800">{coverage}% {escape(stage.label)}</text>'
        )
    return rows


def _legend(width: int, height: int) -> str:
    x = 24
    y = height - 78
    rows = [
        "<g>",
        f'<rect x="{x}" y="{y}" width="{width - 48}" height="54" rx="13" fill="#081928" stroke="#51677d"/>',
        _legend_dot(x + 24, y + 29, "#22c55e", x + 40, y + 34, "strong evidence"),
        _legend_dot(x + 190, y + 29, "#f59e0b", x + 206, y + 34, "partial evidence"),
        _legend_dot(x + 360, y + 29, "#ef4444", x + 376, y + 34, "weak evidence / clash"),
        (
            f'<line x1="{x + 560}" y1="{y + 29}" x2="{x + 610}" y2="{y + 29}" '
            'stroke="#38bdf8" stroke-width="2" stroke-dasharray="7 6"/>'
            f'<text x="{x + 622}" y="{y + 34}" fill="#cbd5e1" font-family="Inter, Arial, sans-serif" '
            'font-size="12">shared system</text>'
        ),
        (
            f'<line x1="{x + 790}" y1="{y + 29}" x2="{x + 840}" y2="{y + 29}" stroke="#fb923c" stroke-width="2"/>'
            f'<text x="{x + 852}" y="{y + 34}" fill="#cbd5e1" font-family="Inter, Arial, sans-serif" '
            'font-size="12">shared control</text>'
        ),
        "</g>",
    ]
    return "\n".join(rows)


def _legend_dot(cx: int, cy: int, colour: str, text_x: int, text_y: int, label: str) -> str:
    return (
        f'<circle cx="{cx}" cy="{cy}" r="6" fill="{colour}"/>'
        f'<text x="{text_x}" y="{text_y}" fill="#cbd5e1" font-family="Inter, Arial, sans-serif" font-size="12">'
        f"{escape(label)}</text>"
    )


def _node_label_lines(x: float, y: float, line_h: float, font_size: float, lines: list[str]) -> list[str]:
    return [
        f'<text x="{x:.1f}" y="{y + (index * line_h):.1f}" fill="#dbeafe" font-family="Inter, Arial, sans-serif" '
        f'font-size="{font_size}" font-weight="700">{escape(line)}</text>'
        for index, line in enumerate(lines)
    ]


def _metric_chips(
    x: float,
    y: float,
    width: float,
    height: float,
    gap: float,
    font_size: float,
    labels: list[str],
) -> list[str]:
    rows: list[str] = []
    for index, label in enumerate(labels):
        chip_x = x + (index * (width + gap))
        rows.append(
            f'<rect x="{chip_x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" rx="5" '
            'fill="#10283a" stroke="#37516a" stroke-width="0.8"/>'
        )
        rows.append(
            f'<text x="{chip_x + (width / 2):.1f}" y="{y + (height / 2) + (font_size / 3):.1f}" text-anchor="middle" '
            f'fill="#c7d7e8" font-family="Inter, Arial, sans-serif" font-size="{font_size}" font-weight="800">'
            f"{escape(label)}</text>"
        )
    return rows


def _status_colour(status: str) -> str:
    if status == "covered":
        return "#46f2b6"
    if status == "partial":
        return "#f59e0b"
    return "#ef4444"


def _node_code(node: EamNode) -> str:
    prefix = _DOMAIN_PREFIXES.get(node.domain_id, "EAM")
    digest = hashlib.sha1(node.id.encode("utf-8")).hexdigest()
    number = (int(digest[:6], 16) % 900) + 100
    return f"{prefix}-{number}"


def _wrap_text(value: str, length: int, max_lines: int) -> list[str]:
    words = value.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= length:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = word
        if len(lines) == max_lines - 1:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    return lines[:max_lines]


def _domain_icon(domain_id: str) -> str:
    icon = _icon_data_uri(domain_id)
    if icon:
        return icon
    fallback = (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 80 80'>"
        "<rect x='14' y='14' width='52' height='52' rx='12' fill='none' stroke='%23dbeafe' stroke-width='4'/>"
        "<path d='M24 44h32M24 32h32M24 56h20' stroke='%23dbeafe' stroke-width='4' stroke-linecap='round'/>"
        "</svg>"
    )
    return "data:image/svg+xml;utf8," + fallback


@lru_cache(maxsize=32)
def _icon_data_uri(domain_id: str) -> str:
    file_name = _DOMAIN_ICON_FILES.get(domain_id)
    if not file_name:
        return ""
    path = Path(__file__).with_name("assets") / file_name
    if not path.exists():
        return ""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _centre(box: tuple[float, float, float, float]) -> tuple[float, float]:
    x, y, w, h = box
    return x + (w / 2), y + (h / 2)


def _truncate(value: str, length: int) -> str:
    if len(value) <= length:
        return value
    return value[: length - 1].rstrip() + "..."


def _node_title(node: EamNode) -> str:
    sources = ", ".join(node.source_refs) if node.source_refs else "no source refs"
    return f"<title>{escape(node.name)} - sources: {escape(sources)}</title>"
