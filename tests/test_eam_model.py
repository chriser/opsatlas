"""Enterprise Activity Model projection tests."""

from __future__ import annotations

from assistant.eam.model import build_eam_model
from assistant.eam.taxonomy import TaxonomyConfig
from assistant.ontology import OntologyStore, SchemaRegistry


def test_build_eam_model_projects_processes_to_taxonomy_cells_and_rollups(tmp_path) -> None:
    store = OntologyStore(tmp_path / "ontology.db", registry=SchemaRegistry.load())
    _seed_process_graph(store)

    model = build_eam_model(store, TaxonomyConfig.load())

    assert model.taxonomy_version == "eam-taxonomy.v2"
    assert model.process_count == 2
    assert model.source_count == 2
    assert {node.name for node in model.nodes} == {"Supplier Ordering", "Article Ranging"}

    ordering_node = next(node for node in model.nodes if node.name == "Supplier Ordering")
    assert ordering_node.domain_id == "ordering"
    assert ordering_node.lifecycle_id == "source-replenish"
    assert ordering_node.role_count == 1
    assert ordering_node.system_count == 1
    assert ordering_node.control_count == 1
    assert ordering_node.evidence_strength >= 50
    assert ordering_node.confidence_band in {"green", "amber"}

    ranging_node = next(node for node in model.nodes if node.name == "Article Ranging")
    assert ranging_node.domain_id == "ranging"

    ordering_cell = next(cell for cell in model.cells if cell.domain_id == "ordering" and cell.lifecycle_id == "source-replenish")
    assert ordering_cell.node_ids == [ordering_node.id]
    assert ordering_cell.is_gap is False
    assert any(cell.is_gap for cell in model.cells)

    assert model.entity_rollups["roles"][0].name == "Data owner"
    assert model.entity_rollups["systems"][0].process_count == 2
    assert model.entity_rollups["controls"][0].process_count == 2
    assert model.coverage.partial_domain_count >= 2
    assert model.coverage.uncovered_domain_count >= 1
    assert model.finding_counts["gap"] >= 1


def test_build_eam_model_derives_shared_system_and_control_edges(tmp_path) -> None:
    store = OntologyStore(tmp_path / "ontology.db", registry=SchemaRegistry.load())
    _seed_process_graph(store)

    model = build_eam_model(store, TaxonomyConfig.load())

    assert {edge.edge_type for edge in model.edges} == {"system", "control"}
    system_edge = next(edge for edge in model.edges if edge.edge_type == "system")
    control_edge = next(edge for edge in model.edges if edge.edge_type == "control")

    assert system_edge.shared_entity_labels == ["Operational master data tool"]
    assert control_edge.shared_entity_labels == ["Readiness gate"]
    assert system_edge.from_node_id != system_edge.to_node_id


def test_build_eam_model_flags_linkable_overlap_and_clash_findings(tmp_path) -> None:
    store = OntologyStore(tmp_path / "ontology.db", registry=SchemaRegistry.load())
    _seed_process_graph(store)

    model = build_eam_model(store, TaxonomyConfig.load())

    overlap = next(finding for finding in model.findings if finding.finding_type == "overlap")
    clash = next(finding for finding in model.findings if finding.finding_type == "clash")

    assert overlap.node_ids == ["process:article_ranging", "process:supplier_ordering"]
    assert any("Shared systems" in item for item in overlap.evidence)
    assert any("Shared controls" in item for item in overlap.evidence)
    assert clash.title == "Shared control has no shared owner evidence"
    assert clash.entity_ids == ["control:readiness_gate"]


def _seed_process_graph(store: OntologyStore) -> None:
    supplier = store.upsert_object(
        "process",
        "supplier-ordering",
        {
            "name": "Supplier Ordering",
            "domain": "ordering",
            "capabilities": ["supplier schedule generation"],
            "business_rules": ["Supplier schedules are published when service rules are ready."],
            "key_facts": ["Release fact: supplier schedule is activated for replenishment order generation."],
        },
    )
    article = store.upsert_object(
        "process",
        "article-ranging",
        {
            "name": "Article Ranging",
            "domain": "ranging",
            "capabilities": ["assortment and list criteria"],
            "business_rules": ["Article list logic must match the real business use case."],
            "key_facts": ["Activation fact: assortment setup and pricing setup make the article sellable."],
        },
    )
    source_a = store.upsert_object("source", "source-a", {"title": "Supplier Pack", "filename": "supplier.md"})
    source_b = store.upsert_object("source", "source-b", {"title": "Article Pack", "filename": "article.md"})
    owner = store.upsert_object("role", "data owner", {"name": "Data owner"})
    trading = store.upsert_object("role", "trading support", {"name": "Trading Support"})
    system = store.upsert_object("system", "operational master data tool", {"name": "Operational master data tool"})
    control = store.upsert_object("control", "readiness gate", {"name": "Readiness gate"})

    store.link("process_derived_from", supplier.id, source_a.id)
    store.link("process_derived_from", article.id, source_b.id)
    store.link("process_has_role", supplier.id, owner.id)
    store.link("process_has_role", article.id, trading.id)
    store.link("process_uses_system", supplier.id, system.id)
    store.link("process_uses_system", article.id, system.id)
    store.link("process_enforced_by", supplier.id, control.id)
    store.link("process_enforced_by", article.id, control.id)
