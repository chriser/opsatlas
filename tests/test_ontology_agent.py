"""Ontology agent loop tests."""

from __future__ import annotations

import json

from assistant.observability.trace import AuditTrace
from assistant.ontology import AgentRunStore, OntologyAgent, OntologyQueryService, OntologyStore, SchemaRegistry
from assistant.ontology.store import object_id_for


class ScriptedGenerator:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if not self.responses:
            return '{"final_answer":"No scripted response left."}'
        return self.responses.pop(0)


def test_agent_answers_two_hop_control_question_and_persists_trace(tmp_path) -> None:
    query = _seed_query(tmp_path)
    generator = ScriptedGenerator([
        json.dumps({"tool": "search_objects", "args": {"type": "system", "query": "integration layer"}}),
        json.dumps({
            "tool": "traverse_links",
            "args": {
                "from_id": object_id_for("system", "integration layer"),
                "link_type": "process_uses_system",
                "direction": "in",
            },
        }),
        json.dumps({
            "tool": "traverse_links",
            "args": {
                "from_id": object_id_for("process", "supplier setup"),
                "link_type": "process_enforced_by",
                "direction": "out",
            },
        }),
        json.dumps({"final_answer": "The process using Integration Layer is Supplier Setup, governed by Readiness gate."}),
    ])
    store = AgentRunStore(tmp_path)
    audit = AuditTrace(tmp_path)
    agent = OntologyAgent(query, generator, store=store, audit_trace=audit)

    trace = agent.run("Which controls govern the processes that use Integration Layer?")

    assert trace.final_answer == "The process using Integration Layer is Supplier Setup, governed by Readiness gate."
    assert [step.tool for step in trace.steps] == ["search_objects", "traverse_links", "traverse_links"]
    assert trace.steps[0].result_summary == "Found 1 system object(s)."
    assert trace.steps[2].result_summary == "Traversed 1 linked object(s)."
    assert store.recent()[0].run_id == trace.run_id
    assert audit.recent()[0]["run_id"] == trace.run_id
    assert all("raw workshop transcript paragraph" not in prompt for prompt in generator.prompts)


def test_agent_recovers_once_from_malformed_tool_json(tmp_path) -> None:
    query = _seed_query(tmp_path)
    generator = ScriptedGenerator(["not json", '{"final_answer":"Recovered from protocol error."}'])
    agent = OntologyAgent(query, generator, store=AgentRunStore(tmp_path))

    trace = agent.run("Which roles are involved?")

    assert trace.final_answer == "Recovered from protocol error."
    assert trace.stopped_reason == "final_answer"
    assert trace.steps == []
    assert len(generator.prompts) == 2
    assert "Tool protocol error" in generator.prompts[1]


def test_agent_stops_at_step_cap(tmp_path) -> None:
    query = _seed_query(tmp_path)
    generator = ScriptedGenerator([
        '{"tool":"search_objects","args":{"type":"process","query":"supplier"}}',
        '{"tool":"search_objects","args":{"type":"process","query":"supplier"}}',
        '{"tool":"search_objects","args":{"type":"process","query":"supplier"}}',
    ])
    agent = OntologyAgent(query, generator, max_steps=2)

    trace = agent.run("Keep searching")

    assert trace.stopped_reason == "step_cap"
    assert "step limit" in trace.final_answer
    assert len(trace.steps) == 2


def test_agent_propose_action_never_executes_mutation(tmp_path) -> None:
    query = _seed_query(tmp_path)
    generator = ScriptedGenerator([
        json.dumps({
            "tool": "propose_action",
            "args": {
                "action": "accept_issue",
                "params": {"source_id": "src-1", "check": "metadata_title", "detail": "Accepted as-is."},
                "rationale": "Operator should confirm the issue is intentionally accepted.",
            },
        }),
        json.dumps({"final_answer": "I proposed accepting the issue for human review."}),
    ])
    agent = OntologyAgent(query, generator, store=AgentRunStore(tmp_path))

    trace = agent.run("Can you accept this issue?")

    assert trace.proposed_actions[0].action == "accept_issue"
    assert trace.proposed_actions[0].status == "pending"
    assert trace.steps[0].result_summary == "Proposed action accept_issue; awaiting human approval."
    assert not (tmp_path / "action_log.json").exists()


def _seed_query(tmp_path) -> OntologyQueryService:
    store = OntologyStore(tmp_path / "ontology.db", registry=SchemaRegistry.load())
    process = store.upsert_object(
        "process",
        "supplier setup",
        {
            "name": "Supplier Setup",
            "domain": "supplier",
            "business_rules": ["Use approved records only."],
        },
        source_ref="source:pack-1",
    )
    system = store.upsert_object("system", "integration layer", {"name": "Integration Layer"})
    control = store.upsert_object("control", "readiness gate", {"name": "Readiness gate"})
    role = store.upsert_object("role", "finance approver", {"name": "Finance approver"})
    store.link("process_uses_system", process.id, system.id)
    store.link("process_enforced_by", process.id, control.id)
    store.link("process_has_role", process.id, role.id)
    return OntologyQueryService(store)
