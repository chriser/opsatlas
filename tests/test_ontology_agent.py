"""Ontology agent loop tests."""

from __future__ import annotations

import json

from assistant.observability.trace import AuditTrace
from assistant.ontology import (
    AgentRunStore,
    OntologyAgent,
    OntologyQueryService,
    OntologyStore,
    PendingActionStore,
    SchemaRegistry,
)
from assistant.ontology.agent import NO_EVIDENCE_ANSWER
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
    assert trace.evidence_reads == 3
    assert store.recent()[0].run_id == trace.run_id
    assert audit.recent()[0]["run_id"] == trace.run_id
    assert all("raw workshop transcript paragraph" not in prompt for prompt in generator.prompts)


def test_agent_recovers_once_from_malformed_tool_json(tmp_path) -> None:
    query = _seed_query(tmp_path)
    generator = ScriptedGenerator([
        "not json",
        '{"tool":"search_objects","args":{"type":"process","query":"supplier setup"}}',
        '{"final_answer":"Recovered from protocol error."}',
    ])
    agent = OntologyAgent(query, generator, store=AgentRunStore(tmp_path))

    trace = agent.run("Which roles are involved?")

    assert trace.final_answer == "Recovered from protocol error."
    assert trace.stopped_reason == "final_answer"
    assert [step.tool for step in trace.steps] == ["search_objects"]
    assert trace.evidence_reads == 1
    assert len(generator.prompts) == 3
    assert "Tool protocol error" in generator.prompts[1]


def test_agent_returns_no_evidence_when_protocol_fails_before_any_relevant_read(tmp_path) -> None:
    query = _seed_query(tmp_path)
    generator = ScriptedGenerator(["not json", "still not json"])
    agent = OntologyAgent(query, generator)

    trace = agent.run("What happens if a supplier goes bankrupt?")

    assert trace.stopped_reason == "no_evidence"
    assert trace.final_answer == NO_EVIDENCE_ANSWER
    assert trace.evidence_reads == 0
    assert trace.steps == []


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
    assert trace.evidence_reads == 2


def test_contingency_stops_after_three_reads_without_condition_evidence(tmp_path) -> None:
    query = _seed_query(tmp_path)
    process_id = object_id_for("process", "supplier setup")
    generator = ScriptedGenerator([
        '{"tool":"search_objects","args":{"type":"process","query":"supplier setup"}}',
        json.dumps({
            "tool": "traverse_links",
            "args": {
                "from_id": process_id,
                "link_type": "process_uses_system",
                "direction": "out",
            },
        }),
        json.dumps({
            "tool": "traverse_links",
            "args": {
                "from_id": process_id,
                "link_type": "process_enforced_by",
                "direction": "out",
            },
        }),
        "not json and must not be consumed",
    ])
    agent = OntologyAgent(query, generator)

    trace = agent.run("What happens if a supplier goes bankrupt?")

    assert trace.stopped_reason == "no_evidence"
    assert trace.final_answer == NO_EVIDENCE_ANSWER
    assert trace.evidence_reads == 0
    assert len(trace.steps) == 3
    assert all("No direct evidence matched the contingency condition" in step.result_summary for step in trace.steps)
    assert generator.responses == ["not json and must not be consumed"]


def test_agent_rejects_traversal_from_wrong_object_type(tmp_path) -> None:
    query = _seed_query(tmp_path)
    generator = ScriptedGenerator([
        json.dumps({
            "tool": "traverse_links",
            "args": {
                "from_id": object_id_for("role", "finance approver"),
                "link_type": "process_uses_system",
                "direction": "out",
            },
        }),
        '{"final_answer":"A role is not a process."}',
    ])
    agent = OntologyAgent(query, generator)

    trace = agent.run("Which systems does the finance approver use?")

    assert trace.stopped_reason == "no_evidence"
    assert trace.final_answer == NO_EVIDENCE_ANSWER
    assert trace.steps[0].result_summary == (
        "traverse_links rejected: out process_uses_system traversal must start from process."
    )


def test_agent_parses_json_object_wrapped_in_model_reasoning(tmp_path) -> None:
    query = _seed_query(tmp_path)
    generator = ScriptedGenerator([
        '<think>Choose a process search.</think>\n'
        '{"tool":"search_objects","args":{"type":"process","query":"supplier setup"}}\nDone.',
        '<think>Use the evidence.</think>\n{"final_answer":"Supplier Setup is recorded."}\nDone.',
    ])
    agent = OntologyAgent(query, generator)

    trace = agent.run("Show Supplier Setup")

    assert trace.stopped_reason == "final_answer"
    assert trace.final_answer == "Supplier Setup is recorded."
    assert trace.evidence_reads == 1


def test_agent_propose_action_never_executes_mutation(tmp_path) -> None:
    query = _seed_query(tmp_path)
    generator = ScriptedGenerator([
        '{"tool":"search_objects","args":{"type":"process","query":"supplier setup"}}',
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
    assert trace.steps[1].result_summary == "Proposed action accept_issue; awaiting human approval."
    assert not (tmp_path / "action_log.json").exists()


def test_agent_rejects_action_proposal_without_ontology_evidence(tmp_path) -> None:
    query = _seed_query(tmp_path)
    generator = ScriptedGenerator([
        json.dumps({
            "tool": "propose_action",
            "args": {
                "action": "create_improvement_action",
                "params": {"title": "Review supplier continuity"},
                "rationale": "A supplier may become bankrupt.",
            },
        }),
        json.dumps({"final_answer": "I proposed an action."}),
    ])
    agent = OntologyAgent(query, generator, store=AgentRunStore(tmp_path))

    trace = agent.run("What happens if a supplier goes bankrupt?")

    assert trace.final_answer == NO_EVIDENCE_ANSWER
    assert trace.stopped_reason == "no_evidence"
    assert trace.evidence_reads == 0
    assert trace.proposed_actions == []
    assert trace.steps[0].result_summary == "propose_action rejected: retrieve relevant ontology evidence first."


def test_agent_rejects_pipe_delimited_object_type_and_prompt_uses_concrete_example(tmp_path) -> None:
    query = _seed_query(tmp_path)
    generator = ScriptedGenerator([
        '{"tool":"search_objects","args":{"type":"process|role|system","query":"supplier"}}',
        '{"final_answer":"A generic supplier answer."}',
    ])
    agent = OntologyAgent(query, generator)

    trace = agent.run("What happens if a supplier goes bankrupt?")

    assert trace.stopped_reason == "no_evidence"
    assert trace.final_answer == NO_EVIDENCE_ANSWER
    assert trace.proposed_actions == []
    assert "type must be one of" in trace.steps[0].result_summary
    assert '"type":"process|role' not in generator.prompts[0]
    assert '"type":"process"' in generator.prompts[0]


def test_agent_collapses_duplicate_proposals(tmp_path) -> None:
    query = _seed_query(tmp_path)
    proposal = {
        "tool": "propose_action",
        "args": {
            "action": "accept_issue",
            "params": {"source_id": "src-1", "check": "metadata_title", "detail": "Accepted as-is."},
            "rationale": "Operator should confirm the issue.",
        },
    }
    generator = ScriptedGenerator([
        '{"tool":"search_objects","args":{"type":"process","query":"supplier setup"}}',
        json.dumps(proposal),
        json.dumps(proposal),
        '{"final_answer":"One action is ready for human review."}',
    ])
    agent = OntologyAgent(query, generator)

    trace = agent.run("Investigate Supplier Setup")

    assert trace.stopped_reason == "final_answer"
    assert len(trace.proposed_actions) == 1
    assert trace.steps[2].result_summary == "Duplicate proposal accept_issue suppressed."


def test_step_capped_run_does_not_enter_pending_action_store(tmp_path) -> None:
    query = _seed_query(tmp_path)
    generator = ScriptedGenerator([
        '{"tool":"search_objects","args":{"type":"process","query":"supplier setup"}}',
        json.dumps({
            "tool": "propose_action",
            "args": {
                "action": "accept_issue",
                "params": {"source_id": "src-1", "check": "metadata_title", "detail": "Accepted as-is."},
                "rationale": "Operator should confirm the issue.",
            },
        }),
    ])
    agent = OntologyAgent(query, generator, max_steps=2)
    pending = PendingActionStore(tmp_path)

    trace = agent.run("Investigate Supplier Setup")

    assert trace.stopped_reason == "step_cap"
    assert len(trace.proposed_actions) == 1
    assert pending.add_from_trace(trace) == []
    assert pending.list() == []


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
