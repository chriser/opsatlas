"""EAM Accountability-view SVG renderer tests."""

from __future__ import annotations

from assistant.eam.model import build_eam_model
from assistant.eam.render_accountability import render_accountability_svg
from assistant.eam.taxonomy import TaxonomyConfig
from assistant.ontology import OntologyStore, SchemaRegistry
from tests.test_eam_model import _seed_process_graph


def test_render_accountability_svg_contains_owner_swimlanes_and_process_cards(tmp_path) -> None:
    store = OntologyStore(tmp_path / "ontology.db", registry=SchemaRegistry.load())
    _seed_process_graph(store)
    model = build_eam_model(store, TaxonomyConfig.load())

    svg = render_accountability_svg(model)

    assert svg.startswith("<svg")
    assert "Accountability View" in svg
    assert 'data-role-id="role:data_owner"' in svg
    assert 'data-role-id="role:trading_support"' in svg
    assert 'data-node-id="process:supplier_ordering"' in svg
    assert "Supplier Ordering" in svg
    assert "Swimlanes are derived from process_has_role ontology links." in svg
