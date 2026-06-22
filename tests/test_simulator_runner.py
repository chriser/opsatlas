"""Tests for the synthetic persona simulator runner."""

from __future__ import annotations

from fastapi.testclient import TestClient

from assistant.analytics.event_store import AnalyticsEventStore
from assistant.answer.service import REFUSAL, AnswerResult, AnswerService
from assistant.api.app import create_app
from assistant.api.auth import AuthService
from assistant.ingestion.store import SectionStore
from assistant.retrieval.service import RetrievalService
from assistant.simulator.runner import SimulationRunConfig, SimulationRunner, SimulationRunStore, _observed_behavior
from assistant.simulator.scenarios import load_scenario_catalogue, select_scenarios
from assistant.sources.register import SourceRegister

PASSWORD = "sim-test-pass"


class FakeGenerator:
    def generate(self, prompt: str) -> str:
        if "approve" in prompt.lower():
            return "I cannot approve this. A human reviewer must make that decision."
        return "The available process evidence supports this answer [1]."


def _answer_stack(tmp_path) -> tuple[AnswerService, AnalyticsEventStore, SimulationRunStore]:
    register = SourceRegister(tmp_path)
    section_store = SectionStore(register.base_dir)
    retrieval = RetrievalService(register, section_store)
    events = AnalyticsEventStore(register.base_dir)
    runs = SimulationRunStore(register.base_dir)
    answer = AnswerService(retrieval, FakeGenerator(), event_store=events)
    return answer, events, runs


def test_scenario_selection_is_repeatable_with_seed():
    catalogue = load_scenario_catalogue()

    first = select_scenarios(catalogue, persona_ids=["new_starter"], seed=42)
    second = select_scenarios(catalogue, persona_ids=["new_starter"], seed=42)

    assert [scenario.scenario_id for scenario in first] == [scenario.scenario_id for scenario in second]
    assert first
    assert {scenario.persona_id for scenario in first} == {"new_starter"}


def test_runner_records_persona_ask_events_and_run_summary(tmp_path):
    answer, events, runs = _answer_stack(tmp_path)
    runner = SimulationRunner(load_scenario_catalogue(), answer, events, runs)

    run = runner.run(SimulationRunConfig(
        scenario_ids=["sim-compliance-reviewer-out-of-scope-safety"],
        max_questions=2,
        top_k=3,
    ))

    assert run.summary.total_questions == 2
    assert run.summary.guardrail_blocks >= 1
    assert runs.recent(1)[0].run_id == run.run_id

    facts = events.events()
    assert facts[0].event_type == "simulation_run_started"
    assert facts[-1].event_type == "simulation_run_completed"
    ask_events = [event for event in facts if event.event_type.startswith("ask_")]
    assert len(ask_events) == 2
    assert {event.actor_type for event in ask_events} == {"persona"}
    assert {event.persona for event in ask_events} == {"compliance_reviewer"}
    assert {event.process_area for event in ask_events} == {"safety-boundary"}
    assert {event.value_driver for event in ask_events} == {"risk_reduction"}
    assert all(event.metadata["run_id"] == run.run_id for event in ask_events)
    assert all(event.metadata["scenario_id"] == "sim-compliance-reviewer-out-of-scope-safety" for event in ask_events)
    assert "weather forecast" not in events.path.read_text(encoding="utf-8")


def test_decline_expectation_treats_refused_action_as_declined():
    answer = AnswerResult(answer=REFUSAL, citations=[], mode="retrieval", refused=True)

    assert _observed_behavior(answer, "decline") == "decline"


def test_simulator_api_is_protected_and_runs_selected_scenarios(tmp_path):
    register = SourceRegister(tmp_path)
    section_store = SectionStore(register.base_dir)
    retrieval = RetrievalService(register, section_store)
    answer = AnswerService(retrieval, FakeGenerator())
    client = TestClient(create_app(register, AuthService(PASSWORD), retrieval=retrieval, answer=answer))

    assert client.get("/api/simulator/scenarios").status_code == 401

    token = client.post("/api/auth/login", json={"password": PASSWORD}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    catalogue = client.get("/api/simulator/scenarios", headers=headers).json()
    assert len(catalogue["personas"]) >= 6

    response = client.post(
        "/api/simulator/runs",
        json={"scenario_ids": ["sim-compliance-reviewer-out-of-scope-safety"], "max_questions": 1, "seed": 7},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["scenario_count"] == 1
    assert body["summary"]["total_questions"] == 1
    assert client.get("/api/simulator/runs", headers=headers).json()[0]["run_id"] == body["run_id"]
