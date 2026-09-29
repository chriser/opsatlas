"""The process map notation and its layout (TIBI E5 PI F18): one standard for every process map, the Human's decision
of 29 September 2026. Until now every step was drawn in one column, so a branched process looked linear."""

from services.process_diagram.engine import render_process_chart, render_svg
from services.process_diagram.examples import example_request, get_example
from services.process_diagram.models import ProcessChartRenderRequest


def chart_of(nodes, edges, title="Made-up process"):
    return render_process_chart(ProcessChartRenderRequest.model_validate(
        {"format": "process-flow", "animation": False, "process_model": {"title": title, "nodes": nodes, "edges": edges}}))


def split_three(kind="or"):
    nodes = [{"id": "ask", "type": "task", "label": "Customer asks for a product"},
             {"id": "which", "type": "gateway", "label": "", "metadata": {"gateway": kind}},
             {"id": "a", "type": "task", "label": "Check ID"},
             {"id": "b", "type": "task", "label": "Check they look over 25"},
             {"id": "c", "type": "task", "label": "Scan the product"},
             {"id": "pay", "type": "task", "label": "Take payment"}]
    edges = [{"from": "ask", "to": "which"}, {"from": "which", "to": "a", "label": "Tobacco"},
             {"from": "which", "to": "b", "label": "Age-restricted, not tobacco"},
             {"from": "which", "to": "c", "label": "No age limit"},
             {"from": "a", "to": "pay"}, {"from": "b", "to": "pay"}, {"from": "c", "to": "pay"}]
    return nodes, edges


def test_the_paths_of_a_split_sit_side_by_side_each_starting_with_its_condition_and_meet_at_a_join():
    chart = chart_of(*split_three())
    nodes = {n.id: n for n in chart.nodes}
    centre = {i: nodes[i].x + nodes[i].width // 2 for i in ("which", "a", "b", "c", "pay")}
    assert len({centre["a"], centre["b"], centre["c"]}) == 3  # three columns, not one
    assert centre["b"] == centre["which"] == centre["pay"]  # the middle path under the split; the flow carries on below
    assert all(nodes[i].y > nodes["which"].y for i in "abc")
    events = {n.label: n for n in chart.nodes if n.type == "event"}
    assert set(events) == {"Tobacco", "Age-restricted, not tobacco", "No age limit"}
    assert events["Tobacco"].y < nodes["a"].y and events["Tobacco"].x + events["Tobacco"].width // 2 == centre["a"]
    [join] = [n for n in chart.nodes if n.type == "gateway" and n.metadata.get("join") == "true"]
    assert join.metadata["gateway"] == "or" and nodes["a"].y < join.y < nodes["pay"].y
    into_join = [e for e in chart.edges if e.to_node == join.id]
    assert sorted(e.from_node for e in into_join) == ["a", "b", "c"]


def test_the_three_connectors_are_drawn_and_named_as_in_the_legend():
    for kind, name in (("xor", "XOR"), ("and", "AND"), ("or", "ANY"), ("any", "ANY"), ("parallel", "AND"), ("odd", "XOR")):
        svg = render_svg(chart_of(*split_three(kind)))
        assert f">{name}</text>" in svg
    assert "<polyline" not in render_svg(chart_of(*split_three("xor")))  # XOR is a cross; AND and ANY are wedges
    assert "<polyline" in render_svg(chart_of(*split_three("and")))


def test_a_step_can_have_two_roles_and_someone_outside_is_dashed():
    nodes = [{"id": "ask", "type": "task", "label": "Ask for a product"},
             {"id": "staff", "type": "who", "label": "Site staff"},
             {"id": "customer", "type": "who", "label": "Customer"}]
    edges = [{"from": "staff", "to": "ask", "type": "association"}, {"from": "customer", "to": "ask", "type": "association"}]
    chart = chart_of(nodes, edges)
    placed = {n.id: n for n in chart.nodes}
    assert placed["staff"].x == placed["customer"].x > placed["ask"].x + placed["ask"].width
    assert placed["staff"].y + placed["staff"].height <= placed["customer"].y  # stacked beside the step
    assert placed["customer"].metadata["external"] == "true" and "external" not in placed["staff"].metadata
    svg = render_svg(chart)
    assert svg.count('stroke-dasharray="9 6"') == 3  # the customer's card, dashed (its outline and two rules)
    assert "marker-end" not in [line for line in svg.splitlines() if 'd="M' in line and "Site" not in line][-1]


def test_a_manual_step_says_non_system_activity_and_other_shapes_do_not():
    nodes = [{"id": "count", "type": "task", "label": "Count the float"},
             {"id": "scan", "type": "task", "label": "Scan the product"},
             {"id": "till", "type": "system", "label": "Point of sale"},
             {"id": "auto", "type": "automated", "label": "Till totals the basket"},
             {"id": "check", "type": "interface", "label": "Carry out age verification check", "metadata": {"reference": "S.4.2"}},
             {"id": "done", "type": "event", "label": "Age verification check completed"}]
    edges = [{"from": "count", "to": "scan"}, {"from": "scan", "to": "auto"}, {"from": "auto", "to": "check"},
             {"from": "check", "to": "done"}, {"from": "till", "to": "scan", "type": "association"}]
    chart = chart_of(nodes, edges)
    systems = {e.to_node: e.from_node for e in chart.edges if e.type == "association"}
    labels = {n.id: n.label for n in chart.nodes}
    assert labels[systems["count"]] == "Non-system activity" and labels[systems["scan"]] == "Point of sale"
    assert not {"auto", "check", "done"} & set(systems)
    svg = render_svg(chart)
    assert ">S.4.2</text>" in svg and "Carry out age" in svg and "Till totals" in svg


def test_a_path_straight_to_the_join_keeps_its_own_column_and_a_loop_back_uses_the_gaps():
    nodes = [{"id": "check", "type": "task", "label": "Check the order"},
             {"id": "ok", "type": "gateway", "label": "Order complete?"},
             {"id": "fix", "type": "task", "label": "Fix the order"},
             {"id": "send", "type": "task", "label": "Send the order"}]
    edges = [{"from": "check", "to": "ok"}, {"from": "ok", "to": "fix", "label": "No"}, {"from": "ok", "to": "send", "label": "Yes"},
             {"from": "fix", "to": "check"}]
    chart = chart_of(nodes, edges)
    placed = {n.id: n for n in chart.nodes}
    [back] = [e for e in chart.edges if e.from_node == "fix" and e.to_node == "check"]
    assert len(back.points) == 6 and back.points[0].y == placed["fix"].y + placed["fix"].height  # out of the bottom
    route = back.points[2].x
    assert all(not (n.x < route < n.x + n.width) for n in chart.nodes)  # up the gap, not through a box
    nodes = [{"id": "ask", "type": "task", "label": "Ask"}, {"id": "g", "type": "gateway", "label": "Gift card?"},
             {"id": "credit", "type": "task", "label": "Issue store credit"}, {"id": "pay", "type": "task", "label": "Take payment"}]
    edges = [{"from": "ask", "to": "g"}, {"from": "g", "to": "credit", "label": "Gift card"}, {"from": "g", "to": "pay", "label": ""},
             {"from": "credit", "to": "pay"}]
    chart = chart_of(nodes, edges)
    placed = {n.id: n for n in chart.nodes}
    [skip] = [e for e in chart.edges if e.from_node == "g" and e.to_node.startswith("join")]
    columns = {p.x for p in skip.points}
    assert len(columns) == 2 and placed["credit"].x + placed["credit"].width // 2 not in columns - {skip.points[0].x}


def test_a_step_not_yet_linked_is_drawn_beside_the_flow_not_on_top_of_it():
    nodes = [{"id": "a", "type": "task", "label": "Greet the customer"}, {"id": "b", "type": "task", "label": "Scan"},
             {"id": "loose", "type": "task", "label": "Restock the shelf"}]
    chart = chart_of(nodes, [{"from": "a", "to": "b"}])
    placed = {n.id: n for n in chart.nodes}
    assert placed["loose"].x > placed["b"].x + placed["b"].width


def test_the_gallery_has_a_branched_example_in_the_notation():
    chart = render_process_chart(example_request(get_example("age-restricted-sale")))
    kinds = {n.type for n in chart.nodes}
    assert {"event", "interface", "gateway", "control", "who", "system"} <= kinds
    gateways = [n for n in chart.nodes if n.type == "gateway"]
    assert [g.metadata["gateway"] for g in gateways] == ["or", "or"]
    assert len({n.x for n in chart.nodes if n.type == "task"}) == 3
