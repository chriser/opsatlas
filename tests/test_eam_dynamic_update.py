"""EAM dynamic update and provenance tests."""

from __future__ import annotations

from assistant.eam.model import build_eam_model
from assistant.eam.render_activity import render_activity_svg
from assistant.eam.taxonomy import TaxonomyConfig
from assistant.ontology import OntologyStore, SchemaRegistry


def test_eam_model_is_read_through_and_reflects_new_ontology_process_without_restart(tmp_path) -> None:
    store = OntologyStore(tmp_path / "ontology.db", registry=SchemaRegistry.load())
    taxonomy = TaxonomyConfig.load()
    _add_process(store, "supplier-ordering", "Supplier Ordering", "ordering", "source replenish", "source-a")

    first = build_eam_model(store, taxonomy)

    _add_process(store, "article-ranging", "Article Ranging", "ranging", "configure", "source-b")
    second = build_eam_model(store, taxonomy)

    assert first.process_count == 1
    assert first.source_count == 1
    assert second.process_count == 2
    assert second.source_count == 2
    assert {node.name for node in second.nodes} == {"Supplier Ordering", "Article Ranging"}


def test_eam_activity_svg_exposes_node_source_refs_for_hover_provenance(tmp_path) -> None:
    store = OntologyStore(tmp_path / "ontology.db", registry=SchemaRegistry.load())
    taxonomy = TaxonomyConfig.load()
    _add_process(store, "supplier-ordering", "Supplier Ordering", "ordering", "source replenish", "source-a")

    svg = render_activity_svg(build_eam_model(store, taxonomy))

    assert "<title>Supplier Ordering - sources: source-a</title>" in svg


def _add_process(store: OntologyStore, key: str, name: str, domain: str, lifecycle: str, source_key: str) -> None:
    process = store.upsert_object(
        "process",
        key,
        {
            "name": name,
            "domain": domain,
            "capabilities": [f"{domain} capability"],
            "business_rules": [f"{domain} process should be ready for {lifecycle} release."],
            "key_facts": [f"{domain} {lifecycle} fact"],
        },
    )
    source = store.upsert_object("source", source_key, {"title": source_key, "filename": f"{source_key}.md"})
    role = store.upsert_object("role", "data owner", {"name": "Data owner"})
    system = store.upsert_object("system", "operational master data tool", {"name": "Operational master data tool"})
    control = store.upsert_object("control", "readiness gate", {"name": "Readiness gate"})
    store.link("process_derived_from", process.id, source.id)
    store.link("process_has_role", process.id, role.id)
    store.link("process_uses_system", process.id, system.id)
    store.link("process_enforced_by", process.id, control.id)
