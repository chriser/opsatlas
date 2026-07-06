"""EAM Activity-view SVG renderer tests."""

from __future__ import annotations

from assistant.eam.model import build_eam_model
from assistant.eam.render_activity import render_activity_svg
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
    assert 'data-node-id="process:supplier_ordering"' in svg
    assert "Supplier Ordering" in svg
    assert "Supplier Ordering - sources: source-a" in svg
    assert "No evidence" in svg
    assert "shared system" in svg
    assert "shared control" in svg
    assert "stroke-dasharray" in svg
    assert 'data-finding-id="eam-finding-' in svg
