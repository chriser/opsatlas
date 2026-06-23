"""Local process diagram generation, validation, layout and rendering."""

from __future__ import annotations

import hashlib
import html
import re
from collections import defaultdict

from .models import (
    AnimationStep,
    DiagramEdge,
    DiagramNode,
    DiagramPoint,
    ProcessChartEdgeInput,
    ProcessChartNodeInput,
    ProcessChartRenderRequest,
    ProcessChartRenderResponse,
    ProcessModelInput,
)

LANE_HEIGHT = 150
LANE_GAP = 18
LEFT_MARGIN = 48
TOP_MARGIN = 64
NODE_X_START = 190
NODE_X_GAP = 190
TASK_WIDTH = 150
TASK_HEIGHT = 66
GATEWAY_SIZE = 92


class DiagramValidationError(ValueError):
    """Raised when a process model cannot be safely rendered."""


def render_process_chart(request: ProcessChartRenderRequest) -> ProcessChartRenderResponse:
    model, warnings = _normalise_input(request)
    _validate_model(model)
    nodes = _layout_nodes(model)
    edges = _layout_edges(model, nodes)
    animation_steps = _animation_steps(nodes, edges) if request.animation else []
    return ProcessChartRenderResponse(
        chart_id=_chart_id(model),
        title=model.title,
        style=request.style,
        format=request.format,
        nodes=nodes,
        edges=edges,
        animation_steps=animation_steps,
        narration_script=[step.narration for step in animation_steps],
        warnings=warnings,
    )


def render_svg(chart: ProcessChartRenderResponse) -> str:
    width = max((node.x + node.width + 56 for node in chart.nodes), default=900)
    height = max((node.y + node.height + 56 for node in chart.nodes), default=500)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<defs>",
        '<marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">',
        '<path d="M0,0 L0,6 L9,3 z" fill="#334155" />',
        "</marker>",
        "</defs>",
        '<rect width="100%" height="100%" fill="#f8fafc" />',
        f'<text x="48" y="34" fill="#0f172a" font-family="Arial" font-size="20" font-weight="700">{_escape(chart.title)}</text>',
    ]
    lane_nodes = [node for node in chart.nodes if node.type == "lane"]
    other_nodes = [node for node in chart.nodes if node.type != "lane"]
    for node in lane_nodes:
        parts.append(_lane_svg(node))
    for edge in chart.edges:
        parts.append(_edge_svg(edge))
    for node in other_nodes:
        parts.append(_node_svg(node))
    parts.append("</svg>")
    return "\n".join(parts)


def _normalise_input(request: ProcessChartRenderRequest) -> tuple[ProcessModelInput, list[str]]:
    warnings: list[str] = []
    if request.process_model and request.process_model.nodes:
        model = request.process_model
        if request.narrative:
            warnings.append("Structured process_model supplied; narrative was retained only as context.")
    else:
        model = _model_from_narrative(request.narrative)
        warnings.append("Narrative was converted with deterministic local heuristics; review before production use.")
    return _with_defaults(model), warnings


def _model_from_narrative(narrative: str) -> ProcessModelInput:
    text = re.sub(r"\s+", " ", narrative).strip()
    if not text:
        raise DiagramValidationError("Either narrative or process_model.nodes must be supplied.")
    title = _title_from_text(text)
    clauses = [
        clause.strip(" .")
        for clause in re.split(r"(?:\.|;|\bthen\b|\bnext\b|\bafter that\b)", text, flags=re.IGNORECASE)
        if clause.strip(" .")
    ]
    nodes: list[ProcessChartNodeInput] = []
    for index, clause in enumerate(clauses[:12], start=1):
        lane = _lane_from_clause(clause)
        node_type = "gateway" if _looks_like_gateway(clause) else "task"
        nodes.append(ProcessChartNodeInput(id=f"step_{index}", type=node_type, label=_clean_label(clause), lane=lane))
    edges = [
        ProcessChartEdgeInput(id=f"edge_{index}", **{"from": nodes[index - 1].id, "to": nodes[index].id, "label": "next"})
        for index in range(1, len(nodes))
    ]
    return ProcessModelInput(title=title, nodes=nodes, edges=edges)


def _with_defaults(model: ProcessModelInput) -> ProcessModelInput:
    cleaned_nodes: list[ProcessChartNodeInput] = []
    lane_ids: set[str] = set()
    generated_ids: set[str] = set()
    id_map: dict[str, str] = {}
    for index, node in enumerate(model.nodes, start=1):
        original_id = node.id or node.label or f"node_{index}"
        node_id = _safe_id(original_id, generated_ids)
        id_map[original_id] = node_id
        if node.id:
            id_map[node.id] = node_id
        generated_ids.add(node_id)
        if node.type == "lane":
            lane_ids.add(node_id)
            cleaned_nodes.append(node.model_copy(update={"id": node_id, "lane": node_id}))
            continue
        lane = _normalise_id(node.lane) if node.lane else "process"
        lane_ids.add(lane)
        cleaned_nodes.append(node.model_copy(update={"id": node_id, "lane": lane}))

    existing_lane_nodes = {node.id for node in cleaned_nodes if node.type == "lane"}
    explicit_lane_nodes = [node for node in cleaned_nodes if node.type == "lane"]
    lane_nodes = [
        ProcessChartNodeInput(id=lane_id, type="lane", label=_label_from_id(lane_id), lane=lane_id)
        for lane_id in sorted(lane_ids - existing_lane_nodes)
    ]
    flow_nodes = [node for node in cleaned_nodes if node.type != "lane"]
    if flow_nodes and flow_nodes[0].type != "start":
        lane = flow_nodes[0].lane or "process"
        flow_nodes.insert(0, ProcessChartNodeInput(id="start", type="start", label="Start", lane=lane))
    if flow_nodes and flow_nodes[-1].type != "end":
        lane = flow_nodes[-1].lane or "process"
        flow_nodes.append(ProcessChartNodeInput(id="end", type="end", label="End", lane=lane))

    edge_inputs = [
        edge.model_copy(update={
            "from_node": id_map.get(edge.from_node, _normalise_id(edge.from_node)),
            "to_node": id_map.get(edge.to_node, _normalise_id(edge.to_node)),
        })
        for edge in model.edges
    ]
    if not edge_inputs:
        edge_inputs = [
            ProcessChartEdgeInput(id=f"edge_{index}", **{"from": flow_nodes[index - 1].id, "to": flow_nodes[index].id})
            for index in range(1, len(flow_nodes))
        ]
    elif flow_nodes:
        first = flow_nodes[0]
        second = flow_nodes[1] if len(flow_nodes) > 1 else None
        penultimate = flow_nodes[-2] if len(flow_nodes) > 1 else None
        last = flow_nodes[-1]
        referenced_from = {edge.from_node for edge in edge_inputs}
        referenced_to = {edge.to_node for edge in edge_inputs}
        if second and first.id not in referenced_from and first.id not in referenced_to:
            edge_inputs.insert(0, ProcessChartEdgeInput(id="edge_start", **{"from": first.id, "to": second.id, "label": "begin"}))
        if penultimate and last.id not in referenced_from and last.id not in referenced_to:
            edge_inputs.append(ProcessChartEdgeInput(id="edge_end", **{"from": penultimate.id, "to": last.id, "label": "complete"}))

    return ProcessModelInput(title=model.title, nodes=[*explicit_lane_nodes, *lane_nodes, *flow_nodes], edges=edge_inputs)


def _validate_model(model: ProcessModelInput) -> None:
    if not model.nodes:
        raise DiagramValidationError("Process model must include at least one node.")
    seen: set[str] = set()
    for node in model.nodes:
        if not node.id:
            raise DiagramValidationError("Every node must have an id.")
        if node.id in seen:
            raise DiagramValidationError(f"Duplicate node id: {node.id}.")
        if not node.label.strip():
            raise DiagramValidationError(f"Node {node.id} must have a readable label.")
        seen.add(node.id)
    renderable_ids = {node.id for node in model.nodes if node.type != "lane"}
    for edge in model.edges:
        if edge.from_node not in renderable_ids:
            raise DiagramValidationError(f"Edge {edge.id or edge.from_node} references unknown from node: {edge.from_node}.")
        if edge.to_node not in renderable_ids:
            raise DiagramValidationError(f"Edge {edge.id or edge.to_node} references unknown to node: {edge.to_node}.")


def _layout_nodes(model: ProcessModelInput) -> list[DiagramNode]:
    flow_nodes = [node for node in model.nodes if node.type != "lane"]
    lane_ids = _ordered_lanes(model.nodes)
    lane_width = max(920, NODE_X_START + (max(1, len(flow_nodes)) - 1) * NODE_X_GAP + TASK_WIDTH + 70)
    lane_y = {
        lane_id: TOP_MARGIN + index * (LANE_HEIGHT + LANE_GAP)
        for index, lane_id in enumerate(lane_ids)
    }
    nodes: list[DiagramNode] = [
        DiagramNode(
            id=lane_id,
            type="lane",
            label=_lane_label(model.nodes, lane_id),
            lane=lane_id,
            x=LEFT_MARGIN,
            y=lane_y[lane_id],
            width=lane_width,
            height=LANE_HEIGHT,
        )
        for lane_id in lane_ids
    ]
    lane_counts: dict[str, int] = defaultdict(int)
    for node in flow_nodes:
        lane = node.lane or lane_ids[0]
        lane_counts[lane] += 1
        order = lane_counts[lane] - 1
        width, height = _node_size(node.type)
        x = NODE_X_START + order * NODE_X_GAP
        y = lane_y[lane] + (LANE_HEIGHT - height) // 2
        nodes.append(
            DiagramNode(
                id=node.id,
                type=node.type,
                label=node.label,
                lane=lane,
                x=x,
                y=y,
                width=width,
                height=height,
                metadata=node.metadata,
            )
        )
    return nodes


def _layout_edges(model: ProcessModelInput, nodes: list[DiagramNode]) -> list[DiagramEdge]:
    by_id = {node.id: node for node in nodes}
    edges: list[DiagramEdge] = []
    for index, edge in enumerate(model.edges, start=1):
        source = by_id[edge.from_node]
        target = by_id[edge.to_node]
        start = DiagramPoint(x=source.x + source.width, y=source.y + source.height // 2)
        end = DiagramPoint(x=target.x, y=target.y + target.height // 2)
        midpoint_x = start.x + max(24, (end.x - start.x) // 2)
        points = [
            start,
            DiagramPoint(x=midpoint_x, y=start.y),
            DiagramPoint(x=midpoint_x, y=end.y),
            end,
        ]
        edges.append(
            DiagramEdge(
                id=edge.id or f"edge_{index}",
                **{"from": edge.from_node, "to": edge.to_node},
                label=edge.label,
                type=edge.type,
                points=points,
            )
        )
    return edges


def _animation_steps(nodes: list[DiagramNode], edges: list[DiagramEdge]) -> list[AnimationStep]:
    steps: list[AnimationStep] = []
    for node in nodes:
        action = "draw_lane" if node.type == "lane" else "draw_node"
        narration = f"Add lane {node.label}." if node.type == "lane" else f"Add {node.type} {node.label}."
        steps.append(AnimationStep(step=len(steps) + 1, action=action, target_id=node.id, label=node.label, narration=narration))
    for edge in edges:
        label = edge.label or "next"
        steps.append(AnimationStep(
            step=len(steps) + 1,
            action="draw_edge",
            target_id=edge.id,
            label=label,
            narration=f"Connect via {label}.",
        ))
    return steps


def _ordered_lanes(nodes: list[ProcessChartNodeInput]) -> list[str]:
    lanes: list[str] = []
    for node in nodes:
        lane = node.id if node.type == "lane" else node.lane
        if lane and lane not in lanes:
            lanes.append(lane)
    return lanes or ["process"]


def _lane_label(nodes: list[ProcessChartNodeInput], lane_id: str) -> str:
    explicit = next((node.label for node in nodes if node.type == "lane" and node.id == lane_id), "")
    return explicit or _label_from_id(lane_id)


def _node_size(node_type: str) -> tuple[int, int]:
    if node_type == "gateway":
        return GATEWAY_SIZE, GATEWAY_SIZE
    if node_type in {"start", "end"}:
        return 76, 76
    if node_type in {"control", "risk", "system"}:
        return 150, 58
    return TASK_WIDTH, TASK_HEIGHT


def _chart_id(model: ProcessModelInput) -> str:
    material = model.model_dump_json(by_alias=True)
    digest = hashlib.sha1(material.encode("utf-8")).hexdigest()[:10]
    return f"{_safe_id(model.title or 'process', set())}-{digest}"


def _title_from_text(text: str) -> str:
    first = re.split(r"[.;]", text, maxsplit=1)[0].strip()
    return _clean_label(first)[:90] or "Generated process"


def _lane_from_clause(clause: str) -> str:
    compact = clause.strip()
    patterns = [
        (
            r"^(?:the\s+)?([A-Z][A-Za-z ]{2,40}?)(?:\s+then)?\s+"
            r"(?:completes?|submits?|reviews?|validates?|approves?|creates?|checks?|sends?)\b"
        ),
        r"\bby\s+(?:the\s+)?([A-Za-z ]{3,40})$",
    ]
    for pattern in patterns:
        match = re.search(pattern, compact)
        if match:
            return _safe_id(match.group(1), set())
    return "process"


def _looks_like_gateway(clause: str) -> bool:
    return bool(re.search(r"\?|\bif\b|\bwhether\b|\bdecision\b|\bcomplete\b", clause, re.IGNORECASE))


def _clean_label(value: str) -> str:
    compact = re.sub(r"\s+", " ", value).strip(" .")
    return compact[:1].upper() + compact[1:] if compact else "Step"


def _safe_id(value: str, existing: set[str]) -> str:
    base = _normalise_id(value)
    candidate = base
    suffix = 2
    while candidate in existing:
        candidate = f"{base}_{suffix}"
        suffix += 1
    return candidate


def _normalise_id(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "node"


def _label_from_id(value: str) -> str:
    return re.sub(r"[_-]+", " ", value).strip().title() or "Process"


def _lane_svg(node: DiagramNode) -> str:
    lane_label = (
        f'<text x="{node.x + 16}" y="{node.y + 34}" fill="#075985" '
        f'font-family="Arial" font-size="13" font-weight="700">{_escape(node.label)}</text>'
    )
    return "\n".join([
        f'<rect x="{node.x}" y="{node.y}" width="{node.width}" height="{node.height}" rx="8" fill="#ffffff" stroke="#cbd5e1" />',
        f'<rect x="{node.x}" y="{node.y}" width="120" height="{node.height}" rx="8" fill="#e0f2fe" stroke="#cbd5e1" />',
        lane_label,
    ])


def _node_svg(node: DiagramNode) -> str:
    if node.type in {"start", "end"}:
        cx = node.x + node.width // 2
        cy = node.y + node.height // 2
        return "\n".join([
            f'<circle cx="{cx}" cy="{cy}" r="{node.width // 2}" fill="#dcfce7" stroke="#16a34a" stroke-width="2" />',
            *_text_svg(node.label, cx, cy - 4, anchor="middle", max_chars=10),
        ])
    if node.type == "gateway":
        cx = node.x + node.width // 2
        cy = node.y + node.height // 2
        points = f"{cx},{node.y} {node.x + node.width},{cy} {cx},{node.y + node.height} {node.x},{cy}"
        return "\n".join([
            f'<polygon points="{points}" fill="#fef3c7" stroke="#d97706" stroke-width="2" />',
            *_text_svg(node.label, cx, cy - 12, anchor="middle", max_chars=12),
        ])
    fill = {
        "control": "#fef3c7",
        "risk": "#fee2e2",
        "system": "#ede9fe",
        "annotation": "#f1f5f9",
    }.get(node.type, "#eff6ff")
    stroke = {
        "control": "#d97706",
        "risk": "#dc2626",
        "system": "#7c3aed",
        "annotation": "#64748b",
    }.get(node.type, "#2563eb")
    dash = ' stroke-dasharray="5 4"' if node.type in {"control", "risk", "annotation"} else ""
    return "\n".join([
        (
            f'<rect x="{node.x}" y="{node.y}" width="{node.width}" height="{node.height}" '
            f'rx="8" fill="{fill}" stroke="{stroke}" stroke-width="2"{dash} />'
        ),
        *_text_svg(node.label, node.x + node.width // 2, node.y + 20, anchor="middle"),
    ])


def _edge_svg(edge: DiagramEdge) -> str:
    path = " ".join(
        f"{'M' if index == 0 else 'L'} {point.x} {point.y}"
        for index, point in enumerate(edge.points)
    )
    label = ""
    if edge.label:
        midpoint = edge.points[len(edge.points) // 2]
        label = (
            f'<text x="{midpoint.x + 6}" y="{midpoint.y - 6}" fill="#475569" '
            f'font-family="Arial" font-size="11">{_escape(edge.label)}</text>'
        )
    return "\n".join([
        f'<path d="{path}" fill="none" stroke="#334155" stroke-width="2" marker-end="url(#arrow)" />',
        label,
    ])


def _text_svg(value: str, x: int, y: int, *, anchor: str = "start", max_chars: int = 22) -> list[str]:
    words = value.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        if sum(len(item) for item in current) + len(current) + len(word) > max_chars and current:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return [
        (
            f'<text x="{x}" y="{y + index * 14}" text-anchor="{anchor}" fill="#0f172a" '
            f'font-family="Arial" font-size="12" font-weight="700">{_escape(line)}</text>'
        )
        for index, line in enumerate(lines[:4])
    ]


def _escape(value: str) -> str:
    return html.escape(value, quote=True)
