"""Server-side Risk and coverage heat-view SVG renderer for the Enterprise Activity Model."""

from __future__ import annotations

from html import escape

from .model import EamCell, EamFinding, EamModel

_HEAT = {
    "low": ("#14532d", "#22c55e"),
    "medium": ("#78350f", "#f59e0b"),
    "high": ("#7f1d1d", "#ef4444"),
}


def render_risk_heat_svg(model: EamModel) -> str:
    """Render domain x lifecycle risk and coverage heat as deterministic SVG."""

    left = 240
    top = 140
    col_w = 154
    row_h = 92
    width = left + (len(model.lifecycle_stages) * col_w) + 64
    height = top + (len(model.domains) * row_h) + 126
    risk_by_cell = _cell_risk(model)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" '
        'aria-label="Enterprise Activity Model Risk and Coverage Heat View">',
        f'<rect width="{width}" height="{height}" fill="#0f172a"/>',
        _header(model, width),
        *_column_headers(model, left, top, col_w),
        *_rows(model, left, top, col_w, row_h, risk_by_cell),
        _legend(width, height),
        "</svg>",
    ]
    return "\n".join(parts)


def _cell_risk(model: EamModel) -> dict[tuple[str, str], tuple[int, list[str]]]:
    node_to_findings: dict[str, list[EamFinding]] = {}
    for finding in model.findings:
        for node_id in finding.node_ids:
            node_to_findings.setdefault(node_id, []).append(finding)
    rows: dict[tuple[str, str], tuple[int, list[str]]] = {}
    for cell in model.cells:
        score = 45 if cell.is_gap else 8
        reasons = ["coverage gap"] if cell.is_gap else ["evidence present"]
        linked_findings = _findings_for_cell(cell, node_to_findings)
        if linked_findings:
            reasons = []
        for finding in linked_findings:
            if finding.finding_type == "clash":
                score += 42
            elif finding.finding_type == "overlap":
                score += 24
            else:
                score += 18
            if finding.severity == "high":
                score += 14
            elif finding.severity == "medium":
                score += 8
            reasons.append(finding.finding_type)
        rows[(cell.domain_id, cell.lifecycle_id)] = (min(100, score), sorted(set(reasons)))
    return rows


def _findings_for_cell(cell: EamCell, node_to_findings: dict[str, list[EamFinding]]) -> list[EamFinding]:
    findings: dict[str, EamFinding] = {}
    for node_id in cell.node_ids:
        for finding in node_to_findings.get(node_id, []):
            findings[finding.id] = finding
    return list(findings.values())


def _header(model: EamModel, width: int) -> str:
    return f"""<rect x="24" y="24" width="{width - 48}" height="84" rx="16" fill="#111827" stroke="#334155"/>
<text x="48" y="58" fill="#f8fafc" font-family="Inter, Arial, sans-serif" font-size="25" font-weight="700">
  Risk and Coverage Heat View
</text>
<text x="48" y="87" fill="#cbd5e1" font-family="Inter, Arial, sans-serif" font-size="15">
  Heat combines missing coverage, gap / overlap / clash signals and finding severity across {model.process_count} process nodes.
</text>
<text x="{width - 285}" y="60" fill="#ec4899" font-family="Inter, Arial, sans-serif" font-size="17" font-weight="700">
  {model.finding_counts.get("clash", 0)} clashes
</text>
<text x="{width - 285}" y="86" fill="#f59e0b" font-family="Inter, Arial, sans-serif" font-size="13">
  {model.finding_counts.get("gap", 0)} gaps / {model.finding_counts.get("overlap", 0)} overlaps
</text>"""


def _column_headers(model: EamModel, left: int, top: int, col_w: int) -> list[str]:
    rows = []
    for index, stage in enumerate(model.lifecycle_stages):
        x = left + (index * col_w)
        rows.append(
            f'<text x="{x + (col_w / 2):.1f}" y="{top - 18}" text-anchor="middle" fill="#e2e8f0" '
            f'font-family="Inter, Arial, sans-serif" font-size="12" font-weight="700">{escape(stage.label)}</text>'
        )
    return rows


def _rows(
    model: EamModel,
    left: int,
    top: int,
    col_w: int,
    row_h: int,
    risk_by_cell: dict[tuple[str, str], tuple[int, list[str]]],
) -> list[str]:
    rows: list[str] = []
    coverage_by_domain = {domain.domain_id: domain for domain in model.coverage.domains}
    for domain_index, domain in enumerate(model.domains):
        y = top + (domain_index * row_h)
        coverage = coverage_by_domain.get(domain.id)
        status = coverage.status if coverage else "uncovered"
        rows.append(f'<rect x="24" y="{y}" width="192" height="{row_h - 12}" rx="13" fill="#111827" stroke="#334155"/>')
        rows.append(
            f'<text x="42" y="{y + 30}" fill="#f8fafc" font-family="Inter, Arial, sans-serif" '
            f'font-size="12" font-weight="700">{escape(_truncate(domain.label, 27))}</text>'
        )
        rows.append(
            f'<text x="42" y="{y + 54}" fill="#94a3b8" font-family="Inter, Arial, sans-serif" font-size="11">'
            f'{escape(status)} / {coverage.node_count if coverage else 0} nodes</text>'
        )
        for stage_index, stage in enumerate(model.lifecycle_stages):
            x = left + (stage_index * col_w)
            score, reasons = risk_by_cell[(domain.id, stage.id)]
            band = _risk_band(score)
            fill, stroke = _HEAT[band]
            cell = next(item for item in model.cells if item.domain_id == domain.id and item.lifecycle_id == stage.id)
            rows.append(
                f'<g data-cell-id="{escape(domain.id)}:{escape(stage.id)}" data-risk-band="{band}">'
                f'<rect x="{x}" y="{y}" width="{col_w - 12}" height="{row_h - 12}" rx="13" fill="{fill}" '
                f'stroke="{stroke}" stroke-width="2" opacity="0.92"/>'
                f'<text x="{x + 14}" y="{y + 29}" fill="#f8fafc" font-family="Inter, Arial, sans-serif" '
                f'font-size="18" font-weight="800">{score}</text>'
                f'<text x="{x + 14}" y="{y + 51}" fill="#e2e8f0" font-family="Inter, Arial, sans-serif" font-size="10">'
                f'{len(cell.node_ids)} nodes</text>'
                f'<text x="{x + 14}" y="{y + 69}" fill="#cbd5e1" font-family="Inter, Arial, sans-serif" font-size="9">'
                f'{escape(_truncate(", ".join(reasons), 20))}</text>'
                "</g>"
            )
    return rows


def _risk_band(score: int) -> str:
    if score >= 70:
        return "high"
    if score >= 35:
        return "medium"
    return "low"


def _legend(width: int, height: int) -> str:
    x = 24
    y = height - 64
    return f"""<g>
  <rect x="{x}" y="{y}" width="{width - 48}" height="40" rx="13" fill="#111827" stroke="#334155"/>
  {_legend_box(x + 24, y + 12, "#14532d", "#22c55e", x + 54, y + 26, "low risk / evidence present")}
  {_legend_box(x + 250, y + 12, "#78350f", "#f59e0b", x + 280, y + 26, "medium risk / coverage gap")}
  {_legend_box(x + 500, y + 12, "#7f1d1d", "#ef4444", x + 530, y + 26, "high risk / clash signal")}
</g>"""


def _legend_box(x: int, y: int, fill: str, stroke: str, text_x: int, text_y: int, label: str) -> str:
    return (
        f'<rect x="{x}" y="{y}" width="18" height="18" rx="5" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
        f'<text x="{text_x}" y="{text_y}" fill="#cbd5e1" font-family="Inter, Arial, sans-serif" font-size="12">'
        f"{escape(label)}</text>"
    )


def _truncate(value: str, length: int) -> str:
    if len(value) <= length:
        return value
    return value[: length - 1].rstrip() + "..."
