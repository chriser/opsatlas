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


def test_clear_removes_objects_and_links(store: OntologyStore) -> None:
    process = store.upsert_object("process", "supplier-setup", {"name": "Supplier Setup"})
    system = store.upsert_object("system", "integration-layer", {"name": "Integration Layer"})
    store.link("process_uses_system", process.id, system.id)

    store.clear()

    assert store.counts() == {"objects": {}, "links": {}, "total_objects": 0, "total_links": 0}
    assert store.get(process.id) is None


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
    """The budget is 2 seconds for 1,000 objects, measured as the best of three runs on fresh stores, so a load spike from
    other work on the machine (parallel gates) does not read as a regression; a real one fails all three (REF S69)."""
    timings = []
    for attempt in range(3):
        store = OntologyStore(tmp_path / f"ontology-{attempt}.db", registry=SchemaRegistry.load())
        started = time.perf_counter()
        for index in range(1000):
            store.upsert_object("role", f"role-{index}", {"name": f"Role {index}"})
        timings.append(time.perf_counter() - started)
        assert store.counts()["objects"] == {"role": 1000}
        if timings[-1] < 2.0:
            break
    assert min(timings) < 2.0, timings


def test_a_rebuild_is_one_transaction_readers_wait_for_the_finished_map_and_a_failure_keeps_the_old_one(tmp_path):
    """ARCH F2: the map was cleared and refilled in separate commits, so a question asked meanwhile could see it empty."""
    import threading

    store = OntologyStore(tmp_path / "ontology.db")
    store.upsert_object("source", "old-1", {"title": "Old one"}, source_ref="old-1")
    store.upsert_object("source", "old-2", {"title": "Old two"}, source_ref="old-2")
    half_way, carry_on, seen = threading.Event(), threading.Event(), {}

    def rebuild():
        with store.rebuilding():
            store.upsert_object("source", "new-1", {"title": "New one"}, source_ref="new-1")
            assert [o.properties["title"] for o in store.find("source")] == ["New one"]  # the rebuild reads its own writes
            half_way.set()
            carry_on.wait(5)
            store.upsert_object("source", "new-2", {"title": "New two"}, source_ref="new-2")

    def read():
        seen["counts"] = store.counts()["total_objects"]
    builder, reader = threading.Thread(target=rebuild), threading.Thread(target=read)
    builder.start()
    assert half_way.wait(5)
    reader.start()
    reader.join(0.3)
    assert reader.is_alive() and "counts" not in seen  # a reader waits; it never sees the half-built map
    carry_on.set()
    builder.join(5)
    reader.join(5)
    assert seen["counts"] == 2 and sorted(o.properties["title"] for o in store.find("source")) == ["New one", "New two"]

    class Boom(Exception):
        pass
    with pytest.raises(Boom):
        with store.rebuilding():
            store.upsert_object("source", "half", {"title": "Half"}, source_ref="half")
            raise Boom()
    assert sorted(o.properties["title"] for o in store.find("source")) == ["New one", "New two"]  # rolled back
