"""Server-side Digital System Landscape SVG renderer for the Enterprise Activity Model."""
# ruff: noqa: E501

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from functools import lru_cache
from html import escape
from pathlib import Path

from .model import EamModel, EamNode


@dataclass(frozen=True)
class SystemLayer:
    id: str
    label: str
    keywords: tuple[str, ...]
    icon_file: str


@dataclass(frozen=True)
class LandscapeProcessRow:
    node: EamNode
    system_keys: tuple[str, ...]


@dataclass(frozen=True)
class LandscapeSystemNode:
    key: str
    name: str
    layer_ids: tuple[str, ...]
    process_ids: tuple[str, ...]


@dataclass(frozen=True)
class LandscapeSystemSegment:
    layer_ids: tuple[str, ...]
    x: float
    y: float
    width: float
    height: float


SYSTEM_LAYERS: tuple[SystemLayer, ...] = (
    SystemLayer("payments-forecourt", "Payments & Forecourt", ("payment", "forecourt", "terminal", "taas", "fuel", "wet-stock"), "payment.png"),
    SystemLayer("sales-execution", "Sales Execution", ("point of sale", "point-of-sale", "pos", "retail selling", "sellable", "sales", "price", "pricing", "promotion", "discount"), "sales.png"),
    SystemLayer("store-operations", "Store Operations", ("store", "site", "warehouse", "depot", "logistics", "retail consumer", "communication"), "store.png"),
    SystemLayer("central-store-admin", "Central Store Administration", ("operational master", "master data", "site master", "supplier header", "item master", "article setup", "article-list", "user profile", "authorisation"), "administration.png"),
    SystemLayer("store-inventory", "Store Inventory Management", ("stock", "inventory", "warehouse", "depot", "logistics-unit", "logistics unit"), "inventory.png"),
    SystemLayer("convenience-head-office", "Convenience Head Office", ("head office", "commercial contract", "service contract", "supplier", "contract", "compliance", "legal", "governance", "due diligence", "business communication", "brand"), "headoffice.png"),
    SystemLayer("invoice-matching", "Invoice Matching", ("grir", "invoice", "reconciliation", "matching"), "invoices.png"),
    SystemLayer("finance", "Finance", ("finance", "payment contract", "accounting", "tax"), "finance.png"),
    SystemLayer("forecasting-replenishment", "Forecasting & Replenishment", ("forecast", "replenish", "replenishment", "planning", "schedule"), "forecasting.png"),
    SystemLayer("ranging-category", "Ranging & Category Management", ("ranging", "assortment", "category", "merchandise", "hierarchy", "article-list", "list", "promotion", "discount"), "ranging.png"),
    SystemLayer("data-analytics", "Data & Analytics", ("analytics", "business intelligence", "bi", "reporting", "dashboard", "data"), "data.png"),
    SystemLayer("integration-reports", "Integration & Operational Reports", ("integration", "reporting extraction", "downstream", "mapping", "cross-reference", "interface", "operational report", "release", "testing"), "integration.png"),
)

LAYER_BY_ID = {layer.id: layer for layer in SYSTEM_LAYERS}
SYSTEM_LAYER_INDEX = {layer.id: index for index, layer in enumerate(SYSTEM_LAYERS)}
LEFT_W = 320
LAYER_LABEL_W = 252
TOP = 168
SYSTEM_COL_W = 198
SYSTEM_NODE_W = 174
HEADER_H = 112
PROCESS_ROW_H = 68
ROW_GAP = 8
LAYER_ROW_H = 118
LAYER_ROW_GAP = 10
SYSTEM_NODE_PAD_Y = 18
CANVAS_TOP = TOP + HEADER_H + 18
MIN_CANVAS_H = 320
SYSTEM_X = LEFT_W + LAYER_LABEL_W


def render_system_landscape_svg(
    model: EamModel,
    selected_node_id: str | None = None,
    show_all_connections: bool = False,
) -> str:
    """Render canonical systems once across digital layers, with process-selected data flow."""

    systems = _landscape_systems(model)
    process_rows = _landscape_process_rows(model, systems)
    if selected_node_id not in {row.node.id for row in process_rows}:
        selected_node_id = None
    visible_systems = _visible_systems(systems, selected_node_id, show_all_connections)
    layout_systems = _ordered_systems_for_layout(visible_systems, process_rows, selected_node_id)
    system_positions = _system_positions(layout_systems)
    process_tops = _process_tops(process_rows)
    system_area_w = max(3, len(layout_systems)) * SYSTEM_COL_W
    grid_h = max(_process_list_height(process_rows), _layer_canvas_height(), MIN_CANVAS_H)
    width = SYSTEM_X + system_area_w + 42
    height = CANVAS_TOP + grid_h + 96

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="Digital System Landscape">',
        _defs(),
        f'<rect width="{width}" height="{height}" fill="#06121d"/>',
        _header(model, width, selected_node_id, process_rows, visible_systems, show_all_connections),
        *_column_headers(system_area_w),
        *_layer_bands(system_area_w),
        *_process_selector(process_rows, process_tops, selected_node_id),
        *_system_nodes(visible_systems, system_positions, selected_node_id, show_all_connections),
        *_connection_paths(process_rows, systems, system_positions, selected_node_id, show_all_connections),
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
  <filter id="eam-landscape-packet-glow" x="-50%" y="-50%" width="200%" height="200%">
    <feDropShadow dx="0" dy="0" stdDeviation="4" flood-color="#f72585" flood-opacity="0.58"/>
  </filter>
  <marker id="landscape-flow-arrow" markerWidth="4" markerHeight="4" refX="3.6" refY="2" orient="auto" markerUnits="strokeWidth">
    <path d="M0,0 L4,2 L0,4 z" fill="#46f2b6"/>
  </marker>
</defs>"""


def _header(
    model: EamModel,
    width: int,
    selected_node_id: str | None,
    process_rows: list[LandscapeProcessRow],
    visible_systems: list[LandscapeSystemNode],
    show_all_connections: bool,
) -> str:
    selected = next((row.node.name for row in process_rows if row.node.id == selected_node_id), "Select a process row")
    connection_mode = "All flows visible" if show_all_connections else "Context flow only"
    return f"""<rect x="24" y="24" width="{width - 48}" height="106" rx="18" fill="#081928" stroke="#2d4055"/>
<text x="52" y="61" fill="#f8fafc" font-family="Inter, Arial, sans-serif" font-size="28" font-weight="900">Digital System Landscape</text>
<text x="52" y="91" fill="#cbd5e1" font-family="Inter, Arial, sans-serif" font-size="14">System layers run vertically. Selecting a process shows participating systems left-to-right with a sequenced data packet.</text>
<text x="{width - 52}" y="62" text-anchor="end" fill="#46f2b6" font-family="Inter, Arial, sans-serif" font-size="15" font-weight="900">{escape(connection_mode)}</text>
<text x="{width - 52}" y="90" text-anchor="end" fill="#cbd5e1" font-family="Inter, Arial, sans-serif" font-size="13">{escape(selected)}</text>
<text x="{width - 52}" y="115" text-anchor="end" fill="#94a3b8" font-family="Inter, Arial, sans-serif" font-size="12">{model.process_count} processes / {len(visible_systems)} visible systems</text>"""


def _column_headers(system_area_w: int) -> list[str]:
    rows = [
        f'<rect x="24" y="{TOP}" width="{LEFT_W - 36}" height="{HEADER_H - 10}" rx="12" fill="#0b1d2b" stroke="#42576b"/>',
        f'<text x="48" y="{TOP + 34}" fill="#f8fafc" font-family="Inter, Arial, sans-serif" font-size="13" font-weight="900">PROCESS SELECTOR</text>',
        f'<text x="48" y="{TOP + 61}" fill="#94a3b8" font-family="Inter, Arial, sans-serif" font-size="11" font-weight="800">Click a row to focus system flow</text>',
        f'<rect x="{LEFT_W}" y="{TOP}" width="{LAYER_LABEL_W - 14}" height="{HEADER_H - 10}" rx="12" fill="#0b1d2b" stroke="#42576b"/>',
        f'<text x="{LEFT_W + 24}" y="{TOP + 34}" fill="#f8fafc" font-family="Inter, Arial, sans-serif" font-size="13" font-weight="900">SYSTEM LAYERS</text>',
        f'<text x="{LEFT_W + 24}" y="{TOP + 61}" fill="#94a3b8" font-family="Inter, Arial, sans-serif" font-size="11" font-weight="800">Vertical operating stack</text>',
        f'<rect x="{SYSTEM_X}" y="{TOP}" width="{system_area_w}" height="{HEADER_H - 10}" rx="12" fill="#0b1d2b" stroke="#42576b"/>',
        f'<text x="{SYSTEM_X + 24}" y="{TOP + 34}" fill="#f8fafc" font-family="Inter, Arial, sans-serif" font-size="13" font-weight="900">SYSTEM FLOW</text>',
        f'<text x="{SYSTEM_X + 24}" y="{TOP + 61}" fill="#94a3b8" font-family="Inter, Arial, sans-serif" font-size="11" font-weight="800">Systems progress left to right for the selected process</text>',
    ]
    return rows


def _layer_bands(system_area_w: int) -> list[str]:
    rows = []
    for index, layer in enumerate(SYSTEM_LAYERS):
        y = CANVAS_TOP + (index * (LAYER_ROW_H + LAYER_ROW_GAP))
        rows.append(
            f'<rect data-landscape-layer-label-id="{escape(layer.id)}" x="{LEFT_W}" y="{y}" width="{LAYER_LABEL_W - 14}" height="{LAYER_ROW_H}" rx="14" '
            'fill="#0b1d2b" stroke="#2d4055" opacity="0.98"/>'
        )
        rows.append(f'<image x="{LEFT_W + 18}" y="{y + 24}" width="58" height="58" preserveAspectRatio="xMidYMid meet" href="{_layer_icon(layer)}"/>')
        for line_index, line in enumerate(_wrap_text_to_width(layer.label.upper(), LAYER_LABEL_W - 108, 12, 3)):
            rows.append(
                f'<text x="{LEFT_W + 88}" y="{y + 43 + (line_index * 15)}" fill="#f8fafc" '
                f'font-family="Inter, Arial, sans-serif" font-size="12" font-weight="900">{escape(line)}</text>'
            )
        rows.append(
            f'<rect data-landscape-layer-id="{escape(layer.id)}" x="{SYSTEM_X}" y="{y}" width="{system_area_w}" height="{LAYER_ROW_H}" rx="14" '
            'fill="#071421" stroke="#1f3447" opacity="0.96"/>'
        )
    return rows


def _process_selector(
    process_rows: list[LandscapeProcessRow],
    process_tops: list[int],
    selected_node_id: str | None,
) -> list[str]:
    rows: list[str] = []
    for row, y in zip(process_rows, process_tops, strict=True):
        selected = row.node.id == selected_node_id
        stroke = "#46f2b6" if selected else "#42576b"
        fill = "#0c2333" if selected else "#081928"
        opacity = 1.0 if selected or not selected_node_id else 0.58
        rows.append(
            f'<g data-landscape-process-id="{escape(row.node.id)}" opacity="{opacity:.2f}">'
            f'<rect x="24" y="{y}" width="{LEFT_W - 36}" height="{PROCESS_ROW_H}" rx="12" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
        )
        code = _node_code(row.node)
        rows.append(f'<text x="44" y="{y + 23}" fill="#46f2b6" font-family="Inter, Arial, sans-serif" font-size="11" font-weight="900">{escape(code)}</text>')
        for line_index, line in enumerate(_wrap_text_to_width(row.node.name, LEFT_W - 72, 12, 2)):
            rows.append(
                f'<text x="44" y="{y + 43 + (line_index * 14)}" fill="#f8fafc" font-family="Inter, Arial, sans-serif" '
                f'font-size="12" font-weight="850">{escape(line)}</text>'
            )
        rows.append(
            f'<text x="{LEFT_W - 38}" y="{y + PROCESS_ROW_H - 16}" text-anchor="end" fill="#94a3b8" '
            f'font-family="Inter, Arial, sans-serif" font-size="10" font-weight="800">{len(row.system_keys)} systems</text></g>'
        )
    return rows


def _system_nodes(
    systems: list[LandscapeSystemNode],
    positions: dict[str, tuple[LandscapeSystemSegment, ...]],
    selected_node_id: str | None,
    show_all_connections: bool,
) -> list[str]:
    rows: list[str] = []
    for system in systems:
        if system.key not in positions:
            continue
        segments = positions[system.key]
        selected_participant = selected_node_id in system.process_ids if selected_node_id else False
        opacity = 1.0 if not selected_node_id or selected_participant or show_all_connections else 0.38
        stroke = "#46f2b6" if selected_participant else "#67e8f9"
        fill = "#083344" if selected_participant else "#0b2536"
        rows.append(
            f'<g data-landscape-system-key="{escape(system.key)}" data-landscape-system-layers="{escape(",".join(system.layer_ids))}" '
            f'opacity="{opacity:.2f}">'
        )
        for segment_index, segment in enumerate(segments):
            rows.append(
                f'<rect data-landscape-system-segment-key="{escape(system.key)}" '
                f'data-landscape-system-segment-layers="{escape(",".join(segment.layer_ids))}" '
                f'x="{segment.x:.1f}" y="{segment.y:.1f}" width="{segment.width:.1f}" height="{segment.height:.1f}" rx="10" '
                f'fill="{fill}" stroke="{stroke}" stroke-width="1.4" filter="url(#eam-landscape-glow)"/>'
            )
            for line_index, line in enumerate(_wrap_text_to_width(system.name, segment.width - 28, 12, 2)):
                rows.append(
                    f'<text x="{segment.x + 14:.1f}" y="{segment.y + 21 + (line_index * 14):.1f}" fill="#dbeafe" '
                    f'font-family="Inter, Arial, sans-serif" font-size="12" font-weight="900">{escape(line)}</text>'
                )
            if segment_index == 0:
                rows.append(
                    f'<text x="{segment.x + segment.width - 12:.1f}" y="{segment.y + segment.height - 12:.1f}" text-anchor="end" fill="#94a3b8" '
                    f'font-family="Inter, Arial, sans-serif" font-size="10" font-weight="800">{len(system.process_ids)} processes / {len(system.layer_ids)} layers</text>'
                )
            else:
                rows.append(
                    f'<text x="{segment.x + segment.width - 12:.1f}" y="{segment.y + segment.height - 12:.1f}" text-anchor="end" fill="#94a3b8" '
                    f'font-family="Inter, Arial, sans-serif" font-size="10" font-weight="800">same system</text>'
                )
        rows.append("</g>")
    if not systems:
        rows.append(
            f'<text x="{LEFT_W + 28}" y="{CANVAS_TOP + 56}" fill="#94a3b8" font-family="Inter, Arial, sans-serif" '
            'font-size="13" font-weight="800">No system evidence is available for the selected process.</text>'
        )
    return rows


def _connection_paths(
    process_rows: list[LandscapeProcessRow],
    systems: list[LandscapeSystemNode],
    positions: dict[str, tuple[LandscapeSystemSegment, ...]],
    selected_node_id: str | None,
    show_all_connections: bool,
) -> list[str]:
    rows: list[str] = []
    if show_all_connections:
        for row in process_rows:
            if row.node.id == selected_node_id:
                continue
            rows.extend(_process_flow(row, systems, positions, selected=False, with_packets=False))
    if selected_node_id:
        selected_row = next((row for row in process_rows if row.node.id == selected_node_id), None)
        if selected_row is not None:
            rows.extend(_process_flow(selected_row, systems, positions, selected=True, with_packets=True))
    return rows


def _process_flow(
    process_row: LandscapeProcessRow,
    systems: list[LandscapeSystemNode],
    positions: dict[str, tuple[LandscapeSystemSegment, ...]],
    *,
    selected: bool,
    with_packets: bool,
) -> list[str]:
    ordered = _ordered_process_systems(process_row, systems, positions)
    if len(ordered) < 2:
        return []
    output: list[str] = []
    full_path_parts: list[str] = []
    payload_label = _flow_payload_label(process_row.node)
    for index, (start, end) in enumerate(zip(ordered, ordered[1:], strict=False)):
        sx, sy = _right_port(positions[start.key])
        ex, ey = _left_port(positions[end.key])
        mid_x = (sx + ex) / 2
        path = f"M{sx:.1f},{sy:.1f} H{mid_x:.1f} V{ey:.1f} H{ex:.1f}"
        if index == 0:
            full_path_parts.append(path)
        else:
            full_path_parts.append(f"H{sx:.1f} H{mid_x:.1f} V{ey:.1f} H{ex:.1f}")
        opacity = 0.9 if selected else 0.22
        width = 3.2 if selected else 1.8
        output.append(
            f'<path data-landscape-flow-process-id="{escape(process_row.node.id)}" class="eam-landscape-flow" '
            f'd="{path}" fill="none" stroke="#46f2b6" stroke-width="{width:.1f}" stroke-linecap="round" '
            f'stroke-dasharray="14 10" stroke-dashoffset="24" opacity="{opacity:.2f}" marker-end="url(#landscape-flow-arrow)" filter="url(#eam-landscape-glow)">'
            '<animate attributeName="stroke-dashoffset" from="24" to="0" dur="1.1s" repeatCount="indefinite"/>'
            '</path>'
        )
        if selected:
            step_x = mid_x
            step_y = min(sy, ey) + (abs(sy - ey) / 2) - 13
            output.append(
                f'<circle data-landscape-flow-step="{index + 1}" cx="{step_x:.1f}" cy="{step_y:.1f}" r="10" '
                'fill="#0f172a" stroke="#46f2b6" stroke-width="1.4"/>'
            )
            output.append(
                f'<text x="{step_x:.1f}" y="{step_y + 4:.1f}" text-anchor="middle" fill="#dbeafe" '
                f'font-family="Inter, Arial, sans-serif" font-size="10" font-weight="900">{index + 1}</text>'
            )
    if with_packets and full_path_parts:
        full_path = " ".join(full_path_parts)
        packet_dur = max(3.6, (len(ordered) - 1) * 1.35)
        sx, sy = _right_port(positions[ordered[0].key])
        label_width = min(260, max(138, _estimated_text_width(payload_label, 11) + 42))
        output.append(
            f'<g class="eam-landscape-flow-payload" data-landscape-flow-payload="{escape(payload_label)}">'
            f'<rect x="{sx:.1f}" y="{sy - 43:.1f}" width="{label_width:.1f}" height="26" rx="12" fill="#111827" stroke="#f72585" opacity="0.92"/>'
            f'<text x="{sx + 14:.1f}" y="{sy - 26:.1f}" fill="#fce7f3" font-family="Inter, Arial, sans-serif" font-size="11" font-weight="900">Payload: {escape(payload_label)}</text>'
            '</g>'
        )
        output.append(
            f'<circle class="eam-landscape-data-packet" r="6" fill="#f72585" opacity="0.96" filter="url(#eam-landscape-packet-glow)">'
            f'<animateMotion dur="{packet_dur:.2f}s" repeatCount="indefinite" path="{full_path}"/></circle>'
        )
    return output


def _legend(width: int, height: int) -> str:
    y = height - 70
    return f"""<g>
  <rect x="24" y="{y}" width="{width - 48}" height="46" rx="13" fill="#081928" stroke="#2d4055"/>
  <rect x="48" y="{y + 15}" width="52" height="16" rx="7" fill="#083344" stroke="#46f2b6"/>
  <text x="112" y="{y + 28}" fill="#cbd5e1" font-family="Inter, Arial, sans-serif" font-size="12">canonical system segment in an evidenced layer row</text>
  <line x1="430" y1="{y + 23}" x2="492" y2="{y + 23}" stroke="#46f2b6" stroke-width="3" stroke-dasharray="14 10" marker-end="url(#landscape-flow-arrow)"/>
  <circle cx="466" cy="{y + 23}" r="5" fill="#f72585"/>
  <text x="510" y="{y + 28}" fill="#cbd5e1" font-family="Inter, Arial, sans-serif" font-size="12">one selected-process packet moves start to end</text>
  <text x="{width - 52}" y="{y + 28}" text-anchor="end" fill="#94a3b8" font-family="Inter, Arial, sans-serif" font-size="12">Layer classification is deterministic from canonical system names plus process context.</text>
</g>"""


def _landscape_systems(model: EamModel) -> list[LandscapeSystemNode]:
    nodes_by_id = {node.id: node for node in model.nodes}
    system_map: dict[str, LandscapeSystemNode] = {}
    for system in model.entity_rollups.get("systems", []):
        key = _normalise_entity_name(system.name)
        layer_ids: list[str] = []
        process_ids = [process_id for process_id in system.linked_process_ids if process_id in nodes_by_id]
        for process_id in process_ids:
            layer_ids.extend(_layers_for_system(system.name, nodes_by_id[process_id]))
        if not layer_ids:
            layer_ids.extend(_layers_for_system(system.name, None))
        existing = system_map.get(key)
        if existing is None:
            system_map[key] = LandscapeSystemNode(
                key=key,
                name=system.name,
                layer_ids=tuple(_dedupe(layer_ids)),
                process_ids=tuple(sorted(set(process_ids))),
            )
            continue
        system_map[key] = LandscapeSystemNode(
            key=key,
            name=existing.name,
            layer_ids=tuple(_dedupe([*existing.layer_ids, *layer_ids])),
            process_ids=tuple(sorted({*existing.process_ids, *process_ids})),
        )
    return sorted(
        system_map.values(),
        key=lambda system: (min(SYSTEM_LAYER_INDEX.get(layer_id, 999) for layer_id in system.layer_ids), system.name.lower()),
    )


def _landscape_process_rows(model: EamModel, systems: list[LandscapeSystemNode]) -> list[LandscapeProcessRow]:
    keys_by_process: dict[str, list[str]] = {node.id: [] for node in model.nodes}
    for system in systems:
        for process_id in system.process_ids:
            keys_by_process.setdefault(process_id, []).append(system.key)
    return [
        LandscapeProcessRow(node=node, system_keys=tuple(sorted(set(keys_by_process.get(node.id, [])))))
        for node in model.nodes
    ]


def _visible_systems(
    systems: list[LandscapeSystemNode],
    selected_node_id: str | None,
    show_all_connections: bool,
) -> list[LandscapeSystemNode]:
    if selected_node_id and not show_all_connections:
        return [system for system in systems if selected_node_id in system.process_ids]
    return systems


def _ordered_systems_for_layout(
    systems: list[LandscapeSystemNode],
    process_rows: list[LandscapeProcessRow],
    selected_node_id: str | None,
) -> list[LandscapeSystemNode]:
    if selected_node_id:
        selected_row = next((row for row in process_rows if row.node.id == selected_node_id), None)
        if selected_row is not None:
            selected_systems = _ordered_process_systems(selected_row, systems, {})
            selected_keys = {system.key for system in selected_systems}
            remaining = [system for system in systems if system.key not in selected_keys]
            return [
                *selected_systems,
                *sorted(remaining, key=_system_sort_key),
            ]
    return sorted(systems, key=_system_sort_key)


def _ordered_process_systems(
    process_row: LandscapeProcessRow,
    systems: list[LandscapeSystemNode],
    positions: dict[str, tuple[LandscapeSystemSegment, ...]],
) -> list[LandscapeSystemNode]:
    by_key = {system.key: system for system in systems}
    return sorted(
        [
            by_key[key]
            for key in process_row.system_keys
            if key in by_key and (not positions or key in positions)
        ],
        key=_system_sort_key,
    )


def _system_sort_key(system: LandscapeSystemNode) -> tuple[int, str]:
    return (
        min(SYSTEM_LAYER_INDEX.get(layer_id, 999) for layer_id in system.layer_ids),
        system.name.lower(),
    )


def _system_positions(systems: list[LandscapeSystemNode]) -> dict[str, tuple[LandscapeSystemSegment, ...]]:
    positions: dict[str, tuple[LandscapeSystemSegment, ...]] = {}
    for column_index, system in enumerate(systems):
        layer_indexes = sorted(SYSTEM_LAYER_INDEX[layer_id] for layer_id in system.layer_ids if layer_id in SYSTEM_LAYER_INDEX)
        if not layer_indexes:
            continue
        x = SYSTEM_X + (column_index * SYSTEM_COL_W) + 12
        segments: list[LandscapeSystemSegment] = []
        for run in _contiguous_layer_runs(layer_indexes):
            first_index = run[0]
            last_index = run[-1]
            y = CANVAS_TOP + (first_index * (LAYER_ROW_H + LAYER_ROW_GAP)) + SYSTEM_NODE_PAD_Y
            height = ((last_index - first_index + 1) * LAYER_ROW_H) + ((last_index - first_index) * LAYER_ROW_GAP) - (SYSTEM_NODE_PAD_Y * 2)
            segments.append(
                LandscapeSystemSegment(
                    layer_ids=tuple(SYSTEM_LAYERS[index].id for index in run),
                    x=x,
                    y=y,
                    width=SYSTEM_NODE_W,
                    height=height,
                )
            )
        positions[system.key] = tuple(segments)
    return positions


def _process_tops(process_rows: list[LandscapeProcessRow]) -> list[int]:
    return [CANVAS_TOP + (index * (PROCESS_ROW_H + ROW_GAP)) for index, _ in enumerate(process_rows)]


def _process_list_height(process_rows: list[LandscapeProcessRow]) -> int:
    if not process_rows:
        return MIN_CANVAS_H
    return (len(process_rows) * PROCESS_ROW_H) + ((len(process_rows) - 1) * ROW_GAP)


def _layer_canvas_height() -> int:
    return (len(SYSTEM_LAYERS) * LAYER_ROW_H) + ((len(SYSTEM_LAYERS) - 1) * LAYER_ROW_GAP)


def _layers_for_system(system_name: str, node: EamNode | None) -> list[str]:
    system_text = _normalise(system_name)
    process_text = ""
    if node is not None:
        process_text = _normalise(" ".join((node.name, node.domain_label, node.lifecycle_label, *node.matched_domain_keywords, *node.matched_lifecycle_keywords)))
    combined = f"{system_text} {process_text}"
    layer_ids: list[str] = []
    if any(term in system_text for term in ("point of sale", "point-of-sale", "pos", "retail consumer", "retail selling")):
        layer_ids.extend(["sales-execution", "store-operations", "central-store-admin"])
    for layer in SYSTEM_LAYERS:
        if any(keyword in system_text for keyword in layer.keywords):
            layer_ids.append(layer.id)
    if not layer_ids and process_text:
        for layer in SYSTEM_LAYERS:
            if any(keyword in combined for keyword in layer.keywords):
                layer_ids.append(layer.id)
    if not layer_ids:
        layer_ids.append("integration-reports")
    return _dedupe(layer_ids)[:4]


def _node_code(node: EamNode) -> str:
    prefix = "SYS"
    if node.domain_id:
        prefix = "".join(part[:1] for part in node.domain_id.split("-")[:3]).upper() or "SYS"
    digest = hashlib.sha1(node.id.encode("utf-8")).hexdigest()
    return f"{prefix}-{(int(digest[:6], 16) % 900) + 100}"


def _flow_payload_label(node: EamNode) -> str:
    text = _normalise(
        " ".join(
            (
                node.name,
                node.domain_label,
                node.lifecycle_label,
                *node.matched_domain_keywords,
                *node.matched_lifecycle_keywords,
            )
        )
    )
    candidates = (
        (("complaint", "case"), "Complaint case"),
        (("invoice", "grir", "reconciliation"), "Invoice matching data"),
        (("payment contract",), "Payment contract data"),
        (("commercial contract", "service contract", "contract"), "Contract data"),
        (("supplier", "vendor"), "Supplier setup data"),
        (("article", "sku", "item"), "Article master data"),
        (("price", "pricing", "rate"), "Price and rate data"),
        (("tax", "vat"), "Tax handling data"),
        (("stock", "inventory"), "Stock movement data"),
        (("forecast", "replenish", "replenishment"), "Forecast and replenishment data"),
        (("promotion", "discount"), "Promotion data"),
        (("list", "criteria"), "List criteria data"),
        (("order", "ordering"), "Order data"),
    )
    for terms, label in candidates:
        if any(term in text for term in terms):
            return label
    cleaned_name = " ".join(node.name.split())
    if cleaned_name:
        return f"{cleaned_name} data"
    return "Operating data"


def _normalise(value: str) -> str:
    return value.lower().replace("\u2013", "-").replace("\u2014", "-")


def _normalise_entity_name(value: str) -> str:
    return " ".join("".join(char if char.isalnum() else " " for char in _normalise(value)).split())


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value in seen or value not in LAYER_BY_ID:
            continue
        seen.add(value)
        output.append(value)
    return output


def _contiguous_layer_runs(layer_indexes: list[int]) -> list[list[int]]:
    if not layer_indexes:
        return []
    runs: list[list[int]] = [[layer_indexes[0]]]
    for index in layer_indexes[1:]:
        if index == runs[-1][-1] + 1:
            runs[-1].append(index)
            continue
        runs.append([index])
    return runs


def _right_port(segments: tuple[LandscapeSystemSegment, ...]) -> tuple[float, float]:
    segment = max(segments, key=lambda item: item.x + item.width)
    return segment.x + segment.width, segment.y + (segment.height / 2)


def _left_port(segments: tuple[LandscapeSystemSegment, ...]) -> tuple[float, float]:
    segment = min(segments, key=lambda item: item.x)
    return segment.x, segment.y + (segment.height / 2)


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


def _layer_icon(layer: SystemLayer) -> str:
    icon = _icon_data_uri(layer.icon_file)
    if icon:
        return icon
    fallback = (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 80 80'>"
        "<rect x='14' y='14' width='52' height='52' rx='12' fill='none' stroke='%23dbeafe' stroke-width='4'/>"
        "<path d='M24 44h32M24 32h32M24 56h20' stroke='%23dbeafe' stroke-width='4' stroke-linecap='round'/>"
        "</svg>"
    )
    return "data:image/svg+xml;utf8," + fallback


@lru_cache(maxsize=16)
def _icon_data_uri(file_name: str) -> str:
    path = Path(__file__).with_name("assets") / "systems" / file_name
    if not path.exists():
        return ""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"
