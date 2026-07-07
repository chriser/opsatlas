"""Server-side Digital System Landscape SVG renderer for the Enterprise Activity Model."""
# ruff: noqa: E501

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from html import escape

from .model import EamModel, EamNode, EntityRollup


@dataclass(frozen=True)
class SystemLayer:
    id: str
    label: str
    keywords: tuple[str, ...]


@dataclass(frozen=True)
class LandscapeRow:
    node: EamNode
    cells: dict[str, list[str]]
    height: int


SYSTEM_LAYERS: tuple[SystemLayer, ...] = (
    SystemLayer("payments-forecourt", "Payments & Forecourt", ("payment", "forecourt", "terminal", "taas", "fuel", "wet-stock")),
    SystemLayer("sales-execution", "Sales Execution", ("point of sale", "point-of-sale", "pos", "retail selling", "sellable", "sales", "price", "pricing", "promotion", "discount")),
    SystemLayer("store-operations", "Store Operations", ("store", "site", "warehouse", "depot", "logistics", "retail consumer", "communication")),
    SystemLayer("central-store-admin", "Central Store Administration", ("operational master", "master data", "site master", "supplier header", "item master", "article setup", "article-list", "user profile", "authorisation")),
    SystemLayer("store-inventory", "Store Inventory Management", ("stock", "inventory", "warehouse", "depot", "logistics-unit", "logistics unit")),
    SystemLayer("convenience-head-office", "Convenience Head Office", ("head office", "commercial contract", "service contract", "supplier", "contract", "compliance", "legal", "governance", "due diligence", "business communication", "brand")),
    SystemLayer("invoice-matching", "Invoice Matching", ("grir", "invoice", "reconciliation", "matching")),
    SystemLayer("finance", "Finance", ("finance", "payment contract", "accounting", "tax")),
    SystemLayer("forecasting-replenishment", "Forecasting & Replenishment", ("forecast", "replenish", "replenishment", "planning", "schedule")),
    SystemLayer("ranging-category", "Ranging & Category Management", ("ranging", "assortment", "category", "merchandise", "hierarchy", "article-list", "list", "promotion", "discount")),
    SystemLayer("data-analytics", "Data & Analytics", ("analytics", "business intelligence", "bi", "reporting", "dashboard", "data")),
    SystemLayer("integration-reports", "Integration & Operational Reports", ("integration", "reporting extraction", "downstream", "mapping", "cross-reference", "interface", "operational report", "release", "testing")),
)

LAYER_BY_ID = {layer.id: layer for layer in SYSTEM_LAYERS}
LEFT_W = 260
TOP = 168
COL_W = 184
ROW_GAP = 8
HEADER_H = 74
MIN_ROW_H = 96


def render_system_landscape_svg(model: EamModel, selected_node_id: str | None = None) -> str:
    """Render processes against digital system layers with selectable flow highlighting."""

    rows = _landscape_rows(model)
    if selected_node_id not in {row.node.id for row in rows}:
        selected_node_id = rows[0].node.id if rows else None
    row_tops = _row_tops(rows)
    width = LEFT_W + (len(SYSTEM_LAYERS) * COL_W) + 42
    grid_h = sum(row.height for row in rows) + (ROW_GAP * max(0, len(rows) - 1))
    height = TOP + HEADER_H + grid_h + 110
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" '
        'aria-label="Digital System Landscape">',
        _defs(),
        f'<rect width="{width}" height="{height}" fill="#06121d"/>',
        _header(model, width, selected_node_id, rows),
        *_column_headers(),
        *_rows(rows, row_tops, selected_node_id),
        *_selected_flow(rows, row_tops, selected_node_id),
        _legend(width, height),
        "</svg>",
    ]
    return "\n".join(parts)


def _defs() -> str:
    return """<defs>
  <filter id="eam-landscape-glow" x="-30%" y="-30%" width="160%" height="180%">
    <feDropShadow dx="0" dy="0" stdDeviation="4" flood-color="#46f2b6" flood-opacity="0.28"/>
    <feDropShadow dx="0" dy="8" stdDeviation="8" flood-color="#020617" flood-opacity="0.42"/>
  </filter>
  <marker id="landscape-flow-arrow" markerWidth="4" markerHeight="4" refX="3.6" refY="2" orient="auto" markerUnits="strokeWidth">
    <path d="M0,0 L4,2 L0,4 z" fill="#46f2b6"/>
  </marker>
</defs>"""


def _header(model: EamModel, width: int, selected_node_id: str | None, rows: list[LandscapeRow]) -> str:
    selected = next((row.node.name for row in rows if row.node.id == selected_node_id), "Select a process row")
    return f"""<rect x="24" y="24" width="{width - 48}" height="106" rx="18" fill="#081928" stroke="#2d4055"/>
<text x="52" y="61" fill="#f8fafc" font-family="Inter, Arial, sans-serif" font-size="28" font-weight="900">Digital System Landscape</text>
<text x="52" y="91" fill="#cbd5e1" font-family="Inter, Arial, sans-serif" font-size="14">Processes are projected across system-layer columns from process_uses_system ontology links.</text>
<text x="{width - 52}" y="62" text-anchor="end" fill="#46f2b6" font-family="Inter, Arial, sans-serif" font-size="15" font-weight="900">Selected flow</text>
<text x="{width - 52}" y="90" text-anchor="end" fill="#cbd5e1" font-family="Inter, Arial, sans-serif" font-size="13">{escape(selected)}</text>
<text x="{width - 52}" y="115" text-anchor="end" fill="#94a3b8" font-family="Inter, Arial, sans-serif" font-size="12">{model.process_count} processes / {len(model.entity_rollups.get('systems', []))} systems</text>"""


def _column_headers() -> list[str]:
    rows = [
        f'<rect x="24" y="{TOP}" width="{LEFT_W - 36}" height="{HEADER_H - 10}" rx="10" fill="#0b1d2b" stroke="#42576b"/>',
        f'<text x="48" y="{TOP + 37}" fill="#f8fafc" font-family="Inter, Arial, sans-serif" font-size="13" font-weight="900">PROCESS</text>',
    ]
    for index, layer in enumerate(SYSTEM_LAYERS):
        x = LEFT_W + (index * COL_W)
        rows.append(f'<rect x="{x}" y="{TOP}" width="{COL_W - 8}" height="{HEADER_H - 10}" rx="10" fill="#0b1d2b" stroke="#42576b"/>')
        for line_index, line in enumerate(_wrap_text_to_width(layer.label.upper(), COL_W - 24, 11, 3)):
            rows.append(
                f'<text x="{x + (COL_W / 2) - 4:.1f}" y="{TOP + 24 + (line_index * 14)}" text-anchor="middle" '
                f'fill="#f8fafc" font-family="Inter, Arial, sans-serif" font-size="11" font-weight="900">{escape(line)}</text>'
            )
    return rows


def _rows(rows: list[LandscapeRow], row_tops: list[int], selected_node_id: str | None) -> list[str]:
    output: list[str] = []
    for row, y in zip(rows, row_tops, strict=True):
        selected = row.node.id == selected_node_id
        stroke = "#46f2b6" if selected else "#42576b"
        fill = "#0c2333" if selected else "#081928"
        output.append(
            f'<g data-landscape-process-id="{escape(row.node.id)}">'
            f'<rect x="24" y="{y}" width="{LEFT_W - 36}" height="{row.height}" rx="12" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
        )
        code = _node_code(row.node)
        output.append(f'<text x="44" y="{y + 24}" fill="#46f2b6" font-family="Inter, Arial, sans-serif" font-size="12" font-weight="900">{escape(code)}</text>')
        for line_index, line in enumerate(_wrap_text_to_width(row.node.name, LEFT_W - 66, 12, 3)):
            output.append(
                f'<text x="44" y="{y + 45 + (line_index * 15)}" fill="#f8fafc" font-family="Inter, Arial, sans-serif" '
                f'font-size="12" font-weight="850">{escape(line)}</text>'
            )
        output.append(
            f'<text x="44" y="{y + row.height - 16}" fill="#94a3b8" font-family="Inter, Arial, sans-serif" font-size="11" font-weight="800">'
            f'{escape(row.node.domain_label)} / {escape(row.node.lifecycle_label)}</text>'
        )
        for index, layer in enumerate(SYSTEM_LAYERS):
            x = LEFT_W + (index * COL_W)
            output.extend(_cell(layer, x, y, row.height, row.cells.get(layer.id, []), selected))
        output.append("</g>")
    return output


def _cell(layer: SystemLayer, x: int, y: int, row_h: int, systems: list[str], selected: bool) -> list[str]:
    populated = bool(systems)
    fill = "#0d2b3b" if populated and selected else "#0a1b2a" if populated else "#071421"
    stroke = "#46f2b6" if populated and selected else "#2d4055" if populated else "#1f3447"
    rows = [
        f'<rect data-landscape-layer-id="{escape(layer.id)}" x="{x}" y="{y}" width="{COL_W - 8}" height="{row_h}" rx="12" '
        f'fill="{fill}" stroke="{stroke}" opacity="0.96"/>'
    ]
    if not systems:
        return rows
    cursor = y + 22
    visible = systems[:3]
    for system_name in visible:
        for line in _wrap_text_to_width(system_name, COL_W - 26, 10, 2):
            rows.append(
                f'<text x="{x + 12}" y="{cursor}" fill="#dbeafe" font-family="Inter, Arial, sans-serif" '
                f'font-size="10" font-weight="800">{escape(line)}</text>'
            )
            cursor += 12
        cursor += 5
    if len(systems) > len(visible):
        rows.append(
            f'<text x="{x + 12}" y="{row_h + y - 14}" fill="#f9a8d4" font-family="Inter, Arial, sans-serif" '
            f'font-size="10" font-weight="900">+{len(systems) - len(visible)} more</text>'
        )
    return rows


def _selected_flow(rows: list[LandscapeRow], row_tops: list[int], selected_node_id: str | None) -> list[str]:
    if not selected_node_id:
        return []
    selected_pair = next(((row, y) for row, y in zip(rows, row_tops, strict=True) if row.node.id == selected_node_id), None)
    if not selected_pair:
        return []
    row, y = selected_pair
    centres: list[tuple[float, float]] = []
    for index, layer in enumerate(SYSTEM_LAYERS):
        if row.cells.get(layer.id):
            centres.append((LEFT_W + (index * COL_W) + ((COL_W - 8) / 2), y + (row.height / 2)))
    output: list[str] = []
    for start, end in zip(centres, centres[1:], strict=False):
        sx, sy = start
        ex, ey = end
        mid_x = (sx + ex) / 2
        path = f"M{sx:.1f},{sy:.1f} H{mid_x:.1f} V{ey:.1f} H{ex:.1f}"
        output.append(
            f'<path class="eam-landscape-flow" d="{path}" fill="none" stroke="#46f2b6" stroke-width="3" stroke-linecap="round" '
            'stroke-dasharray="14 10" stroke-dashoffset="24" marker-end="url(#landscape-flow-arrow)" filter="url(#eam-landscape-glow)">'
            '<animate attributeName="stroke-dashoffset" from="24" to="0" dur="1.1s" repeatCount="indefinite"/>'
            '</path>'
        )
    return output


def _legend(width: int, height: int) -> str:
    y = height - 70
    return f"""<g>
  <rect x="24" y="{y}" width="{width - 48}" height="46" rx="13" fill="#081928" stroke="#2d4055"/>
  <rect x="48" y="{y + 16}" width="28" height="14" rx="5" fill="#0d2b3b" stroke="#46f2b6"/>
  <text x="88" y="{y + 28}" fill="#cbd5e1" font-family="Inter, Arial, sans-serif" font-size="12">selected process system evidence</text>
  <line x1="330" y1="{y + 23}" x2="390" y2="{y + 23}" stroke="#46f2b6" stroke-width="3" stroke-dasharray="14 10" marker-end="url(#landscape-flow-arrow)"/>
  <text x="405" y="{y + 28}" fill="#cbd5e1" font-family="Inter, Arial, sans-serif" font-size="12">animated left-to-right flow follows populated layers only</text>
  <text x="{width - 52}" y="{y + 28}" text-anchor="end" fill="#94a3b8" font-family="Inter, Arial, sans-serif" font-size="12">Classification is deterministic from system names plus process context.</text>
</g>"""


def _landscape_rows(model: EamModel) -> list[LandscapeRow]:
    systems_by_process = _systems_by_process(model.entity_rollups.get("systems", []))
    rows: list[LandscapeRow] = []
    for node in model.nodes:
        cells: dict[str, list[str]] = {layer.id: [] for layer in SYSTEM_LAYERS}
        for system in systems_by_process.get(node.id, []):
            for layer_id in _layers_for_system(system.name, node):
                cells[layer_id].append(system.name)
        cells = {layer_id: sorted(set(names), key=str.lower) for layer_id, names in cells.items()}
        rows.append(LandscapeRow(node=node, cells=cells, height=_row_height(node, cells)))
    return rows


def _systems_by_process(systems: list[EntityRollup]) -> dict[str, list[EntityRollup]]:
    output: dict[str, list[EntityRollup]] = {}
    for system in systems:
        for process_id in system.linked_process_ids:
            output.setdefault(process_id, []).append(system)
    for process_id in output:
        output[process_id].sort(key=lambda item: item.name.lower())
    return output


def _layers_for_system(system_name: str, node: EamNode) -> list[str]:
    system_text = _normalise(system_name)
    process_text = _normalise(" ".join((node.name, node.domain_label, node.lifecycle_label, *node.matched_domain_keywords, *node.matched_lifecycle_keywords)))
    combined = f"{system_text} {process_text}"
    layer_ids: list[str] = []
    if any(term in system_text for term in ("point of sale", "point-of-sale", "pos", "retail consumer", "retail selling")):
        layer_ids.extend(["sales-execution", "store-operations", "central-store-admin"])
    for layer in SYSTEM_LAYERS:
        if any(keyword in system_text for keyword in layer.keywords):
            layer_ids.append(layer.id)
    if not layer_ids:
        for layer in SYSTEM_LAYERS:
            if any(keyword in combined for keyword in layer.keywords):
                layer_ids.append(layer.id)
    if not layer_ids:
        layer_ids.append("integration-reports")
    return _dedupe(layer_ids)[:3]


def _row_height(node: EamNode, cells: dict[str, list[str]]) -> int:
    process_lines = len(_wrap_text_to_width(node.name, LEFT_W - 66, 12, 3))
    max_cell_lines = 0
    for names in cells.values():
        line_count = 0
        for name in names[:3]:
            line_count += len(_wrap_text_to_width(name, COL_W - 26, 10, 2)) + 1
        if len(names) > 3:
            line_count += 1
        max_cell_lines = max(max_cell_lines, line_count)
    return max(MIN_ROW_H, 30 + (max(process_lines, max_cell_lines) * 13) + 24)


def _row_tops(rows: list[LandscapeRow]) -> list[int]:
    tops: list[int] = []
    cursor = TOP + HEADER_H
    for row in rows:
        tops.append(cursor)
        cursor += row.height + ROW_GAP
    return tops


def _node_code(node: EamNode) -> str:
    prefix = "SYS"
    if node.domain_id:
        prefix = "".join(part[:1] for part in node.domain_id.split("-")[:3]).upper() or "SYS"
    digest = hashlib.sha1(node.id.encode("utf-8")).hexdigest()
    return f"{prefix}-{(int(digest[:6], 16) % 900) + 100}"


def _normalise(value: str) -> str:
    return value.lower().replace("\u2013", "-").replace("\u2014", "-")


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value in seen or value not in LAYER_BY_ID:
            continue
        seen.add(value)
        output.append(value)
    return output


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
