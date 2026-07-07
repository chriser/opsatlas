"""Server-side Accountability-view SVG renderer for the Enterprise Activity Model."""

from __future__ import annotations

from html import escape

from .model import EamModel, EamNode, EntityRollup

_BAND_COLOURS = {
    "green": "#22c55e",
    "amber": "#f59e0b",
    "red": "#ef4444",
}

LANE_H = 178
ROLE_PANEL_W = 222
NODE_CARD_W = 164
NODE_CARD_H = 116
NODE_CARD_STEP = 178
NODE_CARD_START_X = 264


def render_accountability_svg(model: EamModel) -> str:
    """Render the EAM accountability view as deterministic owner swimlanes."""

    lanes = _role_lanes(model)
    top = 136
    width = 1180
    height = top + (len(lanes) * LANE_H) + 116
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" '
        'aria-label="Enterprise Activity Model Accountability View">',
        _defs(),
        f'<rect width="{width}" height="{height}" fill="#0f172a"/>',
        _header(model, width),
        *_lanes(lanes, top, LANE_H, width),
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
    label_lines = _wrap_text_to_width(label, ROLE_PANEL_W - 40, 14, 3)
    rows = [
        f'<g data-role-id="{escape(role_id)}">',
        f'<rect x="24" y="{y}" width="{width - 48}" height="{lane_h - 16}" rx="16" fill="#111827" stroke="#334155"/>',
        f'<rect x="24" y="{y}" width="{ROLE_PANEL_W}" height="{lane_h - 16}" rx="16" fill="#172033" stroke="#334155"/>',
        *_text_lines(44, y + 32, label_lines, 14, 16, "#f8fafc", 800),
        f'<text x="44" y="{y + 88}" fill="#94a3b8" font-family="Inter, Arial, sans-serif" font-size="12">'
        f'{len(nodes)} processes</text>',
        f'<text x="44" y="{y + 114}" fill="#38bdf8" font-family="Inter, Arial, sans-serif" font-size="12">'
        f'{linked_counts.get("systems", 0)} linked systems</text>',
        f'<text x="44" y="{y + 140}" fill="#fb923c" font-family="Inter, Arial, sans-serif" font-size="12">'
        f'{linked_counts.get("controls", 0)} linked controls</text>',
    ]
    if not nodes:
        rows.append(
            f'<text x="{NODE_CARD_START_X}" y="{y + 82}" fill="#64748b" font-family="Inter, Arial, sans-serif" font-size="13">'
            "No process evidence linked to this owner</text>"
        )
    for node_index, node in enumerate(nodes[:5]):
        rows.append(_node_card(node, NODE_CARD_START_X + (node_index * NODE_CARD_STEP), y + 24))
    if len(nodes) > 5:
        rows.append(
            f'<text x="{width - 62}" y="{y + 82}" text-anchor="end" fill="#cbd5e1" '
            f'font-family="Inter, Arial, sans-serif" font-size="12">+{len(nodes) - 5} more</text>'
        )
    rows.append("</g>")
    return rows


def _node_card(node: EamNode, x: int, y: int) -> str:
    colour = _BAND_COLOURS.get(node.confidence_band, "#f59e0b")
    name_lines = _wrap_text_to_width(node.name, NODE_CARD_W - 24, 11, 3)
    domain_lines = _wrap_text_to_width(node.domain_label, NODE_CARD_W - 24, 9, 2)
    lifecycle_lines = _wrap_text_to_width(node.lifecycle_label, NODE_CARD_W - 24, 9, 2)
    metrics_y = y + NODE_CARD_H - 13
    domain_y = y + 60
    lifecycle_y = domain_y + (len(domain_lines) * 12) + 8
    return f"""<g data-node-id="{escape(node.id)}" filter="url(#eam-accountability-shadow)">
  {_node_title(node)}
  <rect x="{x}" y="{y}" width="{NODE_CARD_W}" height="{NODE_CARD_H}" rx="12" fill="#f8fafc" stroke="#cbd5e1"/>
  <rect x="{x}" y="{y}" width="6" height="{NODE_CARD_H}" rx="4" fill="{colour}"/>
  {''.join(_text_lines(x + 14, y + 22, name_lines, 11, 13, '#0f172a', 800))}
  {''.join(_text_lines(x + 14, domain_y, domain_lines, 9, 12, '#475569', 700))}
  {''.join(_text_lines(x + 14, lifecycle_y, lifecycle_lines, 9, 12, '#64748b', 700))}
  <text x="{x + 14}" y="{metrics_y}" fill="#0f172a" font-family="Inter, Arial, sans-serif" font-size="10" font-weight="800">
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


def _text_lines(x: int, y: int, lines: list[str], font_size: int, line_h: int, colour: str, weight: int) -> list[str]:
    return [
        f'<text x="{x}" y="{y + (index * line_h)}" fill="{colour}" font-family="Inter, Arial, sans-serif" '
        f'font-size="{font_size}" font-weight="{weight}">{escape(line)}</text>'
        for index, line in enumerate(lines)
    ]


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


def _node_title(node: EamNode) -> str:
    sources = ", ".join(node.source_refs) if node.source_refs else "no source refs"
    return f"<title>{escape(node.name)} - sources: {escape(sources)}</title>"
