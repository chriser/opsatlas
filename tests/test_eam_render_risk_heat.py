"""EAM Risk and coverage heat-view SVG renderer tests."""

from __future__ import annotations

from assistant.eam.model import build_eam_model
from assistant.eam.render_risk_heat import render_risk_heat_svg
from assistant.eam.taxonomy import TaxonomyConfig
from assistant.ontology import OntologyStore, SchemaRegistry
from tests.test_eam_model import _seed_process_graph


def test_render_risk_heat_svg_contains_heat_cells_and_risk_legend(tmp_path) -> None:
    store = OntologyStore(tmp_path / "ontology.db", registry=SchemaRegistry.load())
    _seed_process_graph(store)
    model = build_eam_model(store, TaxonomyConfig.load())

    svg = render_risk_heat_svg(model)

    assert svg.startswith("<svg")
    assert "Risk and Coverage Heat View" in svg
    assert 'data-cell-id="ordering:source-replenish"' in svg
    assert 'data-risk-band="' in svg
    assert "medium risk / coverage gap" in svg
    assert "high risk / clash signal" in svg
