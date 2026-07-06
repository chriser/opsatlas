"""Server-side Accountability-view SVG renderer for the Enterprise Activity Model."""

from __future__ import annotations

from html import escape

from .model import EamModel, EamNode, EntityRollup

_BAND_COLOURS = {
    "green": "#22c55e",
    "amber": "#f59e0b",
    "red": "#ef4444",
}


def render_accountability_svg(model: EamModel) -> str:
    """Render the EAM accountability view as deterministic owner swimlanes."""

    lanes = _role_lanes(model)
    lane_h = 150
    top = 136
    width = 1180
    height = top + (len(lanes) * lane_h) + 116
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" '
        'aria-label="Enterprise Activity Model Accountability View">',
        _defs(),
        f'<rect width="{width}" height="{height}" fill="#0f172a"/>',
        _header(model, width),
        *_lanes(lanes, top, lane_h, width),
        _legend(width, height),
        "</svg>",
    ]
    return "\n".join(parts)


def _role_lanes(model: EamModel) -> list[tuple[EntityRollup | None, list[EamNode]]]:
    node_by_id = {node.id: node for node in model.nodes}
    assigned_node_ids: set[str] = set()
    lanes: list[tuple[EntityRollup | None, list[EamNode]]] = []
    for role in model.entity_rollups.get("roles", []):
        nodes = [node_by_id[node_id] for node_id in role.linked_process_ids if node_id in node_by_id]
        if not nodes:
            continue
        assigned_node_ids.update(node.id for node in nodes)
        lanes.append((role, sorted(nodes, key=lambda node: node.name.lower())))
    unassigned = sorted((node for node in model.nodes if node.id not in assigned_node_ids), key=lambda node: node.name.lower())
    if unassigned:
        lanes.append((None, unassigned))
    return lanes or [(None, [])]


def _defs() -> str:
    return """<defs>
  <filter id="eam-accountability-shadow" x="-20%" y="-20%" width="140%" height="160%">
    <feDropShadow dx="0" dy="8" stdDeviation="8" flood-color="#020617" flood-opacity="0.20"/>
  </filter>
</defs>"""


def _header(model: EamModel, width: int) -> str:
    role_count = len(model.entity_rollups.get("roles", []))
    return f"""<rect x="24" y="24" width="{width - 48}" height="84" rx="16" fill="#111827" stroke="#334155"/>
<text x="48" y="58" fill="#f8fafc" font-family="Inter, Arial, sans-serif" font-size="25" font-weight="700">
  Accountability View
</text>
<text x="48" y="87" fill="#cbd5e1" font-family="Inter, Arial, sans-serif" font-size="15">
  {role_count} roles / owners - {model.process_count} process nodes - {model.source_count} approved sources
</text>
<text x="{width - 310}" y="60" fill="#ec4899" font-family="Inter, Arial, sans-serif" font-size="17" font-weight="700">
  Owner swimlanes
</text>
<text x="{width - 310}" y="86" fill="#94a3b8" font-family="Inter, Arial, sans-serif" font-size="13">
  Cards show domain, lifecycle and evidence strength
</text>"""


def _lanes(lanes: list[tuple[EntityRollup | None, list[EamNode]]], top: int, lane_h: int, width: int) -> list[str]:
    rows: list[str] = []
    for index, (role, nodes) in enumerate(lanes):
        y = top + (index * lane_h)
        rows.extend(_lane(role, nodes, y, lane_h, width))
    return rows


def _lane(role: EntityRollup | None, nodes: list[EamNode], y: int, lane_h: int, width: int) -> list[str]:
    label = role.name if role else "Unassigned owner"
    role_id = role.id if role else "unassigned"
    linked_counts = role.linked_entity_counts if role else {"systems": 0, "controls": 0}
    rows = [
        f'<g data-role-id="{escape(role_id)}">',
        f'<rect x="24" y="{y}" width="{width - 48}" height="{lane_h - 16}" rx="16" fill="#111827" stroke="#334155"/>',
        f'<rect x="24" y="{y}" width="210" height="{lane_h - 16}" rx="16" fill="#172033" stroke="#334155"/>',
        f'<text x="44" y="{y + 34}" fill="#f8fafc" font-family="Inter, Arial, sans-serif" font-size="15" '
        f'font-weight="700">{escape(_truncate(label, 26))}</text>',
        f'<text x="44" y="{y + 62}" fill="#94a3b8" font-family="Inter, Arial, sans-serif" font-size="12">'
        f'{len(nodes)} processes</text>',
        f'<text x="44" y="{y + 88}" fill="#38bdf8" font-family="Inter, Arial, sans-serif" font-size="12">'
        f'{linked_counts.get("systems", 0)} linked systems</text>',
        f'<text x="44" y="{y + 112}" fill="#fb923c" font-family="Inter, Arial, sans-serif" font-size="12">'
        f'{linked_counts.get("controls", 0)} linked controls</text>',
    ]
    if not nodes:
        rows.append(
            f'<text x="270" y="{y + 72}" fill="#64748b" font-family="Inter, Arial, sans-serif" font-size="13">'
            "No process evidence linked to this owner</text>"
        )
    for node_index, node in enumerate(nodes[:5]):
        rows.append(_node_card(node, 270 + (node_index * 172), y + 24))
    if len(nodes) > 5:
        rows.append(
            f'<text x="{width - 62}" y="{y + 82}" text-anchor="end" fill="#cbd5e1" '
            f'font-family="Inter, Arial, sans-serif" font-size="12">+{len(nodes) - 5} more</text>'
        )
    rows.append("</g>")
    return rows


def _node_card(node: EamNode, x: int, y: int) -> str:
    colour = _BAND_COLOURS.get(node.confidence_band, "#f59e0b")
    return f"""<g data-node-id="{escape(node.id)}" filter="url(#eam-accountability-shadow)">
  <rect x="{x}" y="{y}" width="150" height="88" rx="12" fill="#f8fafc" stroke="#cbd5e1"/>
  <rect x="{x}" y="{y}" width="6" height="88" rx="4" fill="{colour}"/>
  <text x="{x + 14}" y="{y + 22}" fill="#0f172a" font-family="Inter, Arial, sans-serif" font-size="12" font-weight="700">
    {escape(_truncate(node.name, 20))}
  </text>
  <text x="{x + 14}" y="{y + 43}" fill="#475569" font-family="Inter, Arial, sans-serif" font-size="10">
    {escape(_truncate(node.domain_label, 18))}
  </text>
  <text x="{x + 14}" y="{y + 60}" fill="#64748b" font-family="Inter, Arial, sans-serif" font-size="10">
    {escape(_truncate(node.lifecycle_label, 18))}
  </text>
  <text x="{x + 14}" y="{y + 77}" fill="#0f172a" font-family="Inter, Arial, sans-serif" font-size="10" font-weight="700">
    R{node.role_count} S{node.system_count} C{node.control_count} / {node.evidence_strength}
  </text>
</g>"""


def _legend(width: int, height: int) -> str:
    x = 24
    y = height - 64
    return f"""<g>
  <rect x="{x}" y="{y}" width="{width - 48}" height="40" rx="13" fill="#111827" stroke="#334155"/>
  {_legend_dot(x + 24, y + 21, "#22c55e", x + 38, y + 26, "strong evidence")}
  {_legend_dot(x + 186, y + 21, "#f59e0b", x + 200, y + 26, "partial evidence")}
  {_legend_dot(x + 354, y + 21, "#ef4444", x + 368, y + 26, "weak evidence or clash")}
  <text x="{x + 550}" y="{y + 26}" fill="#cbd5e1" font-family="Inter, Arial, sans-serif" font-size="12">
    Swimlanes are derived from process_has_role ontology links.
  </text>
</g>"""


def _legend_dot(cx: int, cy: int, colour: str, text_x: int, text_y: int, label: str) -> str:
    return (
        f'<circle cx="{cx}" cy="{cy}" r="6" fill="{colour}"/>'
        f'<text x="{text_x}" y="{text_y}" fill="#cbd5e1" font-family="Inter, Arial, sans-serif" font-size="12">'
        f"{escape(label)}</text>"
    )


def _truncate(value: str, length: int) -> str:
    if len(value) <= length:
        return value
    return value[: length - 1].rstrip() + "..."
