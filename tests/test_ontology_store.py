"""Ontology SQLite store tests."""

from __future__ import annotations

import time

import pytest

from assistant.ontology import OntologyStore, SchemaRegistry
from assistant.ontology.store import object_id_for


@pytest.fixture
def store(tmp_path) -> OntologyStore:
    return OntologyStore(tmp_path / "ontology.db", registry=SchemaRegistry.load())


def test_store_upserts_finds_links_and_traverses_objects(store: OntologyStore) -> None:
    process = store.upsert_object("process", "supplier-setup", {"name": "Supplier Setup", "domain": "Supplier"})
    system = store.upsert_object("system", "integration-layer", {"name": "Integration Layer"})
    role = store.upsert_object("role", "finance-approver", {"name": "Finance approver"})

    process_again = store.upsert_object(
        "process",
        "supplier-setup",
        {"name": "Supplier Setup v2", "domain": "Supplier", "business_rules": ["Check contracts"]},
    )
    link = store.link("process_uses_system", process.id, system.id)
    store.link("process_has_role", process.id, role.id)

    assert process_again.id == process.id
    assert process_again.created_at == process.created_at
    assert process_again.properties["name"] == "Supplier Setup v2"
    assert link.from_id == process.id
    assert store.get(process.id) == process_again
    assert store.find("process", {"domain": "Supplier"}) == [process_again]
    assert store.find("process", contains="contracts") == [process_again]
    assert store.traverse(process.id, "process_uses_system") == [system]
    assert store.traverse(system.id, "process_uses_system", direction="in") == [process_again]

    neighbors = store.neighbors(process.id)
    assert neighbors["process_uses_system"]["out"] == [system]
    assert neighbors["process_has_role"]["out"] == [role]


def test_store_rejects_unknown_schema_writes(store: OntologyStore) -> None:
    process = store.upsert_object("process", "supplier-setup", {"name": "Supplier Setup"})
    system = store.upsert_object("system", "integration-layer", {"name": "Integration Layer"})

    with pytest.raises(KeyError, match="Unknown ontology object type"):
        store.upsert_object("unknown", "x", {"name": "X"})
    with pytest.raises(ValueError, match="Unknown properties"):
        store.upsert_object("process", "supplier-setup", {"name": "Supplier Setup", "unexpected": "x"})
    with pytest.raises(ValueError, match="must be string_list"):
        store.upsert_object("process", "bad-rules", {"name": "Bad Rules", "business_rules": "not a list"})
    with pytest.raises(KeyError, match="Unknown ontology link type"):
        store.link("unknown_link", process.id, system.id)
    with pytest.raises(ValueError, match="expects from_type process"):
        store.link("process_uses_system", system.id, process.id)


def test_delete_object_cascades_links(store: OntologyStore) -> None:
    process = store.upsert_object("process", "supplier-setup", {"name": "Supplier Setup"})
    system = store.upsert_object("system", "integration-layer", {"name": "Integration Layer"})
    store.link("process_uses_system", process.id, system.id)

    assert store.counts()["total_links"] == 1
    assert store.delete_object(system.id) is True
    assert store.counts()["total_links"] == 0
    assert store.traverse(process.id, "process_uses_system") == []
    assert store.delete_object(system.id) is False


def test_rebuild_style_upserts_are_idempotent(store: OntologyStore) -> None:
    for _ in range(3):
        process = store.upsert_object("process", "article-setup", {"name": "Article Setup"})
        system = store.upsert_object("system", "master-data-tool", {"name": "Master Data Tool"})
        store.link("process_uses_system", process.id, system.id)

    assert store.counts() == {
        "objects": {"process": 1, "system": 1},
        "links": {"process_uses_system": 1},
        "total_objects": 2,
        "total_links": 1,
    }


def test_object_id_is_stable_and_readable() -> None:
    assert object_id_for("system", "Integration Layer") == "system:integration_layer"


def test_synthetic_scale_1000_objects_runs_under_two_seconds(tmp_path) -> None:
    store = OntologyStore(tmp_path / "ontology.db", registry=SchemaRegistry.load())

    started = time.perf_counter()
    for index in range(1000):
        store.upsert_object("role", f"role-{index}", {"name": f"Role {index}"})
    elapsed = time.perf_counter() - started

    assert store.counts()["objects"] == {"role": 1000}
    assert elapsed < 2.0
