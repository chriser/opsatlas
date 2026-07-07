"""Enterprise Activity Model scale and density tests."""

from __future__ import annotations

import re
import time

from assistant.eam.model import MAX_EAM_FINDINGS, MAX_PAIRWISE_FINDINGS, build_eam_model
from assistant.eam.render_accountability import render_accountability_svg
from assistant.eam.render_activity import render_activity_svg
from assistant.eam.render_relationship import render_relationship_svg
from assistant.eam.render_risk_heat import render_risk_heat_svg
from assistant.eam.taxonomy import TaxonomyConfig
from assistant.ontology import OntologyStore, SchemaRegistry

SCALE_PROCESS_COUNT = 60
SCALE_BUDGET_SECONDS = 1.5


def test_eam_model_and_svg_views_handle_60_process_fixture_with_bounded_noise(tmp_path) -> None:
    store = OntologyStore(tmp_path / "ontology.db", registry=SchemaRegistry.load())
    taxonomy = TaxonomyConfig.load()
    _seed_scale_graph(store, taxonomy, SCALE_PROCESS_COUNT)

    started = time.perf_counter()
    model = build_eam_model(store, taxonomy)
    activity_svg = render_activity_svg(model)
    accountability_svg = render_accountability_svg(model)
    risk_svg = render_risk_heat_svg(model)
    relationship_svg = render_relationship_svg(model)
    elapsed = time.perf_counter() - started

    assert elapsed < SCALE_BUDGET_SECONDS
    assert model.process_count == SCALE_PROCESS_COUNT
    assert len(model.findings) <= MAX_EAM_FINDINGS
    assert sum(1 for finding in model.findings if finding.node_ids) <= MAX_PAIRWISE_FINDINGS
    assert model.meta["finding_limit"] == MAX_EAM_FINDINGS
    assert model.meta["pairwise_finding_limit"] == MAX_PAIRWISE_FINDINGS

    assert "+2 more" in activity_svg
    assert "Accountability View" in accountability_svg
    assert "Risk and Coverage Heat View" in risk_svg
    assert "Relationship View" in relationship_svg
    assert relationship_svg.count("data-relationship-id=") <= 220


def _seed_scale_graph(store: OntologyStore, taxonomy: TaxonomyConfig, process_count: int) -> None:
    roles = [
        store.upsert_object("role", f"role-{index}", {"name": f"Role {index}"})
        for index in range(12)
    ]
    systems = [
        store.upsert_object("system", f"system-{index}", {"name": f"System {index}"})
        for index in range(18)
    ]
    controls = [
        store.upsert_object("control", f"control-{index}", {"name": f"Control {index}"})
        for index in range(10)
    ]

    for index in range(process_count):
        domain = taxonomy.domains[index % len(taxonomy.domains)]
        stage = taxonomy.lifecycle_stages[(index % len(taxonomy.domains)) % len(taxonomy.lifecycle_stages)]
        domain_keyword = domain.keywords[0]
        stage_keyword = stage.keywords[0]
        process = store.upsert_object(
            "process",
            f"scale-process-{index}",
            {
                "name": f"{domain.label} {stage.label} Scale Process {index}",
                "domain": domain_keyword,
                "capabilities": [f"{domain_keyword} capability", f"{stage_keyword} capability"],
                "business_rules": [f"{domain_keyword} must follow {stage_keyword} control evidence."],
                "key_facts": [f"{domain_keyword} {stage_keyword} fact {index}"],
            },
        )
        source = store.upsert_object(
            "source",
            f"scale-source-{index}",
            {"title": f"Scale Source {index}", "filename": f"scale-{index}.md"},
        )
        store.link("process_derived_from", process.id, source.id)
        store.link("process_has_role", process.id, roles[index % len(roles)].id)
        store.link("process_has_role", process.id, roles[(index + 3) % len(roles)].id)
        store.link("process_uses_system", process.id, systems[index % len(systems)].id)
        store.link("process_uses_system", process.id, systems[(index + 5) % len(systems)].id)
        store.link("process_enforced_by", process.id, controls[index % len(controls)].id)


def test_scale_fixture_cell_distribution_proves_clustering_path(tmp_path) -> None:
    store = OntologyStore(tmp_path / "ontology.db", registry=SchemaRegistry.load())
    taxonomy = TaxonomyConfig.load()
    _seed_scale_graph(store, taxonomy, SCALE_PROCESS_COUNT)
    model = build_eam_model(store, taxonomy)

    populated_cells = [cell for cell in model.cells if cell.node_ids]

    assert len(populated_cells) == len(taxonomy.domains)
    assert all(len(cell.node_ids) == 5 for cell in populated_cells)
    assert re.search(r"\+2 more", render_activity_svg(model))
