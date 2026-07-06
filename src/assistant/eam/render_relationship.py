"""Server-side Relationship-view SVG renderer for the Enterprise Activity Model."""

from __future__ import annotations

import math
from html import escape

from .model import EamModel, EamNode, EntityRollup

_TYPE_COLOURS = {
    "process": ("#f8fafc", "#cbd5e1", "#0f172a"),
    "role": ("#e0f2fe", "#38bdf8", "#0f172a"),
    "system": ("#dcfce7", "#22c55e", "#0f172a"),
    "control": ("#ffedd5", "#fb923c", "#0f172a"),
}

MAX_RELATIONSHIP_RENDER_EDGES = 220


def render_relationship_svg(model: EamModel) -> str:
    """Render the EAM relationship lens as a deterministic entity graph."""

    width = 1240
    height = 860
    graph_cx = width / 2
    graph_cy = 476
    process_positions = _process_positions(model.nodes, graph_cx, graph_cy, 170)
    entity_rows = _entity_rows(model)
    entity_positions = _entity_positions(entity_rows, graph_cx, graph_cy, 316)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" '
        'aria-label="Enterprise Activity Model Relationship View">',
        _defs(),
        f'<rect width="{width}" height="{height}" fill="#0f172a"/>',
        _header(model, width),
        *_rings(graph_cx, graph_cy),
        *_relationship_edges(entity_rows, process_positions, entity_positions),
        *_entity_nodes(entity_rows, entity_positions),
        *_process_nodes(model.nodes, process_positions),
        _legend(width, height),
        "</svg>",
    ]
    return "\n".join(parts)


def _defs() -> str:
    return """<defs>
  <filter id="eam-relationship-shadow" x="-20%" y="-20%" width="140%" height="160%">
    <feDropShadow dx="0" dy="8" stdDeviation="8" flood-color="#020617" flood-opacity="0.22"/>
  </filter>
</defs>"""


def _header(model: EamModel, width: int) -> str:
    entity_count = sum(len(items) for items in model.entity_rollups.values())
    return f"""<rect x="24" y="24" width="{width - 48}" height="84" rx="16" fill="#111827" stroke="#334155"/>
<text x="48" y="58" fill="#f8fafc" font-family="Inter, Arial, sans-serif" font-size="25" font-weight="700">
  Relationship View
</text>
<text x="48" y="87" fill="#cbd5e1" font-family="Inter, Arial, sans-serif" font-size="15">
  Process nodes connected to {entity_count} role, system and control entities from ontology links.
</text>
<text x="{width - 300}" y="60" fill="#ec4899" font-family="Inter, Arial, sans-serif" font-size="17" font-weight="700">
  Entity graph
</text>
<text x="{width - 300}" y="86" fill="#94a3b8" font-family="Inter, Arial, sans-serif" font-size="13">
  Designed for frontend pan / zoom controls
</text>"""


def _rings(cx: float, cy: float) -> list[str]:
    return [
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="170" fill="none" stroke="#1e293b" stroke-width="2"/>',
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="316" fill="none" stroke="#1e293b" stroke-width="2" stroke-dasharray="8 8"/>',
        f'<text x="{cx:.1f}" y="{cy - 188:.1f}" text-anchor="middle" fill="#64748b" '
        'font-family="Inter, Arial, sans-serif" font-size="12">process ring</text>',
        f'<text x="{cx:.1f}" y="{cy - 334:.1f}" text-anchor="middle" fill="#64748b" '
        'font-family="Inter, Arial, sans-serif" font-size="12">entity ring</text>',
    ]


def _process_positions(nodes: list[EamNode], cx: float, cy: float, radius: float) -> dict[str, tuple[float, float]]:
    positions: dict[str, tuple[float, float]] = {}
    if not nodes:
        return positions
    for index, node in enumerate(sorted(nodes, key=lambda item: item.name.lower())):
        angle = (-90 + (360 * index / len(nodes))) * math.pi / 180
        positions[node.id] = (cx + (math.cos(angle) * radius), cy + (math.sin(angle) * radius))
    return positions


def _entity_rows(model: EamModel) -> list[tuple[str, EntityRollup]]:
    rows: list[tuple[str, EntityRollup]] = []
    for key, entity_type in (("roles", "role"), ("systems", "system"), ("controls", "control")):
        rows.extend((entity_type, row) for row in model.entity_rollups.get(key, []))
    return sorted(rows, key=lambda item: (item[0], -item[1].process_count, item[1].name.lower()))


def _entity_positions(rows: list[tuple[str, EntityRollup]], cx: float, cy: float, radius: float) -> dict[str, tuple[float, float]]:
    positions: dict[str, tuple[float, float]] = {}
    if not rows:
        return positions
    type_ranges = {
        "role": (205, 335),
        "system": (-35, 55),
        "control": (75, 175),
    }
    by_type: dict[str, list[EntityRollup]] = {"role": [], "system": [], "control": []}
    for entity_type, row in rows:
        by_type.setdefault(entity_type, []).append(row)
    for entity_type, entities in by_type.items():
        if not entities:
            continue
        start, end = type_ranges.get(entity_type, (0, 360))
        span = max(1, end - start)
        for index, entity in enumerate(entities):
            if len(entities) == 1:
                angle_degrees = start + (span / 2)
            else:
                angle_degrees = start + (span * index / (len(entities) - 1))
            angle = angle_degrees * math.pi / 180
            positions[entity.id] = (cx + (math.cos(angle) * radius), cy + (math.sin(angle) * radius))
    return positions


def _relationship_edges(
    rows: list[tuple[str, EntityRollup]],
    process_positions: dict[str, tuple[float, float]],
    entity_positions: dict[str, tuple[float, float]],
) -> list[str]:
    output: list[str] = []
    for entity_type, entity in rows:
        if entity.id not in entity_positions:
            continue
        x2, y2 = entity_positions[entity.id]
        colour = _TYPE_COLOURS.get(entity_type, _TYPE_COLOURS["process"])[1]
        for process_id in entity.linked_process_ids:
            if process_id not in process_positions:
                continue
            if len(output) >= MAX_RELATIONSHIP_RENDER_EDGES:
                return output
            x1, y1 = process_positions[process_id]
            output.append(
                f'<line data-relationship-id="{escape(process_id)}:{escape(entity.id)}" x1="{x1:.1f}" y1="{y1:.1f}" '
                f'x2="{x2:.1f}" y2="{y2:.1f}" stroke="{colour}" stroke-width="1.8" opacity="0.55"/>'
            )
    return output


def _entity_nodes(rows: list[tuple[str, EntityRollup]], positions: dict[str, tuple[float, float]]) -> list[str]:
    output: list[str] = []
    for entity_type, entity in rows:
        if entity.id not in positions:
            continue
        x, y = positions[entity.id]
        fill, stroke, text = _TYPE_COLOURS.get(entity_type, _TYPE_COLOURS["process"])
        output.append(
            f'<g data-entity-id="{escape(entity.id)}" data-entity-type="{escape(entity_type)}" '
            'filter="url(#eam-relationship-shadow)">'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="34" fill="{fill}" stroke="{stroke}" stroke-width="3"/>'
            f'<text x="{x:.1f}" y="{y - 2:.1f}" text-anchor="middle" fill="{text}" '
            f'font-family="Inter, Arial, sans-serif" font-size="10" font-weight="800">{escape(entity_type.upper())}</text>'
            f'<text x="{x:.1f}" y="{y + 14:.1f}" text-anchor="middle" fill="{text}" '
            f'font-family="Inter, Arial, sans-serif" font-size="9">{entity.process_count} links</text>'
            f'<text x="{x:.1f}" y="{y + 51:.1f}" text-anchor="middle" fill="#cbd5e1" '
            f'font-family="Inter, Arial, sans-serif" font-size="10">{escape(_truncate(entity.name, 24))}</text>'
            "</g>"
        )
    return output


def _process_nodes(nodes: list[EamNode], positions: dict[str, tuple[float, float]]) -> list[str]:
    output: list[str] = []
    for node in sorted(nodes, key=lambda item: item.name.lower()):
        if node.id not in positions:
            continue
        x, y = positions[node.id]
        fill, stroke, text = _TYPE_COLOURS["process"]
        output.append(
            f'<g data-node-id="{escape(node.id)}" filter="url(#eam-relationship-shadow)">'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="42" fill="{fill}" stroke="{stroke}" stroke-width="3"/>'
            f'<text x="{x:.1f}" y="{y - 4:.1f}" text-anchor="middle" fill="{text}" '
            f'font-family="Inter, Arial, sans-serif" font-size="11" font-weight="800">{escape(_truncate(node.name, 17))}</text>'
            f'<text x="{x:.1f}" y="{y + 15:.1f}" text-anchor="middle" fill="#475569" '
            f'font-family="Inter, Arial, sans-serif" font-size="9">{escape(_truncate(node.domain_label, 17))}</text>'
            "</g>"
        )
    return output


def _legend(width: int, height: int) -> str:
    x = 24
    y = height - 64
    return f"""<g>
  <rect x="{x}" y="{y}" width="{width - 48}" height="40" rx="13" fill="#111827" stroke="#334155"/>
  {_legend_dot(x + 24, y + 21, "#f8fafc", "#cbd5e1", x + 42, y + 26, "process")}
  {_legend_dot(x + 138, y + 21, "#e0f2fe", "#38bdf8", x + 156, y + 26, "role / owner")}
  {_legend_dot(x + 294, y + 21, "#dcfce7", "#22c55e", x + 312, y + 26, "system")}
  {_legend_dot(x + 414, y + 21, "#ffedd5", "#fb923c", x + 432, y + 26, "control")}
  <text x="{x + 560}" y="{y + 26}" fill="#cbd5e1" font-family="Inter, Arial, sans-serif" font-size="12">
    Links are generated from process_has_role, process_uses_system and process_enforced_by.
  </text>
</g>"""


def _legend_dot(cx: int, cy: int, fill: str, stroke: str, text_x: int, text_y: int, label: str) -> str:
    return (
        f'<circle cx="{cx}" cy="{cy}" r="7" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
        f'<text x="{text_x}" y="{text_y}" fill="#cbd5e1" font-family="Inter, Arial, sans-serif" font-size="12">'
        f"{escape(label)}</text>"
    )


def _truncate(value: str, length: int) -> str:
    if len(value) <= length:
        return value
    return value[: length - 1].rstrip() + "..."
