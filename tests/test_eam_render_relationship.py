"""EAM Relationship-view SVG renderer tests."""

from __future__ import annotations

from assistant.eam.model import build_eam_model
from assistant.eam.render_relationship import render_relationship_svg
from assistant.eam.taxonomy import TaxonomyConfig
from assistant.ontology import OntologyStore, SchemaRegistry
from tests.test_eam_model import _seed_process_graph


def test_render_relationship_svg_contains_process_entity_nodes_and_edges(tmp_path) -> None:
    store = OntologyStore(tmp_path / "ontology.db", registry=SchemaRegistry.load())
    _seed_process_graph(store)
    model = build_eam_model(store, TaxonomyConfig.load())

    svg = render_relationship_svg(model)

    assert svg.startswith("<svg")
    assert "Relationship View" in svg
    assert 'data-node-id="process:supplier_ordering"' in svg
    assert 'data-entity-id="role:data_owner"' in svg
    assert 'data-entity-type="system"' in svg
    assert 'data-relationship-id="process:supplier_ordering:role:data_owner"' in svg
    assert "Designed for frontend pan / zoom controls" in svg
