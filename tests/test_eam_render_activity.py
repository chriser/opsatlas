"""EAM Activity-view SVG renderer tests."""

from __future__ import annotations

from assistant.eam.model import build_eam_model
from assistant.eam.render_activity import _wrap_text_to_width, render_activity_svg
from assistant.eam.taxonomy import TaxonomyConfig
from assistant.ontology import OntologyStore, SchemaRegistry
from tests.test_eam_model import _seed_process_graph


def test_render_activity_svg_contains_grid_nodes_edges_and_gap_ghosts(tmp_path) -> None:
    store = OntologyStore(tmp_path / "ontology.db", registry=SchemaRegistry.load())
    _seed_process_graph(store)
    model = build_eam_model(store, TaxonomyConfig.load())

    svg = render_activity_svg(model)

    assert svg.startswith("<svg")
    assert "Enterprise Activity Model" in svg
    assert "FROM STATIC DOCUMENTS TO OPERATING INTELLIGENCE" not in svg
    assert "eam-grid-small" not in svg
    assert "EAM Coverage" in svg
    assert "0-32 red" in svg
    assert "rotate(-90" not in svg
    assert "RETAIL DOMAIN" in svg
    assert "data:image/png;base64" in svg
    assert 'clipPath id="eam-card-clip-' in svg
    assert 'markerWidth="4"' in svg
    assert 'data-domain-id="ordering"' in svg
    assert 'class="eam-node-card eam-node-card--collapsed"' in svg
    assert "Supplier Ordering" in svg
    assert "Supplier Ordering - sources: source-a" in svg
    assert "1 Roles" not in svg
    assert "No evidence" in svg
    assert "shared system" in svg
    assert "shared control" in svg
    assert "eam-routed-edge" in svg
    assert "marker-end=\"url(#arrow-" in svg
    assert "eam-clash-trace" in svg
    assert "stroke-dasharray" in svg
    assert 'data-finding-id="eam-finding-' in svg


def test_render_activity_svg_expands_requested_cards_and_grows_rows(tmp_path) -> None:
    store = OntologyStore(tmp_path / "ontology.db", registry=SchemaRegistry.load())
    _seed_process_graph(store)
    long_process = store.upsert_object(
        "process",
        "long-ordering-flow",
        {
            "name": "Supplier Ordering Schedule Generation Replenishment Allocation and Service Contract Control Review",
            "domain": "ordering",
            "capabilities": ["supplier schedule generation and replenishment allocation"],
            "business_rules": ["Ordering cadence and supplier schedule generation control replenishment allocation."],
            "key_facts": ["Long card fixture for expanded-row sizing."],
        },
    )
    role = store.upsert_object("role", "long fixture owner", {"name": "Long fixture owner"})
    system = store.upsert_object("system", "long fixture system", {"name": "Long fixture system"})
    control = store.upsert_object("control", "long fixture control", {"name": "Long fixture control"})
    store.link("process_has_role", long_process.id, role.id)
    store.link("process_uses_system", long_process.id, system.id)
    store.link("process_enforced_by", long_process.id, control.id)
    model = build_eam_model(store, TaxonomyConfig.load())
    node_id = long_process.id

    collapsed_svg = render_activity_svg(model)
    expanded_svg = render_activity_svg(model, expanded_node_ids={node_id})

    assert 'class="eam-node-card eam-node-card--expanded"' in expanded_svg
    assert "1 Roles" in expanded_svg
    assert _viewbox_height(expanded_svg) > _viewbox_height(collapsed_svg)


def test_render_activity_svg_focuses_selected_node_connections(tmp_path) -> None:
    store = OntologyStore(tmp_path / "ontology.db", registry=SchemaRegistry.load())
    _seed_process_graph(store)
    stock = store.upsert_object(
        "process",
        "stock-count",
        {
            "name": "Stock Count",
            "domain": "stock",
            "capabilities": ["inventory stock control"],
            "business_rules": ["Stock count evidence is captured separately."],
            "key_facts": ["Fixture node that should dim when supplier ordering is focused."],
        },
    )
    source = store.upsert_object("source", "source-stock", {"title": "Stock Pack", "filename": "stock.md"})
    role = store.upsert_object("role", "stock owner", {"name": "Stock owner"})
    system = store.upsert_object("system", "stock platform", {"name": "Stock platform"})
    control = store.upsert_object("control", "stock gate", {"name": "Stock gate"})
    store.link("process_derived_from", stock.id, source.id)
    store.link("process_has_role", stock.id, role.id)
    store.link("process_uses_system", stock.id, system.id)
    store.link("process_enforced_by", stock.id, control.id)
    model = build_eam_model(store, TaxonomyConfig.load())

    svg = render_activity_svg(
        model,
        expanded_node_ids={node.id for node in model.nodes},
        selected_node_id="process:supplier_ordering",
    )

    assert 'data-node-id="process:supplier_ordering" data-focus-state="selected"' in svg
    assert 'data-node-id="process:article_ranging" data-focus-state="connected"' in svg
    assert 'data-node-id="process:stock_count" data-focus-state="dimmed"' in svg
    assert 'class="eam-routed-edge eam-routed-edge--system" data-focus-state="connected"' in svg


def test_activity_card_title_wrapping_respects_card_width() -> None:
    assert _wrap_text_to_width("Supplier Master Data and Contract Design", 166, 15, 6) == [
        "Supplier Master Data",
        "and Contract Design",
    ]
    assert _wrap_text_to_width("End-to-End Article Setup and Bulk Upload Process", 166, 15, 6) == [
        "End-to-End Article",
        "Setup and Bulk Upload",
        "Process",
    ]


def _viewbox_height(svg: str) -> int:
    prefix = 'viewBox="0 0 '
    start = svg.index(prefix) + len(prefix)
    values = svg[start : svg.index('"', start)].split()
    return int(values[1])
