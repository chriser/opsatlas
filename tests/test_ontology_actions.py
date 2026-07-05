"""Governed ontology action engine tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from assistant.api.app import create_app
from assistant.api.auth import AuthService
from assistant.ontology import ActionActor, ActionsEngine, OntologyStore, SchemaRegistry, ValidationResult
from assistant.ontology.actions import ActionContext
from assistant.sources.register import SourceRegister

PASSWORD = "test-pass"


def test_actions_engine_executes_handler_side_effect_and_audits_ok(tmp_path) -> None:
    registry = _action_registry()
    store = OntologyStore(tmp_path / "ontology.db", registry=registry)
    source = store.upsert_object("source", "source-1", {"title": "Supplier Pack"})
    engine = ActionsEngine(store, base_dir=tmp_path, registry=registry)
    calls: list[dict] = []

    def handler(context: ActionContext) -> dict:
        calls.append(context.params)
        return {"updated_source": context.params["source"]}

    engine.register_validation_rule("note_mentions_control", _note_mentions_control)
    engine.register_handler("tag_source", handler)
    engine.register_side_effect("record_side_effect", lambda context, result: {"recorded": result["updated_source"]})

    result = engine.execute(
        "tag_source",
        {"source": source.id, "note": "control " + ("x" * 340)},
        ActionActor(type="operator", id="tester"),
    )

    assert result.outcome == "ok"
    assert calls == [{"source": source.id, "note": "control " + ("x" * 340)}]
    assert result.result["handler"] == {"updated_source": source.id}
    assert result.result["side_effects"] == {"record_side_effect": {"recorded": source.id}}

    audit = engine.action_log.recent()[0]
    assert audit.execution_id == result.execution_id
    assert audit.action == "tag_source"
    assert audit.actor.type == "operator"
    assert audit.actor.id == "tester"
    assert audit.outcome == "ok"
    assert audit.validation_results[0].rule == "parameters"
    assert audit.validation_results[0].passed is True
    assert audit.params["note"].endswith("[truncated 48 chars]")


def test_actions_engine_rejects_invalid_object_reference_without_calling_handler(tmp_path) -> None:
    registry = _action_registry()
    store = OntologyStore(tmp_path / "ontology.db", registry=registry)
    engine = ActionsEngine(store, base_dir=tmp_path, registry=registry)
    called = False

    def handler(context: ActionContext) -> dict:
        nonlocal called
        called = True
        return {}

    engine.register_handler("tag_source", handler)

    result = engine.execute(
        "tag_source",
        {"source": "source:missing", "note": "control"},
        {"type": "operator", "id": "tester"},
    )

    assert result.outcome == "rejected"
    assert result.failed_rule == "parameters"
    assert "unknown ontology object id source:missing" in result.message
    assert called is False
    assert engine.action_log.recent()[0].outcome == "rejected"


def test_actions_engine_captures_handler_errors_in_audit_log(tmp_path) -> None:
    registry = _action_registry()
    store = OntologyStore(tmp_path / "ontology.db", registry=registry)
    source = store.upsert_object("source", "source-1", {"title": "Supplier Pack"})
    engine = ActionsEngine(store, base_dir=tmp_path, registry=registry)
    engine.register_validation_rule("note_mentions_control", _note_mentions_control)

    def explode(context: ActionContext) -> dict:
        raise RuntimeError("handler boom")

    engine.register_handler("tag_source", explode)

    result = engine.execute(
        "tag_source",
        {"source": source.id, "note": "control evidence"},
        {"type": "operator", "id": "tester"},
    )

    assert result.outcome == "error"
    assert result.message == "handler boom"
    audit = engine.action_log.recent()[0]
    assert audit.outcome == "error"
    assert audit.message == "handler boom"


def test_ontology_actions_api_lists_executes_and_returns_log(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("KP_DATA_DIR", str(tmp_path))
    client = TestClient(create_app(SourceRegister(tmp_path), AuthService(PASSWORD)))

    assert client.get("/api/ontology/actions").status_code == 401
    token = client.post("/api/auth/login", json={"password": PASSWORD}).json()["token"]
    client.headers.update({"Authorization": f"Bearer {token}"})

    actions = client.get("/api/ontology/actions").json()
    assert actions["count"] == 1
    assert actions["actions"][0]["api_name"] == "rebuild_ontology"
    assert actions["actions"][0]["handler_registered"] is True
    assert actions["actions"][0]["side_effects_registered"] == {"refresh_ontology_store": True}

    result = client.post("/api/ontology/actions/rebuild_ontology", json={"params": {}}).json()
    assert result["outcome"] == "ok"
    assert result["action"] == "rebuild_ontology"
    assert result["result"]["side_effects"]["refresh_ontology_store"]["status"] == "rebuilt"

    log = client.get("/api/ontology/actions/log").json()
    assert log["count"] == 1
    assert log["executions"][0]["action"] == "rebuild_ontology"
    assert log["executions"][0]["actor"] == {"type": "operator", "id": "operator", "approved_by": None}
    assert log["executions"][0]["outcome"] == "ok"

    assert client.post("/api/ontology/actions/missing", json={"params": {}}).status_code == 404


def _note_mentions_control(context: ActionContext) -> ValidationResult:
    if "control" in context.params.get("note", "").lower():
        return ValidationResult(rule="note_mentions_control", passed=True, message="Control context present.")
    return ValidationResult(rule="note_mentions_control", passed=False, message="Note must mention the control.")


def _action_registry() -> SchemaRegistry:
    return SchemaRegistry.from_dict({
        "schema_version": "test-actions.v1",
        "object_types": [
            {
                "api_name": "source",
                "display_name": "Source",
                "primary_key": "source_id",
                "properties": [
                    {"name": "source_id", "base_type": "string", "required": True},
                    {"name": "title", "base_type": "string", "required": True},
                ],
            }
        ],
        "link_types": [],
        "action_types": [
            {
                "api_name": "tag_source",
                "display_name": "Tag Source",
                "parameters": [
                    {"name": "source", "type": "object", "object_type": "source"},
                    {"name": "note", "type": "string"},
                ],
                "validation_rules": ["auth_required", "note_mentions_control"],
                "edit_kind": "custom",
                "side_effects": ["record_side_effect"],
            }
        ],
    })
