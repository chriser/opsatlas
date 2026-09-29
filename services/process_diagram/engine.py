"""Local process diagram generation, validation, layout and rendering."""

from __future__ import annotations

import hashlib
import html
import re
from collections import defaultdict

from .layout import FLOW_TYPES, LEFT_SUPPORT, OUTSIDE_ROLES, apply_notation, gateway_kind, place
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
LEFT_MARGIN = 40
TASK_WIDTH = 280
TASK_HEIGHT = 112
EVENT_WIDTH = 240
EVENT_HEIGHT = 104
ROLE_WIDTH = 220
ROLE_HEIGHT = 80
SYSTEM_WIDTH = 220
SYSTEM_HEIGHT = 80
GATEWAY_SIZE = 60
SIDE_GAP = 44      # between a step and the boxes beside it
COLUMN_GAP = 64    # between one path's column and the next
ROW_GAP = 64
CELL_WIDTH = SYSTEM_WIDTH + SIDE_GAP + TASK_WIDTH + SIDE_GAP + ROLE_WIDTH + COLUMN_GAP
FIRST_CENTER = LEFT_MARGIN + SYSTEM_WIDTH + SIDE_GAP + TASK_WIDTH // 2
SUPPORT_STACK_GAP = 14
SUPPORT_NODE_TYPES = LEFT_SUPPORT
FLOW_NODE_TYPES = FLOW_TYPES
TEXT_WIDTH_FACTOR = 0.56
GATEWAY_NAMES = {"xor": "XOR", "and": "AND", "or": "ANY"}


class DiagramValidationError(ValueError):
    """Raised when a process model cannot be safely rendered."""


def render_process_chart(request: ProcessChartRenderRequest) -> ProcessChartRenderResponse:
    model, warnings = _normalise_input(request)
    _validate_model(model)
    model = apply_notation(model)
    nodes, edges = _layout(model)
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
    # A gateway's question is written beside it.
    width = max((node.x + node.width + (240 if node.type == "gateway" and node.label.strip() else 56) for node in chart.nodes),
                default=900)
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
    primary_nodes = [node for node in cleaned_nodes if node.type in FLOW_NODE_TYPES]
    support_nodes = [node for node in cleaned_nodes if node.type != "lane" and node.type not in FLOW_NODE_TYPES]
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
        if not node.label.strip() and node.type != "gateway":  # a connector needs no words
            raise DiagramValidationError(f"Node {node.id} must have a readable label.")
        seen.add(node.id)
    renderable_ids = {node.id for node in model.nodes if node.type != "lane"}
    for edge in model.edges:
        if edge.from_node not in renderable_ids:
            raise DiagramValidationError(f"Edge {edge.id or edge.from_node} references unknown from node: {edge.from_node}.")
        if edge.to_node not in renderable_ids:
            raise DiagramValidationError(f"Edge {edge.id or edge.to_node} references unknown to node: {edge.to_node}.")


def _layout(model: ProcessModelInput) -> tuple[list[DiagramNode], list[DiagramEdge]]:
    """Each path in its own column (see layout.py); beside each step its system(s) and controls on the left and its
    roles on the right; rows as tall as their tallest step or stack."""
    positions, forward, back, via = place(model)
    by_id = {node.id: node for node in model.nodes}
    roles: dict[str, list[ProcessChartNodeInput]] = defaultdict(list)
    left: dict[str, list[ProcessChartNodeInput]] = defaultdict(list)
    for edge in model.edges:
        a, b = by_id.get(edge.from_node), by_id.get(edge.to_node)
        if a is None or b is None:
            continue
        for support, anchor in ((a, b), (b, a)):
            if anchor.id not in positions:
                continue
            bucket = roles if support.type == "who" else left if support.type in LEFT_SUPPORT else None
            if bucket is not None and all(s.id != support.id for s in bucket[anchor.id]):
                bucket[anchor.id].append(support)
    placed_support = {s.id for group in (*roles.values(), *left.values()) for s in group}
    order = [node.id for node in model.nodes if node.id in positions]
    loose = [node for node in model.nodes if node.type in LEFT_SUPPORT and node.id not in placed_support]
    for index, node in enumerate(loose):
        if order:
            left[order[min(index, len(order) - 1)]].append(node)
    lane_roles: set[str] = set()
    for node in model.nodes:
        if node.type == "task" and node.id in positions and not roles[node.id]:
            label = _who_label_for(model.nodes, node.lane)
            if label:
                roles[node.id].append(ProcessChartNodeInput(id=f"who_{node.id}", type="who", label=label, lane=node.lane))
                lane_roles.add(node.id)

    size = {node_id: _node_size(by_id[node_id].type, by_id[node_id].label) for node_id in positions}

    def stack(group: list[ProcessChartNodeInput]) -> list[tuple[int, int]]:
        return [_node_size(s.type, s.label) for s in group]

    rows: dict[int, int] = defaultdict(int)
    for node_id, (_, row) in positions.items():
        heights = [size[node_id][1]]
        for group in (left[node_id], roles[node_id]):
            sizes = stack(group)
            heights.append(sum(h for _, h in sizes) + SUPPORT_STACK_GAP * max(0, len(sizes) - 1))
        rows[row] = max(rows[row], *heights)
    top: dict[int, int] = {}
    y = TOP_MARGIN
    for row in range(max(rows, default=-1) + 1):
        top[row] = y
        y += rows.get(row, GATEWAY_SIZE) + ROW_GAP

    nodes: list[DiagramNode] = []
    for node_id, (column, row) in sorted(positions.items(), key=lambda item: (item[1][1], item[1][0])):
        node = by_id[node_id]
        width, height = size[node_id]
        center = FIRST_CENTER + column * CELL_WIDTH
        node_y = top[row] + (rows[row] - height) // 2
        metadata = dict(node.metadata)
        if node.type == "gateway":
            metadata["gateway"] = gateway_kind(node)
        nodes.append(DiagramNode(id=node.id, type=node.type, label=node.label, lane=node.lane, x=round(center - width / 2),
                                 y=node_y, width=width, height=height, metadata=metadata))
        middle = node_y + height // 2
        for group, x in ((left[node_id], round(center - TASK_WIDTH / 2 - SIDE_GAP - SYSTEM_WIDTH)),
                         (roles[node_id], round(center + TASK_WIDTH / 2 + SIDE_GAP))):
            sizes = stack(group)
            cursor = middle - (sum(h for _, h in sizes) + SUPPORT_STACK_GAP * max(0, len(sizes) - 1)) // 2
            for support, (support_width, support_height) in zip(group, sizes):
                extra = {"anchor_id": node_id}
                if support.type == "who" and (support.metadata.get("external") == "true"
                                              or support.label.strip().lower() in OUTSIDE_ROLES):
                    extra["external"] = "true"
                nodes.append(DiagramNode(id=support.id, type=support.type, label=support.label, lane=support.lane,
                                         x=x, y=cursor, width=support_width, height=support_height,
                                         metadata={**support.metadata, **extra}))
                cursor += support_height + SUPPORT_STACK_GAP

    placed = {node.id: node for node in nodes}
    splits = {a for a, _ in forward if sum(1 for x, _ in forward if x == a) > 1}
    edges: list[DiagramEdge] = []
    for index, edge in enumerate(model.edges, start=1):
        source, target = placed.get(edge.from_node), placed.get(edge.to_node)
        if source is None or target is None:
            continue
        flow = source.type in FLOW_NODE_TYPES and target.type in FLOW_NODE_TYPES
        key = (edge.from_node, edge.to_node)
        points = (_flow_points(source, target, loop=key in back, split=source.id in splits,
                               via=FIRST_CENTER + via[key] * CELL_WIDTH if key in via else None, beside=nodes)
                  if flow else _edge_points(source, target))
        edges.append(DiagramEdge(id=edge.id or f"edge_{index}", **{"from": edge.from_node, "to": edge.to_node},
                                 label=edge.label, type=edge.type if flow else "association", points=points))
    for node_id in lane_roles:
        anchor, role = placed[node_id], placed[f"who_{node_id}"]
        edges.append(DiagramEdge(id=f"edge_{node_id}_who_{node_id}", **{"from": node_id, "to": role.id}, label="",
                                 type="association", points=_edge_points(anchor, role)))
    return nodes, edges


def _flow_points(source: DiagramNode, target: DiagramNode, *, loop: bool, split: bool, via: float | None,
                 beside: list[DiagramNode] = ()) -> list[DiagramPoint]:
    """Down a column; a split fans out along a bar just below it, paths meet along a bar just above the join; a path
    straight from a split to its join keeps its own column; a loop back runs up beside the columns."""
    sx, tx = source.x + source.width // 2, target.x + target.width // 2
    bottom, top = source.y + source.height, target.y
    if loop or top <= bottom:
        # Out of the bottom into the gap below the row, along it past everything beside the way up, up, and in from
        # above: through gaps only, never across a box.
        below, above = bottom + ROW_GAP // 3, top - ROW_GAP // 3
        alongside = [n.x + n.width for n in beside if n.y < below and n.y + n.height > above]
        route = max([sx, tx, *alongside]) + COLUMN_GAP // 2
        return [DiagramPoint(x=sx, y=bottom), DiagramPoint(x=sx, y=below), DiagramPoint(x=route, y=below),
                DiagramPoint(x=route, y=above), DiagramPoint(x=tx, y=above), DiagramPoint(x=tx, y=top)]
    if via is not None:
        lane = round(via)
        return [DiagramPoint(x=sx, y=bottom), DiagramPoint(x=sx, y=bottom + ROW_GAP // 2),
                DiagramPoint(x=lane, y=bottom + ROW_GAP // 2), DiagramPoint(x=lane, y=top - ROW_GAP // 2),
                DiagramPoint(x=tx, y=top - ROW_GAP // 2), DiagramPoint(x=tx, y=top)]
    if abs(sx - tx) < 2:
        return [DiagramPoint(x=sx, y=bottom), DiagramPoint(x=tx, y=top)]
    bar = bottom + ROW_GAP // 2 if split else top - ROW_GAP // 2
    return [DiagramPoint(x=sx, y=bottom), DiagramPoint(x=sx, y=bar), DiagramPoint(x=tx, y=bar), DiagramPoint(x=tx, y=top)]


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


def _node_size(node_type: str, label: str = "") -> tuple[int, int]:
    if node_type == "gateway":
        return GATEWAY_SIZE, GATEWAY_SIZE
    if node_type in {"start", "end", "event"}:
        # A hexagon: its slanted ends leave less room for text than a box of the same width.
        return EVENT_WIDTH, _text_aware_height(label, EVENT_WIDTH, EVENT_HEIGHT, font_size=16, horizontal_padding=96,
                                               vertical_padding=40)
    if node_type == "who":
        return ROLE_WIDTH, _text_aware_height(
            label,
            ROLE_WIDTH,
            ROLE_HEIGHT,
            font_size=16,
            horizontal_padding=56,
            vertical_padding=44,
        )
    if node_type in SUPPORT_NODE_TYPES:
        return SYSTEM_WIDTH, _text_aware_height(
            label,
            SYSTEM_WIDTH,
            SYSTEM_HEIGHT,
            font_size=16,
            horizontal_padding=56,
            vertical_padding=44,
        )
    return TASK_WIDTH, _text_aware_height(
        label,
        TASK_WIDTH,
        TASK_HEIGHT,
        font_size=16,
        horizontal_padding=36,
        vertical_padding=34,
    )


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
    if node.type in {"start", "end", "event"}:
        return _event_svg(node)
    if node.type == "gateway":
        return _gateway_svg(node)
    if node.type in {"lane", "who"}:
        return _who_svg(node)
    if node.type == "system":
        return _system_svg(node)
    if node.type == "control":
        return _control_svg(node)
    if node.type in {"risk", "annotation"}:
        return _support_svg(node)
    if node.type == "interface":
        return _interface_svg(node)
    if node.type == "automated":
        return _automated_svg(node)
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
    """XOR: only one path followed (a cross); AND: all paths (an upward wedge); ANY: any number (a downward wedge). The
    connector's name sits above it; a split's question, when there is one, beside it."""
    kind = node.metadata.get("gateway", "xor")
    cx = node.x + node.width // 2
    cy = node.y + node.height // 2
    r = node.width // 2
    inset = round(r * 0.42)
    stroke = 'stroke="#374151" stroke-width="2.5" fill="none" stroke-linecap="round"'
    if kind == "and":
        mark = f'<polyline points="{cx - inset},{cy + inset // 2 + 6} {cx},{cy - inset} {cx + inset},{cy + inset // 2 + 6}" {stroke} />'
    elif kind == "or":
        mark = f'<polyline points="{cx - inset},{cy - inset // 2 - 6} {cx},{cy + inset} {cx + inset},{cy - inset // 2 - 6}" {stroke} />'
    else:
        mark = (f'<line x1="{cx - inset}" y1="{cy - inset}" x2="{cx + inset}" y2="{cy + inset}" {stroke} />'
                f'<line x1="{cx + inset}" y1="{cy - inset}" x2="{cx - inset}" y2="{cy + inset}" {stroke} />')
    parts = [
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#ffffff" stroke="#374151" stroke-width="2" />',
        mark,
        (f'<text x="{cx + r + 6}" y="{node.y - 4}" fill="#374151" font-family="Arial" font-size="12" '
         f'font-weight="700">{GATEWAY_NAMES.get(kind, "XOR")}</text>'),
    ]
    if node.label.strip():
        for index, line in enumerate(_wrap_lines(node.label, max_chars=26)[:3]):
            parts.append(f'<text x="{cx + r + 12}" y="{cy + 4 + index * 16}" fill="#475569" font-family="Arial" '
                         f'font-size="13">{_escape(line)}</text>')
    return "\n".join(parts)


def _interface_svg(node: DiagramNode) -> str:
    """Another process this one hands over to: a grey card with a notched right edge and a shadow card behind it, and
    the process's reference above."""
    x, y, w, h, notch = node.x, node.y, node.width, node.height, 18

    def card(dx: int, dy: int, fill: str) -> str:
        points = " ".join([f"{x + dx},{y + dy}", f"{x + dx + w - notch},{y + dy}", f"{x + dx + w},{y + dy + h // 2}",
                           f"{x + dx + w - notch},{y + dy + h}", f"{x + dx},{y + dy + h}"])
        return f'<polygon points="{points}" fill="{fill}" stroke="#6b7280" stroke-width="3" stroke-linejoin="round" />'
    reference = node.metadata.get("reference", "")
    return "\n".join([
        card(14, 14, "#f3f4f6"),
        card(0, 0, "#ffffff"),
        *([f'<text x="{x + w - notch}" y="{y - 8}" text-anchor="end" fill="#374151" font-family="Arial" '
           f'font-size="12">{_escape(reference)}</text>'] if reference else []),
        *_center_text_svg(node.label, x + (w - notch) // 2, y + h // 2, max_chars=_max_chars(w - 56, 16), font_size=16),
    ])


def _automated_svg(node: DiagramNode) -> str:
    """A step a system does on its own: blue, with a small screen in the corner."""
    x, y, w, h = node.x, node.y, node.width, node.height
    return "\n".join([
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="#ffffff" stroke="#3b82f6" stroke-width="4" />',
        f'<rect x="{x + w - 30}" y="{y + h - 24}" width="20" height="14" rx="2" fill="none" stroke="#3b82f6" stroke-width="2" />',
        f'<line x1="{x + w - 24}" y1="{y + h - 7}" x2="{x + w - 16}" y2="{y + h - 7}" stroke="#3b82f6" stroke-width="2" />',
        *_center_text_svg(node.label, x + w // 2, y + h // 2, max_chars=_max_chars(w - 36, 16), font_size=16),
    ])


def _control_svg(node: DiagramNode) -> str:
    """A control performed at the step: a red downward triangle marked C, with what the control is."""
    x, y, h = node.x, node.y, node.height
    cy = y + h // 2
    triangle = f"{x + 4},{cy - 20} {x + 48},{cy - 20} {x + 26},{cy + 20}"
    text_left = x + 58
    return "\n".join([
        f'<polygon points="{triangle}" fill="#ffffff" stroke="#b91c1c" stroke-width="3" stroke-linejoin="round" />',
        (f'<text x="{x + 26}" y="{cy - 3}" text-anchor="middle" fill="#b91c1c" font-family="Arial" font-size="13" '
         f'font-weight="700">C</text>'),
        *[f'<text x="{text_left}" y="{cy - (len(lines) - 1) * 9 + 5 + n * 18}" fill="#111827" font-family="Arial" '
          f'font-size="14">{_escape(line)}</text>'
          for lines in [_wrap_lines(node.label, max_chars=_max_chars(node.width - 62, 14))] for n, line in enumerate(lines)],
    ])


def _process_step_svg(node: DiagramNode) -> str:
    max_chars = _max_chars(node.width - 36, 16)
    return "\n".join([
        (
            f'<rect x="{node.x}" y="{node.y}" width="{node.width}" height="{node.height}" '
            f'rx="10" fill="#ffffff" stroke="#50c463" stroke-width="4" />'
        ),
        *_center_text_svg(node.label, node.x + node.width // 2, node.y + node.height // 2, max_chars=max_chars, font_size=16),
    ])


def _who_svg(node: DiagramNode) -> str:
    # Someone outside the organisation (a customer, a supplier) is dashed.
    return _tab_card_svg(node, stroke="#e8c200", dashed=node.metadata.get("external") == "true")


def _system_svg(node: DiagramNode) -> str:
    return _tab_card_svg(node, stroke="#66adff")


def _support_svg(node: DiagramNode) -> str:
    stroke = {
        "control": "#f59e0b",
        "risk": "#ef4444",
        "annotation": "#9ca3af",
    }.get(node.type, "#9ca3af")
    dash = ' stroke-dasharray="7 6"' if node.type in {"control", "risk", "annotation"} else ""
    max_chars = _max_chars(node.width - 36, 16)
    return "\n".join([
        (
            f'<rect x="{node.x}" y="{node.y}" width="{node.width}" height="{node.height}" rx="10" '
            f'fill="#ffffff" stroke="{stroke}" stroke-width="4"{dash} />'
        ),
        *_center_text_svg(node.label, node.x + node.width // 2, node.y + node.height // 2, max_chars=max_chars, font_size=16),
    ])


def _tab_card_svg(node: DiagramNode, *, stroke: str, dashed: bool = False) -> str:
    dash = ' stroke-dasharray="9 6"' if dashed else ""
    tab_width = 22
    header_height = 22
    tab_x = node.x + tab_width
    header_y = node.y + header_height
    content_left = tab_x + 10
    content_width = node.width - tab_width - 20
    content_x = content_left + content_width // 2
    content_y = header_y + (node.height - header_height) // 2
    max_chars = _max_chars(content_width, 16)
    return "\n".join([
        (
            f'<rect x="{node.x}" y="{node.y}" width="{node.width}" height="{node.height}" '
            f'rx="10" fill="#ffffff" stroke="{stroke}" stroke-width="4"{dash} />'
        ),
        f'<line x1="{tab_x}" y1="{node.y}" x2="{tab_x}" y2="{node.y + node.height}" stroke="{stroke}" stroke-width="4"{dash} />',
        f'<line x1="{node.x}" y1="{header_y}" x2="{node.x + node.width}" y2="{header_y}" stroke="{stroke}" stroke-width="4"{dash} />',
        *_center_text_svg(node.label, content_x, content_y, max_chars=max_chars, font_size=16),
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
    line_height = _line_height(font_size)
    first_y = center_y - ((len(lines) - 1) * line_height) // 2 + font_size // 3
    return [
        (
            f'<text x="{x}" y="{first_y + index * line_height}" text-anchor="middle" fill="#111827" '
            f'font-family="Arial" font-size="{font_size}" font-weight="400">{_escape(line)}</text>'
        )
        for index, line in enumerate(lines)
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


def _text_aware_height(
    value: str,
    width: int,
    minimum: int,
    *,
    font_size: int,
    horizontal_padding: int,
    vertical_padding: int,
) -> int:
    lines = _wrap_lines(value, max_chars=_max_chars(width - horizontal_padding, font_size))
    return max(minimum, len(lines) * _line_height(font_size) + vertical_padding)


def _max_chars(width: int, font_size: int) -> int:
    return max(10, int(width / (font_size * TEXT_WIDTH_FACTOR)))


def _line_height(font_size: int) -> int:
    return font_size + 6


def _edge_svg(edge: DiagramEdge) -> str:
    marker = "" if edge.type == "association" else ' marker-end="url(#arrow)"'  # a line to a role or system has no arrow
    path = " ".join(
        f"{'M' if index == 0 else 'L'} {point.x} {point.y}"
        for index, point in enumerate(edge.points)
    )
    label = ""
    if edge.label:
        midpoint = edge.points[len(edge.points) // 2]
        label_width = max(28, len(edge.label) * 6 + 10)
        label_x = midpoint.x + 4
        label_y = midpoint.y - 19
        label = (
            f'<rect x="{label_x}" y="{label_y}" width="{label_width}" height="16" rx="4" fill="#ffffff" opacity="0.9" />'
            f'<text x="{label_x + 4}" y="{label_y + 12}" fill="#475569" '
            f'font-family="Arial" font-size="11">{_escape(edge.label)}</text>'
        )
    return "\n".join([
        f'<path d="{path}" fill="none" stroke="#334155" stroke-width="2"{marker} />',
        label,
    ])


def _escape(value: str) -> str:
    return html.escape(value, quote=True)
