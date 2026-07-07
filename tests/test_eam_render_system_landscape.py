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
    assert "Digital System Landscape" in svg
    assert "data:image/png;base64" in svg
    assert "PAYMENTS &amp;" in svg
    assert 'data-landscape-process-id="process:supplier_ordering"' in svg
    assert 'data-landscape-layer-id="sales-execution"' in svg
    assert 'data-landscape-layer-id="central-store-admin"' in svg
    assert "Point-of-sale platform" in svg
    assert svg.count("Point-of-sale platform") == 1
    assert 'data-landscape-system-layers="sales-execution,store-operations,central-store-admin"' in svg
    assert 'class="eam-landscape-flow"' in svg
    assert 'class="eam-landscape-data-packet"' in svg
    assert '<animate attributeName="stroke-dashoffset"' in svg


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
