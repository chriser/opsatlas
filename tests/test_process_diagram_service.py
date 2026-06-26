"""Local process diagram microservice tests."""

from fastapi.testclient import TestClient

from services.process_diagram.app import app
from services.process_diagram.engine import DiagramValidationError, render_process_chart, render_svg
from services.process_diagram.models import ProcessChartRenderRequest, ProcessModelInput


def _structured_request() -> ProcessChartRenderRequest:
    return ProcessChartRenderRequest.model_validate({
        "style": "plain",
        "format": "cross-functional-flowchart",
        "animation": True,
        "process_model": {
            "title": "Supplier setup",
            "nodes": [
                {"id": "buyer", "type": "lane", "label": "Category Buyer"},
                {"id": "support", "type": "lane", "label": "Trading Support"},
                {"id": "submit_form", "type": "task", "label": "Complete supplier setup form", "lane": "buyer"},
                {"id": "review", "type": "task", "label": "Review submitted form", "lane": "support"},
                {"id": "decision", "type": "gateway", "label": "Details complete?", "lane": "support"},
            ],
            "edges": [
                {"from": "submit_form", "to": "review", "label": "submit"},
                {"from": "review", "to": "decision", "label": "check"},
            ],
        },
    })


def test_structured_process_model_returns_layout_animation_and_narration():
    chart = render_process_chart(_structured_request())
    nodes = {node.id: node for node in chart.nodes}

    assert chart.schema_version == "process-chart.v1"
    assert chart.chart_id.startswith("supplier_setup-")
    assert "buyer" not in nodes
    assert nodes["who_submit_form"].type == "who"
    assert nodes["who_submit_form"].label == "Category Buyer"
    assert nodes["who_submit_form"].y + nodes["who_submit_form"].height // 2 == nodes["submit_form"].y + nodes["submit_form"].height // 2
    assert nodes["submit_form"].lane == "buyer"
    assert nodes["review"].lane == "support"
    assert nodes["decision"].type == "gateway"
    assert nodes["submit_form"].x == nodes["review"].x
    assert nodes["who_submit_form"].x > nodes["submit_form"].x
    assert chart.edges[0].from_node == "start"
    assert chart.edges[1].from_node == "submit_form"
    assert any(edge.from_node == "submit_form" and edge.to_node == "who_submit_form" for edge in chart.edges)
    assert chart.animation_steps[0].action == "draw_node"
    assert chart.narration_script


def test_narrative_input_is_converted_into_reviewable_process_model():
    request = ProcessChartRenderRequest(
        narrative=(
            "The category buyer completes the supplier setup form. "
            "Trading Support reviews the request. "
            "If details are complete, Finance creates the supplier record."
        )
    )

    chart = render_process_chart(request)

    assert any(node.type == "gateway" for node in chart.nodes)
    assert any(node.label.startswith("Trading Support reviews") for node in chart.nodes)
    assert chart.warnings == ["Narrative was converted with deterministic local heuristics; review before production use."]


def test_validation_rejects_edges_that_reference_unknown_nodes():
    request = ProcessChartRenderRequest(
        process_model=ProcessModelInput.model_validate({
            "title": "Broken model",
            "nodes": [{"id": "known", "type": "task", "label": "Known task"}],
            "edges": [{"from": "known", "to": "missing"}],
        })
    )

    try:
        render_process_chart(request)
    except DiagramValidationError as exc:
        assert "unknown to node" in str(exc)
    else:
        raise AssertionError("Expected invalid edge to be rejected")


def test_svg_renderer_preserves_structured_labels():
    chart = render_process_chart(_structured_request())
    svg = render_svg(chart)

    assert svg.startswith('<svg xmlns="http://www.w3.org/2000/svg"')
    assert "Supplier setup" in svg
    assert "Category Buyer" in svg
    assert "Complete supplier" in svg


def test_long_labels_expand_boxes_and_are_not_truncated():
    request = ProcessChartRenderRequest.model_validate({
        "process_model": {
            "title": "Long label fit",
            "nodes": [
                {
                    "id": "operator",
                    "type": "lane",
                    "label": "finance aligned downstream operational ownership forum",
                },
                {
                    "id": "long_task",
                    "type": "task",
                    "label": "payment contract is mandatory for invoice matching in the operational master data process",
                    "lane": "operator",
                },
                {
                    "id": "long_system",
                    "type": "system",
                    "label": "Supplier header in operational master data tool",
                    "lane": "systems",
                },
            ],
            "edges": [{"from": "long_system", "to": "long_task", "label": "supports"}],
        },
    })

    chart = render_process_chart(request)
    nodes = {node.id: node for node in chart.nodes}
    svg = render_svg(chart)

    assert nodes["long_task"].height > 112
    assert nodes["long_system"].height > 86
    assert nodes["who_long_task"].height > 92
    assert "operational" in svg
    assert "master data process" in svg
    assert "finance aligned" in svg


def test_microservice_json_and_svg_endpoints():
    client = TestClient(app)
    payload = _structured_request().model_dump(mode="json", by_alias=True)

    health = client.get("/health")
    json_response = client.post("/process-chart/render", json=payload)
    svg_response = client.post("/process-chart/render.svg", json=payload)

    assert health.json() == {"status": "ok", "service": "process-diagram"}
    assert json_response.status_code == 200
    assert json_response.json()["title"] == "Supplier setup"
    assert svg_response.status_code == 200
    assert svg_response.headers["content-type"].startswith("image/svg+xml")
    assert "<svg" in svg_response.text


def test_microservice_examples_gallery_and_direct_svg_routes():
    client = TestClient(app)

    gallery = client.get("/examples")
    index = client.get("/examples/index")
    svg = client.get("/examples/supplier-setup/svg")
    payload = client.get("/examples/supplier-setup/payload")
    json_response = client.get("/examples/supplier-setup/json")
    missing = client.get("/examples/missing/svg")

    assert gallery.status_code == 200
    assert gallery.headers["content-type"].startswith("text/html")
    assert "Local Process Diagram Examples" in gallery.text
    assert "/examples/supplier-setup/svg" in gallery.text
    assert index.status_code == 200
    assert index.json()[0]["id"] == "supplier-setup"
    assert svg.status_code == 200
    assert svg.headers["content-type"].startswith("image/svg+xml")
    assert "Supplier Setup Process" in svg.text
    assert payload.status_code == 200
    assert payload.json()["process_model"]["title"] == "Supplier Setup Process"
    assert json_response.status_code == 200
    assert json_response.json()["title"] == "Supplier Setup Process"
    assert missing.status_code == 404
