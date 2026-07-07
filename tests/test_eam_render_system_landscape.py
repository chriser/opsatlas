"""EAM Digital System Landscape SVG renderer tests."""

from __future__ import annotations

from assistant.eam.model import build_eam_model
from assistant.eam.render_system_landscape import render_system_landscape_svg
from assistant.eam.taxonomy import TaxonomyConfig
from assistant.ontology import OntologyStore, SchemaRegistry
from tests.test_eam_model import _seed_process_graph


def test_render_system_landscape_svg_maps_processes_to_system_layers_and_flow(tmp_path) -> None:
    store = OntologyStore(tmp_path / "ontology.db", registry=SchemaRegistry.load())
    _seed_process_graph(store)
    pos = store.upsert_object("system", "point-of-sale-platform", {"name": "Point-of-sale platform"})
    store.link("process_uses_system", "process:supplier_ordering", pos.id)
    model = build_eam_model(store, TaxonomyConfig.load())

    svg = render_system_landscape_svg(model, selected_node_id="process:supplier_ordering")

    assert svg.startswith("<svg")
    assert 'width="' in svg and 'height="' in svg
    assert "Digital System Landscape" in svg
    assert "data:image/png;base64" in svg
    assert "PAYMENTS &amp;" in svg
    assert "SYSTEM LAYERS" in svg
    assert "SYSTEM FLOW" in svg
    assert 'data-landscape-process-id="process:supplier_ordering"' in svg
    assert 'data-landscape-layer-label-id="sales-execution"' in svg
    assert 'data-landscape-layer-id="sales-execution"' in svg
    assert 'height="132"' in svg
    assert 'data-landscape-layer-id="central-store-admin"' in svg
    assert "Point-of-sale platform" in svg
    assert svg.count("Point-of-sale platform") == 1
    assert 'data-landscape-system-layers="sales-execution,store-operations,central-store-admin"' in svg
    assert 'class="eam-landscape-flow"' in svg
    assert 'class="eam-landscape-data-packet"' in svg
    assert 'data-landscape-flow-step="1"' in svg
    assert 'data-landscape-flow-payload="Supplier setup data"' in svg
    assert "Payload: Supplier setup data" in svg
    assert '<animate attributeName="stroke-dashoffset"' in svg
    assert '<animateMotion dur="' in svg


def test_render_system_landscape_svg_wraps_long_payload_labels(tmp_path) -> None:
    store = OntologyStore(tmp_path / "ontology.db", registry=SchemaRegistry.load())
    process = store.upsert_object(
        "process",
        "customer-escalation-evidence-resolution",
        {
            "name": "Customer Escalation Evidence Resolution and Operational Follow Up",
            "domain": "support",
            "capabilities": ["customer issue review"],
            "business_rules": ["Escalations need evidence capture and follow up."],
            "key_facts": ["Escalation evidence is checked before resolution."],
        },
    )
    source = store.upsert_object("source", "source-c", {"title": "Support Pack", "filename": "support.md"})
    start = store.upsert_object("system", "store-operations-console", {"name": "Store operations console"})
    end = store.upsert_object("system", "operational-reporting", {"name": "Operational reporting"})
    store.link("process_derived_from", process.id, source.id)
    store.link("process_uses_system", process.id, start.id)
    store.link("process_uses_system", process.id, end.id)
    model = build_eam_model(store, TaxonomyConfig.load())

    svg = render_system_landscape_svg(model, selected_node_id=process.id)

    assert (
        'data-landscape-flow-payload="Customer Escalation Evidence Resolution and Operational Follow Up data"'
        in svg
    )
    assert "Payload: Customer Escalation" in svg
    assert "Evidence Resolution and" in svg
    assert "Operational Follow Up data" in svg


def test_render_system_landscape_svg_hides_connections_without_selection_unless_revealed(tmp_path) -> None:
    store = OntologyStore(tmp_path / "ontology.db", registry=SchemaRegistry.load())
    _seed_process_graph(store)
    pos = store.upsert_object("system", "point-of-sale-platform", {"name": "Point-of-sale platform"})
    store.link("process_uses_system", "process:supplier_ordering", pos.id)
    model = build_eam_model(store, TaxonomyConfig.load())

    svg = render_system_landscape_svg(model, selected_node_id="missing")
    revealed_svg = render_system_landscape_svg(model, selected_node_id="missing", show_all_connections=True)

    assert "Select a process row" in svg
    assert model.nodes[0].name in svg
    assert 'class="eam-landscape-flow"' not in svg
    assert 'class="eam-landscape-flow"' in revealed_svg


def test_render_system_landscape_svg_splits_non_contiguous_system_layers(tmp_path) -> None:
    store = OntologyStore(tmp_path / "ontology.db", registry=SchemaRegistry.load())
    _seed_process_graph(store)
    payment_contract = store.upsert_object("system", "payment-contract", {"name": "Payment Contract"})
    store.link("process_uses_system", "process:supplier_ordering", payment_contract.id)
    model = build_eam_model(store, TaxonomyConfig.load())

    svg = render_system_landscape_svg(model, selected_node_id="process:supplier_ordering")

    assert 'data-landscape-system-key="payment contract"' in svg
    assert (
        'data-landscape-system-layers="payments-forecourt,convenience-head-office,finance"'
        in svg
    )
    assert svg.count('data-landscape-system-segment-key="payment contract"') == 3
    assert 'data-landscape-system-segment-layers="payments-forecourt"' in svg
    assert 'data-landscape-system-segment-layers="convenience-head-office"' in svg
    assert 'data-landscape-system-segment-layers="finance"' in svg
    assert (
        'data-landscape-system-segment-layers="payments-forecourt,convenience-head-office,finance"'
        not in svg
    )
