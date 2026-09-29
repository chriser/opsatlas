"""The process map notation and its layout: one standard for every process map (the Human's decision, 29 September 2026).

The notation is an event-driven process chain, as in the organisation's shape legend:
- trigger and outcome events (pink hexagons), including the condition each path after a split starts with;
- process steps (green), automated steps (blue), and interfaces to another process (grey, with its reference);
- connectors: XOR (only one path followed), AND (all paths followed), ANY (any number of paths followed); a split's
  paths meet again at a join of the same kind;
- beside each step: the roles performing it on the right (an outside party, such as the customer, dashed), and the
  application system supporting it on the left ("Non-system activity" when there is none), with any controls.

The layout gives each path its own column: a split's paths sit side by side under it and meet at the join below them,
so a branched process is drawn branched (until now every step was drawn in one column, in the order given).
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field

from .models import ProcessChartEdgeInput, ProcessChartNodeInput, ProcessModelInput

FLOW_TYPES = {"start", "end", "task", "gateway", "event", "interface", "automated"}
STEP_TYPES = {"task", "automated", "interface"}
LEFT_SUPPORT = {"system", "control", "risk", "annotation"}
GATEWAY_KINDS = {"xor", "and", "or"}
NO_SYSTEM = "Non-system activity"
OUTSIDE_ROLES = {"customer", "customers", "supplier", "suppliers", "visitor", "member of the public", "client"}


KIND_NAMES = {"any": "or", "inclusive": "or", "exclusive": "xor", "parallel": "and", "all": "and"}


def gateway_kind(node: ProcessChartNodeInput) -> str:
    """xor, and or or (shown as ANY); anything else is taken as xor."""
    kind = (node.metadata.get("gateway") or "xor").strip().lower()
    kind = KIND_NAMES.get(kind, kind)
    return kind if kind in GATEWAY_KINDS else "xor"


def apply_notation(model: ProcessModelInput) -> ProcessModelInput:
    """The notation's rules, made explicit in the model: events after a split, joins where paths meet, a system (or
    "Non-system activity") for every manual step. Nothing the caller gave is dropped."""
    nodes = list(model.nodes)
    edges = list(model.edges)
    by_id = {n.id: n for n in nodes}
    flow = {n.id for n in nodes if n.type in FLOW_TYPES}
    taken = set(by_id)

    def new_id(base: str) -> str:
        candidate, n = base, 2
        while candidate in taken:
            candidate, n = f"{base}_{n}", n + 1
        taken.add(candidate)
        return candidate

    # Each path after a split starts with its condition, as an event.
    outgoing: dict[str, list[ProcessChartEdgeInput]] = defaultdict(list)
    for edge in edges:
        if edge.type == "sequence" and edge.from_node in flow and edge.to_node in flow:
            outgoing[edge.from_node].append(edge)
    rewritten: list[ProcessChartEdgeInput] = []
    for edge in edges:
        source = by_id.get(edge.from_node)
        label = edge.label.strip()
        if (source is not None and source.type == "gateway" and len(outgoing[source.id]) > 1 and edge in outgoing[source.id]
                and label and label.lower() not in {"next", "begin", "complete", "…", "..."}
                and by_id[edge.to_node].type != "event"):
            event = ProcessChartNodeInput(id=new_id(f"{source.id}__{edge.to_node}"), type="event",
                                          label=label[:1].upper() + label[1:], lane=by_id[edge.to_node].lane,
                                          metadata={"condition_of": source.id})
            nodes.append(event)
            by_id[event.id] = event
            flow.add(event.id)
            rewritten.append(edge.model_copy(update={"to_node": event.id, "label": ""}))
            rewritten.append(ProcessChartEdgeInput(id=f"{event.id}__next", **{"from": event.id, "to": edge.to_node}))
        else:
            rewritten.append(edge)
    edges = rewritten

    # Where paths meet, a join of the same kind as the split they came from.
    start = _start(nodes, edges, flow)
    forward, _ = _forward_edges(start, flow, edges)
    incoming: dict[str, list[ProcessChartEdgeInput]] = defaultdict(list)
    for edge in edges:
        if (edge.from_node, edge.to_node) in forward:
            incoming[edge.to_node].append(edge)
    splits = {n.id: gateway_kind(n) for n in nodes if n.type == "gateway"}
    for target, into in list(incoming.items()):
        if len(into) < 2 or by_id[target].type == "gateway":
            continue
        kind = _nearest_split_kind(target, edges, splits, by_id) or "xor"
        join = ProcessChartNodeInput(id=new_id(f"join_{target}"), type="gateway", label="",
                                     lane=by_id[target].lane, metadata={"gateway": kind, "join": "true"})
        nodes.append(join)
        by_id[join.id] = join
        flow.add(join.id)
        edges = [e.model_copy(update={"to_node": join.id}) if e in into else e for e in edges]
        edges.append(ProcessChartEdgeInput(id=f"{join.id}__next", **{"from": join.id, "to": target}))

    # Every manual step says which system supports it, or that none does.
    supported = {e.to_node for e in edges if by_id.get(e.from_node) is not None and by_id[e.from_node].type == "system"}
    supported |= {e.from_node for e in edges if by_id.get(e.to_node) is not None and by_id[e.to_node].type == "system"}
    for node in list(nodes):
        if node.type == "task" and node.id not in supported:
            system = ProcessChartNodeInput(id=new_id(f"{node.id}__no_system"), type="system", label=NO_SYSTEM,
                                           lane="systems", metadata={"default": "true"})
            nodes.append(system)
            edges.append(ProcessChartEdgeInput(id=f"{system.id}__supports", type="association",
                                               **{"from": system.id, "to": node.id}))
    return ProcessModelInput(title=model.title, nodes=nodes, edges=edges)


def _start(nodes, edges, flow) -> str | None:
    starts = [n.id for n in nodes if n.type == "start" and n.id in flow]
    if starts:
        return starts[0]
    targets = {e.to_node for e in edges if e.type == "sequence"}
    return next((n.id for n in nodes if n.id in flow and n.id not in targets), next(iter(flow), None))


def _forward_edges(start, flow, edges) -> tuple[set[tuple[str, str]], set[tuple[str, str]]]:
    """Sequence edges between flow nodes, split into forward ones and those that loop back (to a step still open on
    the path from the start)."""
    adjacency: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        if edge.type == "sequence" and edge.from_node in flow and edge.to_node in flow:
            adjacency[edge.from_node].append(edge.to_node)
    forward, back, state = set(), set(), {}
    roots = [start] if start else []
    roots += [n for n in flow if n != start]
    for root in roots:
        if root in state:
            continue
        stack = [(root, iter(adjacency[root]))]
        state[root] = "open"
        while stack:
            node, children = stack[-1]
            child = next(children, None)
            if child is None:
                state[node] = "done"
                stack.pop()
                continue
            if state.get(child) == "open":
                back.add((node, child))
                continue
            forward.add((node, child))
            if child not in state:
                state[child] = "open"
                stack.append((child, iter(adjacency[child])))
    return forward, back


def _nearest_split_kind(target, edges, splits, by_id) -> str | None:
    """The kind of the split a join closes: the nearest split gateway found walking back from the join."""
    backwards: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        if edge.type == "sequence":
            backwards[edge.to_node].append(edge.from_node)
    seen, queue = {target}, deque(backwards[target])
    while queue:
        node = queue.popleft()
        if node in seen:
            continue
        seen.add(node)
        if node in splits and by_id[node].metadata.get("join") != "true":
            return splits[node]
        queue.extend(backwards[node])
    return None


@dataclass
class Block:
    """Placed flow nodes, relative to the block's own axis: (id, column, row)."""
    items: list[tuple[str, float, int]] = field(default_factory=list)
    height: int = 0
    via: list[tuple[tuple[str, str], float]] = field(default_factory=list)

    def columns(self) -> list[float]:
        return [c for _, c, _ in self.items] + [c for _, c in self.via]

    @property
    def left(self) -> float:
        return max([0.0, *(-c for c in self.columns())])

    @property
    def right(self) -> float:
        return max([0.0, *self.columns()])

    @property
    def width(self) -> float:
        return self.left + 1 + self.right


def place(model: ProcessModelInput) -> tuple[dict[str, tuple[float, int]], set[tuple[str, str]], set[tuple[str, str]],
                                             dict[tuple[str, str], float]]:
    """Columns and rows for the flow nodes. Returns {id: (column, row)}, the forward edges, the loop-backs, and the
    column a path that goes straight from a split to its join runs down."""
    flow_nodes = [n for n in model.nodes if n.type in FLOW_TYPES]
    flow = {n.id for n in flow_nodes}
    start = _start(flow_nodes, model.edges, flow)
    forward, back = _forward_edges(start, flow, model.edges)
    successors: dict[str, list[str]] = defaultdict(list)
    for edge in model.edges:
        if (edge.from_node, edge.to_node) in forward and edge.to_node not in successors[edge.from_node]:
            successors[edge.from_node].append(edge.to_node)
    placed: set[str] = set()

    def reachable(node: str, stops: set[str]) -> dict[str, int]:
        depth, queue = {node: 0}, deque([node])
        while queue:
            current = queue.popleft()
            if current in stops and current != node:
                continue
            for nxt in successors[current]:
                if nxt not in depth:
                    depth[nxt] = depth[current] + 1
                    queue.append(nxt)
        return depth

    def join_of(branches: list[str], stops: set[str]) -> str | None:
        reach = [reachable(b, stops) for b in branches]
        common = set(reach[0]).intersection(*reach[1:]) - placed
        if not common:
            return None
        best = min(common, key=lambda n: (max(r[n] for r in reach), n))
        return None if best in stops else best

    def chain(first: str, stops: set[str]) -> Block:
        block, row, current = Block(), 0, first
        offsets: list[tuple[tuple[str, str], float]] = []
        while current is not None and current not in stops and current not in placed:
            placed.add(current)
            block.items.append((current, 0.0, row))
            row += 1
            nexts = [s for s in successors[current] if s not in placed]
            if not nexts:
                break
            if len(nexts) == 1:
                current = nexts[0]
                continue
            join = join_of(nexts, stops)
            inner = stops | ({join} if join else set())
            blocks = [chain(n, inner) for n in nexts]
            total = sum(b.width for b in blocks)
            cursor = -(total - 1) / 2
            for branch, sub in zip(nexts, blocks):
                axis = cursor + sub.left
                block.items.extend((i, axis + c, row + r) for i, c, r in sub.items)
                offsets.extend((key, axis + c) for key, c in sub.via)
                if not sub.items:  # straight to the join: the path keeps a column of its own
                    offsets.append(((current, branch), axis))
                cursor += sub.width
            block.via = offsets
            row += max([1, *(b.height for b in blocks)])
            current = join
        block.height = row
        block.via = offsets
        return block

    main = chain(start, set()) if start else Block()
    # Steps not reached from the start (said, but not yet linked): each chain to the right, from the top.
    extra = [n.id for n in flow_nodes if n.id not in placed]
    for node_id in extra:
        if node_id in placed:
            continue
        loose = chain(node_id, set())
        axis = main.right + 1 + loose.left
        main.items.extend((i, axis + c, r) for i, c, r in loose.items)
        main.via.extend((key, axis + c) for key, c in loose.via)
        main.height = max(main.height, loose.height)
    shift = main.left
    return ({i: (c + shift, r) for i, c, r in main.items}, forward, back,
            {key: c + shift for key, c in main.via})
