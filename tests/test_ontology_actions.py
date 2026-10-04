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
    engine.register_side_effect("record_side_effect", lambda context, result: {})

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
    assert actions["count"] == 9
    by_name = {item["api_name"]: item for item in actions["actions"]}
    assert set(by_name) == {
        "accept_issue",
        "approve_source",
        "publish_version",
        "capture_governance_snapshot",
        "create_improvement_action",
        "rebuild_ontology",
        "reject_source",
        "save_document",
        "transition_improvement_action",
    }
    assert by_name["rebuild_ontology"]["handler_registered"] is True
    assert by_name["rebuild_ontology"]["side_effects_registered"] == {"refresh_ontology_store": True}
    assert by_name["approve_source"]["side_effects_registered"] == {
        "rebuild_ontology": True,
        "record_analytics_event": True,
        "refresh_process_registry": True,
    }

    result = client.post("/api/ontology/actions/rebuild_ontology", json={"params": {}}).json()
    assert result["outcome"] == "ok"
    assert result["action"] == "rebuild_ontology"
    assert result["result"]["side_effects"]["refresh_ontology_store"]["status"] == "rebuilt"

    log = client.get("/api/ontology/actions/log").json()
    assert log["count"] == 1
    assert log["executions"][0]["action"] == "rebuild_ontology"
    actor = log["executions"][0]["actor"]
    assert actor["type"] == "operator" and actor["id"] not in ("operator", "system")  # the signed-in person (REF S3)
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


# ---- REF S3: each action names its permission; what changes knowledge needs a person; the audit names the person ----

def test_every_action_names_a_registered_permission_and_knowledge_changes_need_a_person() -> None:
    from assistant.iam import catalogue

    actions = {a.api_name: a for a in SchemaRegistry.load().schema.action_types}
    for action in actions.values():
        assert action.permission and catalogue.get(action.permission) is not None, action.api_name
    changes_knowledge = {"approve_source", "reject_source", "accept_issue", "save_document", "publish_version"}
    assert {name for name, a in actions.items() if a.requires_human_approval} == changes_knowledge


def test_an_agent_cannot_run_a_knowledge_change_without_a_persons_approval(tmp_path) -> None:
    registry = SchemaRegistry.load()
    engine = ActionsEngine(OntologyStore(tmp_path / "ontology.db", registry=registry), base_dir=tmp_path, registry=registry)
    ran: list[str] = []
    engine.register_handler("approve_source", lambda context: ran.append(context.params["source_id"]) or {})
    engine.register_validation_rule("source_exists", lambda c: ValidationResult(rule="source_exists", passed=True))
    engine.register_validation_rule("not_already_approved", lambda c: ValidationResult(rule="not_already_approved", passed=True))
    engine.register_validation_rule("names_current_text", lambda c: ValidationResult(rule="names_current_text", passed=True))
    for effect in ("refresh_process_registry", "rebuild_ontology", "record_analytics_event"):
        engine.register_side_effect(effect, lambda context, result: {})

    alone = engine.execute("approve_source", {"source_id": "s1", "sha": "0" * 64}, ActionActor(type="agent", id="agent-run-1"))
    assert alone.outcome == "rejected" and alone.failed_rule == "human_approval_required" and ran == []

    approved = engine.execute("approve_source", {"source_id": "s1", "sha": "0" * 64},
                              ActionActor(type="agent", id="agent-run-1", approved_by="user-123"))
    assert approved.outcome == "ok" and ran == ["s1"]
    assert engine.action_log.recent()[0].actor.approved_by == "user-123"


def test_a_governed_action_records_the_signed_in_person(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("KP_DATA_DIR", str(tmp_path))
    client = TestClient(create_app(SourceRegister(tmp_path), AuthService(PASSWORD)))
    token = client.post("/api/auth/login", json={"password": PASSWORD}).json()["token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    me = client.get("/api/auth/me").json()["user"]

    assert client.post("/api/ontology/actions/rebuild_ontology", json={"params": {}}).json()["outcome"] == "ok"
    actor = client.get("/api/ontology/actions/log").json()["executions"][0]["actor"]
    assert actor["id"] == me["id"] and actor["id"] != "operator" and actor["name"] == me["display_name"]


def test_an_action_whose_steps_are_unknown_takes_no_decision(tmp_path) -> None:
    """Every side effect is known before an action's handler takes its decision (REF S23, red team round 11): an
    unregistered one stops the action before the handler runs, so no decision is taken whose steps cannot follow."""
    registry = _action_registry()
    store = OntologyStore(tmp_path / "ontology.db", registry=registry)
    source = store.upsert_object("source", "source-1", {"title": "Supplier Pack"})
    engine = ActionsEngine(store, base_dir=tmp_path, registry=registry)
    engine.register_validation_rule("note_mentions_control", _note_mentions_control)
    ran: list[str] = []
    engine.register_handler("tag_source", lambda context: ran.append("decided") or {})
    result = engine.execute("tag_source", {"source": source.id, "note": "control evidence"},
                            {"type": "operator", "id": "tester"})
    assert result.outcome == "error" and "not registered" in result.message and ran == []
