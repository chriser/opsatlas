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

TOP_MARGIN = 88
ROW_GAP = 190
SYSTEM_X = 86
PROCESS_X = 470
WHO_X = 820
TASK_WIDTH = 235
TASK_HEIGHT = 108
EVENT_WIDTH = 245
EVENT_HEIGHT = 126
ROLE_WIDTH = 235
ROLE_HEIGHT = 92
SYSTEM_WIDTH = 230
SYSTEM_HEIGHT = 82
GATEWAY_SIZE = 66
SUPPORT_STACK_GAP = 18
SUPPORT_NODE_TYPES = {"system", "control", "risk", "annotation"}
FLOW_NODE_TYPES = {"start", "end", "task", "gateway"}


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
        f"<title>{_escape(chart.title)}</title>",
        "<defs>",
        '<marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">',
        '<path d="M0,0 L0,6 L9,3 z" fill="#374151" />',
        "</marker>",
        "</defs>",
        '<rect width="100%" height="100%" fill="#ffffff" />',
    ]
    for edge in chart.edges:
        parts.append(_edge_svg(edge))
    for node in chart.nodes:
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
    lane_order: list[str] = []
    generated_ids: set[str] = set()
    id_map: dict[str, str] = {}

    def add_lane(lane_id: str) -> None:
        if lane_id not in lane_ids:
            lane_ids.add(lane_id)
            lane_order.append(lane_id)

    for index, node in enumerate(model.nodes, start=1):
        original_id = node.id or node.label or f"node_{index}"
        node_id = _safe_id(original_id, generated_ids)
        id_map[original_id] = node_id
        if node.id:
            id_map[node.id] = node_id
        generated_ids.add(node_id)
        if node.type == "lane":
            add_lane(node_id)
            cleaned_nodes.append(node.model_copy(update={"id": node_id, "lane": node_id}))
            continue
        lane = _normalise_id(node.lane) if node.lane else "process"
        add_lane(lane)
        cleaned_nodes.append(node.model_copy(update={"id": node_id, "lane": lane}))

    existing_lane_nodes = {node.id for node in cleaned_nodes if node.type == "lane"}
    explicit_lane_nodes = [node for node in cleaned_nodes if node.type == "lane"]
    lane_nodes = [
        ProcessChartNodeInput(id=lane_id, type="lane", label=_label_from_id(lane_id), lane=lane_id)
        for lane_id in lane_order
        if lane_id not in existing_lane_nodes
    ]
    primary_nodes = [
        node for node in cleaned_nodes
        if node.type != "lane" and node.type not in SUPPORT_NODE_TYPES
    ]
    support_nodes = [node for node in cleaned_nodes if node.type in SUPPORT_NODE_TYPES]
    if primary_nodes and primary_nodes[0].type != "start":
        lane = primary_nodes[0].lane or "process"
        primary_nodes.insert(0, ProcessChartNodeInput(id="start", type="start", label="Start", lane=lane))
    if primary_nodes and primary_nodes[-1].type != "end":
        lane = primary_nodes[-1].lane or "process"
        primary_nodes.append(ProcessChartNodeInput(id="end", type="end", label="End", lane=lane))

    edge_inputs = [
        edge.model_copy(update={
            "from_node": id_map.get(edge.from_node, _normalise_id(edge.from_node)),
            "to_node": id_map.get(edge.to_node, _normalise_id(edge.to_node)),
        })
        for edge in model.edges
    ]
    if not edge_inputs:
        edge_inputs = [
            ProcessChartEdgeInput(id=f"edge_{index}", **{"from": primary_nodes[index - 1].id, "to": primary_nodes[index].id})
            for index in range(1, len(primary_nodes))
        ]
    elif primary_nodes:
        first = primary_nodes[0]
        second = primary_nodes[1] if len(primary_nodes) > 1 else None
        penultimate = primary_nodes[-2] if len(primary_nodes) > 1 else None
        last = primary_nodes[-1]
        referenced_from = {edge.from_node for edge in edge_inputs}
        referenced_to = {edge.to_node for edge in edge_inputs}
        if second and first.id not in referenced_from and first.id not in referenced_to:
            edge_inputs.insert(0, ProcessChartEdgeInput(id="edge_start", **{"from": first.id, "to": second.id, "label": "begin"}))
        if penultimate and last.id not in referenced_from and last.id not in referenced_to:
            edge_inputs.append(ProcessChartEdgeInput(id="edge_end", **{"from": penultimate.id, "to": last.id, "label": "complete"}))

    return ProcessModelInput(
        title=model.title,
        nodes=[*explicit_lane_nodes, *lane_nodes, *primary_nodes, *support_nodes],
        edges=edge_inputs,
    )


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
    primary_inputs = [node for node in model.nodes if node.type in FLOW_NODE_TYPES]
    support_inputs = [node for node in model.nodes if node.type in SUPPORT_NODE_TYPES]
    nodes: list[DiagramNode] = []
    primary_by_id: dict[str, DiagramNode] = {}

    for index, node in enumerate(primary_inputs):
        width, height = _node_size(node.type)
        x = PROCESS_X + (TASK_WIDTH - width) // 2
        y = TOP_MARGIN + index * ROW_GAP
        diagram_node = DiagramNode(
            id=node.id,
            type=node.type,
            label=node.label,
            lane=node.lane,
            x=x,
            y=y,
            width=width,
            height=height,
            metadata=node.metadata,
        )
        nodes.append(diagram_node)
        primary_by_id[node.id] = diagram_node

        who_label = _who_label_for(model.nodes, node.lane)
        if node.type == "task" and who_label:
            nodes.append(DiagramNode(
                id=f"who_{node.id}",
                type="who",
                label=who_label,
                lane=node.lane,
                x=WHO_X,
                y=y + (height - ROLE_HEIGHT) // 2,
                width=ROLE_WIDTH,
                height=ROLE_HEIGHT,
                metadata={"anchor_id": node.id},
            ))

    support_groups = _support_groups(model, support_inputs, primary_inputs)
    for anchor_id, grouped_support in support_groups.items():
        anchor = primary_by_id.get(anchor_id)
        if anchor is None:
            continue
        for index, node in enumerate(grouped_support):
            width, height = _node_size(node.type)
            offset = round((index - (len(grouped_support) - 1) / 2) * (height + SUPPORT_STACK_GAP))
            metadata = {**node.metadata, "anchor_id": anchor_id}
            nodes.append(DiagramNode(
                id=node.id,
                type=node.type,
                label=node.label,
                lane=node.lane,
                x=SYSTEM_X,
                y=anchor.y + anchor.height // 2 - height // 2 + offset,
                width=width,
                height=height,
                metadata=metadata,
            ))

    return nodes


def _layout_edges(model: ProcessModelInput, nodes: list[DiagramNode]) -> list[DiagramEdge]:
    by_id = {node.id: node for node in nodes}
    edges: list[DiagramEdge] = []
    for index, edge in enumerate(model.edges, start=1):
        if edge.from_node not in by_id or edge.to_node not in by_id:
            continue
        source = by_id[edge.from_node]
        target = by_id[edge.to_node]
        edges.append(
            DiagramEdge(
                id=edge.id or f"edge_{index}",
                **{"from": edge.from_node, "to": edge.to_node},
                label=edge.label,
                type=edge.type,
                points=_edge_points(source, target),
            )
        )
    for node in nodes:
        if node.type != "who":
            continue
        anchor_id = node.metadata.get("anchor_id", "")
        anchor = by_id.get(anchor_id)
        if anchor is None:
            continue
        edges.append(DiagramEdge(
            id=f"edge_{anchor_id}_{node.id}",
            **{"from": anchor_id, "to": node.id},
            label="",
            type="association",
            points=_edge_points(anchor, node),
        ))
    return edges


def _animation_steps(nodes: list[DiagramNode], edges: list[DiagramEdge]) -> list[AnimationStep]:
    steps: list[AnimationStep] = []
    for node in nodes:
        action = "draw_node"
        narration = f"Add {node.type} {node.label}."
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


def _lane_label(nodes: list[ProcessChartNodeInput], lane_id: str) -> str:
    explicit = next((node.label for node in nodes if node.type == "lane" and node.id == lane_id), "")
    return explicit or _label_from_id(lane_id)


def _node_size(node_type: str) -> tuple[int, int]:
    if node_type == "gateway":
        return GATEWAY_SIZE, GATEWAY_SIZE
    if node_type in {"start", "end"}:
        return EVENT_WIDTH, EVENT_HEIGHT
    if node_type == "who":
        return ROLE_WIDTH, ROLE_HEIGHT
    if node_type in SUPPORT_NODE_TYPES:
        return SYSTEM_WIDTH, SYSTEM_HEIGHT
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
    if re.match(r"^(?:if|when|whether)\b", compact, re.IGNORECASE):
        return "process"
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


def _node_svg(node: DiagramNode) -> str:
    if node.type in {"start", "end"}:
        return _event_svg(node)
    if node.type == "gateway":
        return _gateway_svg(node)
    if node.type in {"lane", "who"}:
        return _who_svg(node)
    if node.type == "system":
        return _system_svg(node)
    if node.type in {"control", "risk", "annotation"}:
        return _support_svg(node)
    return _process_step_svg(node)


def _event_svg(node: DiagramNode) -> str:
    cut = 42
    points = " ".join([
        f"{node.x + cut},{node.y}",
        f"{node.x + node.width - cut},{node.y}",
        f"{node.x + node.width},{node.y + node.height // 2}",
        f"{node.x + node.width - cut},{node.y + node.height}",
        f"{node.x + cut},{node.y + node.height}",
        f"{node.x},{node.y + node.height // 2}",
    ])
    return "\n".join([
        f'<polygon points="{points}" fill="#ffffff" stroke="#b126e8" stroke-width="5" stroke-linejoin="round" />',
        *_center_text_svg(node.label, node.x + node.width // 2, node.y + node.height // 2, max_chars=18, font_size=18),
    ])


def _gateway_svg(node: DiagramNode) -> str:
    cx = node.x + node.width // 2
    cy = node.y + node.height // 2
    radius = node.width // 2
    top_left = f'x1="{cx - radius + 13}" y1="{cy - radius + 13}"'
    top_right = f'x1="{cx + radius - 13}" y1="{cy - radius + 13}"'
    bottom_left = f'x2="{cx - radius + 13}" y2="{cy + radius - 13}"'
    bottom_right = f'x2="{cx + radius - 13}" y2="{cy + radius - 13}"'
    return "\n".join([
        f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="#ffffff" stroke="#374151" stroke-width="2" />',
        f'<line {top_left} {bottom_right} stroke="#374151" stroke-width="2" />',
        f'<line {top_right} {bottom_left} stroke="#374151" stroke-width="2" />',
    ])


def _process_step_svg(node: DiagramNode) -> str:
    return "\n".join([
        (
            f'<rect x="{node.x}" y="{node.y}" width="{node.width}" height="{node.height}" '
            f'rx="10" fill="#ffffff" stroke="#50c463" stroke-width="4" />'
        ),
        *_center_text_svg(node.label, node.x + node.width // 2, node.y + node.height // 2, max_chars=18, font_size=18),
    ])


def _who_svg(node: DiagramNode) -> str:
    return _tab_card_svg(node, stroke="#ffdd33", max_chars=18)


def _system_svg(node: DiagramNode) -> str:
    return _tab_card_svg(node, stroke="#66adff", max_chars=17)


def _support_svg(node: DiagramNode) -> str:
    stroke = {
        "control": "#f59e0b",
        "risk": "#ef4444",
        "annotation": "#9ca3af",
    }.get(node.type, "#9ca3af")
    dash = ' stroke-dasharray="7 6"' if node.type in {"control", "risk", "annotation"} else ""
    return "\n".join([
        (
            f'<rect x="{node.x}" y="{node.y}" width="{node.width}" height="{node.height}" rx="10" '
            f'fill="#ffffff" stroke="{stroke}" stroke-width="4"{dash} />'
        ),
        *_center_text_svg(node.label, node.x + node.width // 2, node.y + node.height // 2, max_chars=17, font_size=17),
    ])


def _tab_card_svg(node: DiagramNode, *, stroke: str, max_chars: int) -> str:
    tab_x = node.x + 28
    header_y = node.y + 27
    return "\n".join([
        (
            f'<rect x="{node.x}" y="{node.y}" width="{node.width}" height="{node.height}" '
            f'rx="10" fill="#ffffff" stroke="{stroke}" stroke-width="4" />'
        ),
        f'<line x1="{tab_x}" y1="{node.y}" x2="{tab_x}" y2="{node.y + node.height}" stroke="{stroke}" stroke-width="4" />',
        f'<line x1="{node.x}" y1="{header_y}" x2="{node.x + node.width}" y2="{header_y}" stroke="{stroke}" stroke-width="4" />',
        *_center_text_svg(node.label, node.x + node.width // 2 + 12, node.y + node.height // 2 + 8, max_chars=max_chars, font_size=17),
    ])


def _edge_points(source: DiagramNode, target: DiagramNode) -> list[DiagramPoint]:
    source_center_x = source.x + source.width // 2
    source_center_y = source.y + source.height // 2
    target_center_x = target.x + target.width // 2
    target_center_y = target.y + target.height // 2
    if abs(source_center_x - target_center_x) < 80:
        return [
            DiagramPoint(x=source_center_x, y=source.y + source.height),
            DiagramPoint(x=target_center_x, y=target.y),
        ]
    if source_center_x < target_center_x:
        start = DiagramPoint(x=source.x + source.width, y=source_center_y)
        end = DiagramPoint(x=target.x, y=target_center_y)
    else:
        start = DiagramPoint(x=source.x, y=source_center_y)
        end = DiagramPoint(x=target.x + target.width, y=target_center_y)
    midpoint_x = start.x + (end.x - start.x) // 2
    return [
        start,
        DiagramPoint(x=midpoint_x, y=start.y),
        DiagramPoint(x=midpoint_x, y=end.y),
        end,
    ]


def _support_groups(
    model: ProcessModelInput,
    support_inputs: list[ProcessChartNodeInput],
    primary_inputs: list[ProcessChartNodeInput],
) -> dict[str, list[ProcessChartNodeInput]]:
    if not primary_inputs:
        return {}
    primary_ids = {node.id for node in primary_inputs}
    primary_order = [node.id for node in primary_inputs]
    groups: dict[str, list[ProcessChartNodeInput]] = defaultdict(list)
    for index, node in enumerate(support_inputs):
        anchor_id = _support_anchor_id(node.id, primary_ids, model.edges)
        if not anchor_id:
            anchor_id = primary_order[min(index, len(primary_order) - 1)]
        groups[anchor_id].append(node)
    return groups


def _support_anchor_id(
    node_id: str,
    primary_ids: set[str],
    edges: list[ProcessChartEdgeInput],
) -> str:
    for edge in edges:
        if edge.from_node == node_id and edge.to_node in primary_ids:
            return edge.to_node
        if edge.to_node == node_id and edge.from_node in primary_ids:
            return edge.from_node
    return ""


def _who_label_for(nodes: list[ProcessChartNodeInput], lane_id: str) -> str:
    support_lanes = {"process", "systems", "controls", "risks", "annotations", "data", "documents"}
    if not lane_id or lane_id in SUPPORT_NODE_TYPES or lane_id in support_lanes:
        return ""
    return _lane_label(nodes, lane_id)


def _center_text_svg(value: str, x: int, center_y: int, *, max_chars: int, font_size: int) -> list[str]:
    lines = _wrap_lines(value, max_chars=max_chars)
    line_height = font_size + 7
    first_y = center_y - ((len(lines) - 1) * line_height) // 2 + font_size // 3
    return [
        (
            f'<text x="{x}" y="{first_y + index * line_height}" text-anchor="middle" fill="#111827" '
            f'font-family="Arial" font-size="{font_size}" font-weight="400">{_escape(line)}</text>'
        )
        for index, line in enumerate(lines[:4])
    ]


def _wrap_lines(value: str, *, max_chars: int) -> list[str]:
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
    return lines or [value]


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


def _escape(value: str) -> str:
    return html.escape(value, quote=True)
