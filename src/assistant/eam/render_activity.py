"""Server-side Activity-view SVG renderer for the Enterprise Activity Model."""

from __future__ import annotations

from html import escape

from .model import EamFinding, EamModel

_BAND_COLOURS = {
    "green": "#22c55e",
    "amber": "#f59e0b",
    "red": "#ef4444",
}


def render_activity_svg(model: EamModel) -> str:
    """Render the EAM domain x lifecycle Activity view as deterministic SVG."""

    left = 220
    top = 128
    col_w = 168
    row_h = 156
    cell_pad = 12
    width = left + (len(model.lifecycle_stages) * col_w) + 56
    height = top + (len(model.domains) * row_h) + 148
    node_positions = _node_positions(model, left, top, col_w, row_h, cell_pad)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="Enterprise Activity Model">',
        _defs(),
        f'<rect width="{width}" height="{height}" fill="#0f172a"/>',
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
  <filter id="eam-shadow" x="-20%" y="-20%" width="140%" height="160%">
    <feDropShadow dx="0" dy="8" stdDeviation="8" flood-color="#020617" flood-opacity="0.22"/>
  </filter>
</defs>"""


def _header(model: EamModel, width: int) -> str:
    return f"""<rect x="24" y="24" width="{width - 48}" height="78" rx="16" fill="#111827" stroke="#334155"/>
<text x="48" y="58" fill="#f8fafc" font-family="Inter, Arial, sans-serif" font-size="26" font-weight="700">
  Enterprise Activity Model
</text>
<text x="48" y="86" fill="#cbd5e1" font-family="Inter, Arial, sans-serif" font-size="15">
  Derived from {model.source_count} approved sources - {model.process_count} processes - EAM coverage {model.coverage.score}%
</text>
<text x="{width - 250}" y="62" fill="#ec4899" font-family="Inter, Arial, sans-serif" font-size="18" font-weight="700">
  {model.finding_counts.get("clash", 0)} clashes
</text>
<text x="{width - 250}" y="86" fill="#f59e0b" font-family="Inter, Arial, sans-serif" font-size="15">
  {model.finding_counts.get("gap", 0)} gaps / {model.finding_counts.get("overlap", 0)} overlaps
</text>"""


def _column_headers(model: EamModel, left: int, top: int, col_w: int) -> list[str]:
    rows = []
    for index, stage in enumerate(model.lifecycle_stages):
        x = left + (index * col_w)
        rows.append(
            f'<text x="{x + col_w / 2:.1f}" y="{top - 18}" text-anchor="middle" fill="#e2e8f0" '
            f'font-family="Inter, Arial, sans-serif" font-size="13" font-weight="700">{escape(stage.label)}</text>'
        )
    return rows


def _row_headers(model: EamModel, top: int, row_h: int) -> list[str]:
    rows = []
    for index, domain in enumerate(model.domains):
        y = top + (index * row_h)
        rows.append(f'<rect x="24" y="{y}" width="176" height="{row_h - 14}" rx="14" fill="#111827" stroke="#1f2937"/>')
        rows.append(
            f'<text x="42" y="{y + 32}" fill="#f8fafc" font-family="Inter, Arial, sans-serif" '
            f'font-size="13" font-weight="700">{escape(domain.label)}</text>'
        )
        rows.append(
            f'<text x="42" y="{y + 58}" fill="#94a3b8" font-family="Inter, Arial, sans-serif" font-size="11">'
            f'{escape(domain.id)}</text>'
        )
    return rows


def _cells(model: EamModel, left: int, top: int, col_w: int, row_h: int) -> list[str]:
    rows = []
    for domain_index, domain in enumerate(model.domains):
        for stage_index, stage in enumerate(model.lifecycle_stages):
            x = left + (stage_index * col_w)
            y = top + (domain_index * row_h)
            cell = next(item for item in model.cells if item.domain_id == domain.id and item.lifecycle_id == stage.id)
            if cell.is_gap:
                rows.append(
                    f'<rect x="{x}" y="{y}" width="{col_w - 12}" height="{row_h - 14}" rx="14" '
                    f'fill="#111827" stroke="#334155" stroke-dasharray="6 6" opacity="0.76"/>'
                )
                rows.append(
                    f'<text x="{x + col_w / 2 - 6:.1f}" y="{y + row_h / 2 - 5:.1f}" text-anchor="middle" '
                    f'fill="#64748b" font-family="Inter, Arial, sans-serif" font-size="11">No evidence</text>'
                )
            else:
                rows.append(
                    f'<rect x="{x}" y="{y}" width="{col_w - 12}" height="{row_h - 14}" rx="14" '
                    f'fill="#172033" stroke="#334155"/>'
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
            for stack_index, node_id in enumerate(node_ids[:3]):
                x = left + (stage_index * col_w) + cell_pad
                y = top + (domain_index * row_h) + cell_pad + (stack_index * 42)
                positions[node_id] = (x, y, col_w - 36, 34)
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
            label = _truncate(node.name, 24)
            rows.append(
                f'<g data-node-id="{escape(node.id)}" filter="url(#eam-shadow)">'
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="9" fill="#f8fafc" stroke="#cbd5e1"/>'
                f'<rect x="{x:.1f}" y="{y:.1f}" width="5" height="{h:.1f}" rx="3" fill="{colour}"/>'
                f'<text x="{x + 12:.1f}" y="{y + 15:.1f}" fill="#0f172a" font-family="Inter, Arial, sans-serif" '
                f'font-size="11" font-weight="700">{escape(label)}</text>'
                f'<text x="{x + 12:.1f}" y="{y + 28:.1f}" fill="#475569" font-family="Inter, Arial, sans-serif" '
                f'font-size="9">R{node.role_count} S{node.system_count} C{node.control_count}</text>'
                "</g>"
            )
        if hidden:
            first_node = node_by_id[cell.node_ids[0]]
            x, y, w, _ = positions[first_node.id]
            rows.append(
                f'<text x="{x + w - 8:.1f}" y="{y + 130:.1f}" text-anchor="end" fill="#cbd5e1" '
                f'font-family="Inter, Arial, sans-serif" font-size="11">+{hidden} more</text>'
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
        rows.append(
            f'<line data-edge-id="{escape(edge.id)}" x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{colour}" stroke-width="2.2" opacity="0.72"{dash}/>'
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
            f'stroke-linecap="round" opacity="0.9"/>'
        )
    return rows


def _stage_strip(model: EamModel, left: int, y: int, col_w: int) -> list[str]:
    rows = [
        f'<text x="{left}" y="{y - 14}" fill="#cbd5e1" font-family="Inter, Arial, sans-serif" font-size="13" '
        'font-weight="700">Per-stage coverage</text>'
    ]
    for index, stage in enumerate(model.lifecycle_stages):
        cells = [cell for cell in model.cells if cell.lifecycle_id == stage.id]
        coverage = round((sum(1 for cell in cells if not cell.is_gap) / len(cells)) * 100) if cells else 0
        x = left + (index * col_w)
        rows.append(f'<rect x="{x}" y="{y}" width="{col_w - 18}" height="10" rx="5" fill="#1e293b"/>')
        rows.append(f'<rect x="{x}" y="{y}" width="{(col_w - 18) * coverage / 100:.1f}" height="10" rx="5" fill="#ec4899"/>')
        rows.append(
            f'<text x="{x + (col_w / 2) - 9:.1f}" y="{y + 30}" text-anchor="middle" fill="#94a3b8" '
            f'font-family="Inter, Arial, sans-serif" font-size="11">{coverage}%</text>'
        )
    return rows


def _legend(width: int, height: int) -> str:
    x = 24
    y = height - 64
    rows = [
        "<g>",
        f'<rect x="{x}" y="{y}" width="{width - 48}" height="40" rx="13" fill="#111827" stroke="#334155"/>',
        _legend_dot(x + 24, y + 21, "#22c55e", x + 38, y + 26, "strong evidence"),
        _legend_dot(x + 180, y + 21, "#f59e0b", x + 194, y + 26, "partial evidence"),
        _legend_dot(x + 340, y + 21, "#ef4444", x + 354, y + 26, "weak/clash"),
        (
            f'<line x1="{x + 490}" y1="{y + 21}" x2="{x + 540}" y2="{y + 21}" '
            'stroke="#38bdf8" stroke-width="2" stroke-dasharray="7 6"/>'
            f'<text x="{x + 552}" y="{y + 26}" fill="#cbd5e1" font-family="Inter, Arial, sans-serif" '
            'font-size="12">shared system</text>'
        ),
        (
            f'<line x1="{x + 680}" y1="{y + 21}" x2="{x + 730}" y2="{y + 21}" stroke="#fb923c" stroke-width="2"/>'
            f'<text x="{x + 742}" y="{y + 26}" fill="#cbd5e1" font-family="Inter, Arial, sans-serif" '
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


def _centre(box: tuple[float, float, float, float]) -> tuple[float, float]:
    x, y, w, h = box
    return x + (w / 2), y + (h / 2)


def _truncate(value: str, length: int) -> str:
    if len(value) <= length:
        return value
    return value[: length - 1].rstrip() + "..."
