"""Server-side Activity-view SVG renderer for the Enterprise Activity Model."""
# ruff: noqa: E501

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
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

_ROW_HEADER_MIN_H = 150
_COLLAPSED_CARD_H = 54
_CARD_GAP = 10


@dataclass(frozen=True)
class _EdgeRoute:
    path: str
    label_x: float
    label_y: float
    label: str


def render_activity_svg(model: EamModel, expanded_node_ids: set[str] | None = None) -> str:
    """Render the EAM domain x lifecycle Activity view as deterministic SVG."""

    expanded_node_ids = expanded_node_ids or set()
    left = 220
    top = 250
    col_w = 230
    cell_pad = 14
    row_heights = _row_heights(model, col_w, cell_pad, expanded_node_ids)
    row_tops = _row_tops(top, row_heights)
    grid_h = sum(row_heights)
    width = left + (len(model.lifecycle_stages) * col_w) + 56
    height = top + grid_h + 218
    node_positions = _node_positions(model, left, row_tops, col_w, cell_pad, expanded_node_ids)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="Enterprise Activity Model">',
        _defs(),
        _background(width, height),
        _header(model, width),
        *_column_headers(model, left, top, col_w),
        *_row_headers(model, row_tops, row_heights),
        *_cells(model, left, row_tops, row_heights, col_w),
        *_edges(model, node_positions),
        *_clash_edges(model.findings, node_positions),
        *_nodes(model, node_positions, expanded_node_ids),
        *_stage_strip(model, left, top + grid_h + 36, col_w),
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
  <filter id="eam-edge-glow" x="-20%" y="-20%" width="140%" height="140%">
    <feDropShadow dx="0" dy="0" stdDeviation="3" flood-color="#38bdf8" flood-opacity="0.22"/>
  </filter>
  <filter id="eam-control-glow" x="-20%" y="-20%" width="140%" height="140%">
    <feDropShadow dx="0" dy="0" stdDeviation="3" flood-color="#fb923c" flood-opacity="0.24"/>
  </filter>
  <marker id="arrow-cyan" markerWidth="6" markerHeight="6" refX="5.4" refY="3" orient="auto" markerUnits="strokeWidth">
    <path d="M0,0 L6,3 L0,6 z" fill="#38bdf8"/>
  </marker>
  <marker id="arrow-orange" markerWidth="6" markerHeight="6" refX="5.4" refY="3" orient="auto" markerUnits="strokeWidth">
    <path d="M0,0 L6,3 L0,6 z" fill="#fb923c"/>
  </marker>
  <marker id="arrow-red" markerWidth="7" markerHeight="7" refX="6.2" refY="3.5" orient="auto" markerUnits="strokeWidth">
    <path d="M0,0 L7,3.5 L0,7 z" fill="#ef4444"/>
  </marker>
</defs>"""


def _background(width: int, height: int) -> str:
    return f'<rect width="{width}" height="{height}" fill="#06121d"/>'


def _header(model: EamModel, width: int) -> str:
    return _coverage_bar(model, width)


def _coverage_bar(model: EamModel, width: int) -> str:
    score = max(0, min(100, model.coverage.score))
    bar_w = min(880, width - 520)
    x = (width - bar_w) / 2
    y = 118
    fill = "#ef4444" if score < 33 else "#f59e0b" if score < 66 else "#46f2b6"
    progress = bar_w * score / 100
    return f"""<g filter="url(#eam-card-glow)">
  <text x="{width / 2:.1f}" y="{y - 38}" text-anchor="middle" fill="#f8fafc" font-family="Inter, Arial, sans-serif" font-size="22" font-weight="900">EAM Coverage</text>
  <text x="{width / 2:.1f}" y="{y - 12}" text-anchor="middle" fill="{fill}" font-family="Inter, Arial, sans-serif" font-size="28" font-weight="900">{score}%</text>
  <rect x="{x:.1f}" y="{y}" width="{bar_w:.1f}" height="18" rx="9" fill="#12283a" stroke="#37516a"/>
  <rect x="{x:.1f}" y="{y}" width="{progress:.1f}" height="18" rx="9" fill="{fill}"/>
  <line x1="{x + (bar_w * 0.33):.1f}" y1="{y - 7}" x2="{x + (bar_w * 0.33):.1f}" y2="{y + 25}" stroke="#6f8298" stroke-width="1.2" opacity="0.8"/>
  <line x1="{x + (bar_w * 0.66):.1f}" y1="{y - 7}" x2="{x + (bar_w * 0.66):.1f}" y2="{y + 25}" stroke="#6f8298" stroke-width="1.2" opacity="0.8"/>
  <text x="{x:.1f}" y="{y + 48}" fill="#ef4444" font-family="Inter, Arial, sans-serif" font-size="12" font-weight="900">0-32 red</text>
  <text x="{x + (bar_w / 2):.1f}" y="{y + 48}" text-anchor="middle" fill="#f59e0b" font-family="Inter, Arial, sans-serif" font-size="12" font-weight="900">33-65 amber</text>
  <text x="{x + bar_w:.1f}" y="{y + 48}" text-anchor="end" fill="#46f2b6" font-family="Inter, Arial, sans-serif" font-size="12" font-weight="900">66+ green</text>
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
            f'font-family="Inter, Arial, sans-serif" font-size="13" font-weight="900">{escape(stage.label.upper())}</text>'
        )
    return rows


def _row_headers(model: EamModel, row_tops: list[int], row_heights: list[int]) -> list[str]:
    rows = []
    coverage_by_domain = {domain.domain_id: domain for domain in model.coverage.domains}
    for index, domain in enumerate(model.domains):
        y = row_tops[index]
        row_h = row_heights[index]
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


def _cells(model: EamModel, left: int, row_tops: list[int], row_heights: list[int], col_w: int) -> list[str]:
    rows = []
    for domain_index, domain in enumerate(model.domains):
        for stage_index, stage in enumerate(model.lifecycle_stages):
            x = left + (stage_index * col_w)
            y = row_tops[domain_index]
            row_h = row_heights[domain_index]
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


def _row_heights(model: EamModel, col_w: int, cell_pad: int, expanded_node_ids: set[str]) -> list[int]:
    heights: list[int] = []
    node_by_id = {node.id: node for node in model.nodes}
    card_w = col_w - 42
    for domain in model.domains:
        required = _ROW_HEADER_MIN_H
        for stage in model.lifecycle_stages:
            cell = next(item for item in model.cells if item.domain_id == domain.id and item.lifecycle_id == stage.id)
            visible_node_ids = [node_id for node_id in cell.node_ids[:3] if node_id in node_by_id]
            if not visible_node_ids:
                continue
            stack_h = cell_pad * 2
            stack_h += sum(_card_height(node_by_id[node_id], card_w, node_id in expanded_node_ids) for node_id in visible_node_ids)
            stack_h += _CARD_GAP * (len(visible_node_ids) - 1)
            if len(cell.node_ids) > 3:
                stack_h += 22
            required = max(required, int(stack_h + 0.5))
        heights.append(required)
    return heights


def _row_tops(top: int, row_heights: list[int]) -> list[int]:
    tops: list[int] = []
    cursor = top
    for height in row_heights:
        tops.append(cursor)
        cursor += height
    return tops


def _node_positions(
    model: EamModel,
    left: int,
    row_tops: list[int],
    col_w: int,
    cell_pad: int,
    expanded_node_ids: set[str],
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
            current_y = row_tops[domain_index] + cell_pad
            for stack_index, node_id in enumerate(visible_node_ids):
                x = left + (stage_index * col_w) + cell_pad
                node_h = _card_height(node_by_id[node_id], col_w - 42, node_id in expanded_node_ids)
                y = current_y
                positions[node_id] = (x, y, col_w - 42, node_h)
                current_y += node_h + _CARD_GAP
    return positions


def _nodes(
    model: EamModel,
    positions: dict[str, tuple[float, float, float, float]],
    expanded_node_ids: set[str],
) -> list[str]:
    rows = []
    node_by_id = {node.id: node for node in model.nodes}
    for cell in model.cells:
        hidden = max(0, len(cell.node_ids) - 3)
        for node_id in cell.node_ids[:3]:
            node = node_by_id[node_id]
            x, y, w, h = positions[node.id]
            colour = _BAND_COLOURS[node.confidence_band]
            expanded = node.id in expanded_node_ids
            title_font = 16 if expanded else 17
            line_h = title_font + 4
            chip_h = 20
            chip_font = 10
            title_y = y + title_font + 10
            chip_y = y + h - chip_h - 12
            chip_gap = 6
            chip_w = (w - 22 - (chip_gap * 2)) / 3
            code = _node_code(node)
            clip_id = f"eam-card-clip-{hashlib.sha1(node.id.encode('utf-8')).hexdigest()[:12]}"
            content_x = x + 11
            content_w = w - 22
            label_lines = _wrap_text_to_width(node.name, content_w, title_font - 1, 8)
            filter_id = "eam-card-glow" if node.confidence_band == "green" else "eam-amber-glow" if node.confidence_band == "amber" else "eam-red-glow"
            rows.extend(
                [
                    f'<g data-node-id="{escape(node.id)}" class="eam-node-card eam-node-card--{"expanded" if expanded else "collapsed"}" filter="url(#{filter_id})">',
                    _node_title(node),
                    f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="8" fill="#071421" stroke="{colour}" stroke-width="1.9"/>',
                    f'<clipPath id="{clip_id}"><rect x="{content_x:.1f}" y="{y + 8:.1f}" width="{content_w:.1f}" height="{h - 16:.1f}" rx="5"/></clipPath>',
                    f'<g clip-path="url(#{clip_id})">',
                ]
            )
            if expanded:
                rows.extend(
                    [
                        f'<text x="{content_x:.1f}" y="{title_y:.1f}" fill="#f8fafc" font-family="Inter, Arial, sans-serif" font-size="{title_font}" font-weight="900">{escape(code)}</text>',
                        *_node_label_lines(content_x, title_y + line_h, line_h, title_font - 1, label_lines),
                        *_metric_chips(
                            content_x,
                            chip_y,
                            chip_w,
                            chip_h,
                            chip_gap,
                            chip_font,
                            [f"{node.role_count} Roles", f"{node.system_count} Systems", f"{node.control_count} Controls"],
                        ),
                    ]
                )
            else:
                rows.append(
                    f'<text x="{x + (w / 2):.1f}" y="{y + (h / 2) + 6:.1f}" text-anchor="middle" fill="#f8fafc" '
                    f'font-family="Inter, Arial, sans-serif" font-size="{title_font}" font-weight="900">{escape(code)}</text>'
                )
            rows.extend(["</g>", "</g>"])
        if hidden:
            last_visible_id = cell.node_ids[min(2, len(cell.node_ids) - 1)]
            x, y, w, h = positions[last_visible_id]
            rows.append(
                f'<text x="{x + w - 4:.1f}" y="{y + h + 18:.1f}" text-anchor="end" fill="#9fb1c5" '
                f'font-family="Inter, Arial, sans-serif" font-size="11" font-weight="800">+{hidden} more</text>'
            )
    return rows


def _edges(model: EamModel, positions: dict[str, tuple[float, float, float, float]]) -> list[str]:
    rows = []
    edge_count_by_node: dict[str, int] = {}
    edge_label_count = 0
    for edge in model.edges:
        if edge.from_node_id not in positions or edge.to_node_id not in positions:
            continue
        if edge_count_by_node.get(edge.from_node_id, 0) >= 4 or edge_count_by_node.get(edge.to_node_id, 0) >= 4:
            continue
        from_count = edge_count_by_node.get(edge.from_node_id, 0)
        to_count = edge_count_by_node.get(edge.to_node_id, 0)
        edge_count_by_node[edge.from_node_id] = from_count + 1
        edge_count_by_node[edge.to_node_id] = to_count + 1
        route = _edge_route(positions[edge.from_node_id], positions[edge.to_node_id], max(from_count, to_count), edge.edge_type)
        colour = "#60a5fa" if edge.edge_type == "system" else "#fb923c" if edge.edge_type == "control" else "#46f2b6"
        dash = ' stroke-dasharray="9 7"' if edge.edge_type == "system" else ""
        marker = "arrow-cyan" if edge.edge_type == "system" else "arrow-orange"
        filter_id = "eam-edge-glow" if edge.edge_type == "system" else "eam-control-glow"
        rows.append(
            f'<path data-edge-id="{escape(edge.id)}" class="eam-routed-edge eam-routed-edge--{escape(edge.edge_type)}" '
            f'd="{route.path}" fill="none" stroke="{colour}" stroke-width="3.1" stroke-linecap="round" '
            f'stroke-linejoin="round" opacity="0.82" marker-end="url(#{marker})" filter="url(#{filter_id})"{dash}/>'
        )
        if route.label and edge_label_count < 8:
            edge_label_count += 1
            rows.append(
                f'<text class="eam-edge-label" x="{route.label_x:.1f}" y="{route.label_y:.1f}" text-anchor="middle" '
                f'fill="{colour}" font-family="Inter, Arial, sans-serif" font-size="10" font-weight="900">'
                f"{escape(route.label)}</text>"
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
        path, label_x, label_y = _clash_route(positions[left], positions[right])
        rows.append(
            f'<path data-finding-id="{escape(finding.id)}" class="eam-clash-trace" d="{path}" fill="none" stroke="#ef4444" stroke-width="3.8" '
            f'stroke-linecap="round" opacity="0.94" marker-end="url(#arrow-red)" filter="url(#eam-red-glow)"/>'
        )
        rows.append(
            f'<text x="{label_x:.1f}" y="{label_y:.1f}" fill="#ff5c5c" '
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


def _edge_route(
    from_box: tuple[float, float, float, float],
    to_box: tuple[float, float, float, float],
    route_index: int,
    edge_type: str,
) -> _EdgeRoute:
    from_x, from_y = _centre(from_box)
    to_x, to_y = _centre(to_box)
    offset = ((route_index % 4) - 1.5) * 8
    label = "Shared Systems" if edge_type == "system" else "Shared Controls" if edge_type == "control" else "Dependency"

    if abs(to_x - from_x) >= abs(to_y - from_y):
        if to_x >= from_x:
            sx, sy = _port(from_box, "right", offset)
            ex, ey = _port(to_box, "left", -offset)
        else:
            sx, sy = _port(from_box, "left", offset)
            ex, ey = _port(to_box, "right", -offset)
        elbow_x = (sx + ex) / 2
        path = f"M{sx:.1f},{sy:.1f} H{elbow_x:.1f} V{ey:.1f} H{ex:.1f}"
        label_x = elbow_x
        label_y = min(sy, ey) - 8 if abs(sy - ey) < 18 else ((sy + ey) / 2) - 8
    else:
        if to_y >= from_y:
            sx, sy = _port(from_box, "bottom", offset)
            ex, ey = _port(to_box, "top", -offset)
        else:
            sx, sy = _port(from_box, "top", offset)
            ex, ey = _port(to_box, "bottom", -offset)
        elbow_y = (sy + ey) / 2
        path = f"M{sx:.1f},{sy:.1f} V{elbow_y:.1f} H{ex:.1f} V{ey:.1f}"
        label_x = (sx + ex) / 2
        label_y = elbow_y - 8

    if abs(to_x - from_x) + abs(to_y - from_y) < 210:
        label = ""
    return _EdgeRoute(path=path, label_x=label_x, label_y=label_y, label=label)


def _clash_route(
    from_box: tuple[float, float, float, float],
    to_box: tuple[float, float, float, float],
) -> tuple[str, float, float]:
    from_x, from_y = _centre(from_box)
    to_x, to_y = _centre(to_box)
    if abs(to_x - from_x) >= abs(to_y - from_y):
        if to_x >= from_x:
            sx, sy = _port(from_box, "right", 0)
            ex, ey = _port(to_box, "left", 0)
        else:
            sx, sy = _port(from_box, "left", 0)
            ex, ey = _port(to_box, "right", 0)
        mid_x = (sx + ex) / 2
        points = [
            (sx, sy),
            (mid_x - 18, sy),
            (mid_x - 10, sy - 12),
            (mid_x - 2, sy + 12),
            (mid_x + 6, sy - 12),
            (mid_x + 14, sy + 12),
            (mid_x + 22, ey),
            (ex, ey),
        ]
        label_x = mid_x + 28
        label_y = min(sy, ey) - 12
    else:
        if to_y >= from_y:
            sx, sy = _port(from_box, "bottom", 0)
            ex, ey = _port(to_box, "top", 0)
        else:
            sx, sy = _port(from_box, "top", 0)
            ex, ey = _port(to_box, "bottom", 0)
        mid_y = (sy + ey) / 2
        points = [
            (sx, sy),
            (sx, mid_y - 18),
            (sx - 12, mid_y - 10),
            (sx + 12, mid_y - 2),
            (sx - 12, mid_y + 6),
            (sx + 12, mid_y + 14),
            (ex, mid_y + 22),
            (ex, ey),
        ]
        label_x = max(sx, ex) + 16
        label_y = mid_y - 12
    path = " ".join(("M" if index == 0 else "L") + f"{x:.1f},{y:.1f}" for index, (x, y) in enumerate(points))
    return path, label_x, label_y


def _port(box: tuple[float, float, float, float], side: str, offset: float) -> tuple[float, float]:
    x, y, w, h = box
    if side == "left":
        return x, y + (h / 2) + offset
    if side == "right":
        return x + w, y + (h / 2) + offset
    if side == "top":
        return x + (w / 2) + offset, y
    return x + (w / 2) + offset, y + h


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


def _card_height(node: EamNode, width: float, expanded: bool) -> float:
    if not expanded:
        return _COLLAPSED_CARD_H
    content_w = width - 22
    title_font = 16
    line_h = title_font + 4
    label_lines = _wrap_text_to_width(node.name, content_w, title_font - 1, 8)
    return 18 + 22 + 8 + (len(label_lines) * line_h) + 14 + 20 + 14


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


def _wrap_text_to_width(value: str, width: float, font_size: float, max_lines: int) -> list[str]:
    words = value.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if not current or _estimated_text_width(candidate, font_size) <= width:
            current = candidate
            continue
        lines.append(current)
        current = word
        if len(lines) == max_lines - 1:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    return lines[:max_lines]


def _estimated_text_width(value: str, font_size: float) -> float:
    width = 0.0
    for char in value:
        if char.isspace():
            factor = 0.32
        elif char in "ilI.,:;|!'":
            factor = 0.3
        elif char in "mwMW@#%&":
            factor = 0.82
        elif char.isupper():
            factor = 0.64
        else:
            factor = 0.56
        width += font_size * factor
    return width


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
