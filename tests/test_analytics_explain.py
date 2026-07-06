"""Analytics computation trace endpoint tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from assistant.analytics.log import UsageEntry
from assistant.api.app import create_app
from assistant.api.auth import AuthService
from assistant.sources.register import SourceRegister

PASSWORD = "explain-test-pass"


def test_analytics_explain_traces_match_reported_metrics(tmp_path) -> None:
    client = TestClient(create_app(SourceRegister(tmp_path), AuthService(PASSWORD)))

    assert client.get("/api/analytics/explain").status_code == 401

    token = client.post("/api/auth/login", json={"password": PASSWORD}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    _seed_trace_data(client)

    explain = client.get("/api/analytics/explain", headers=headers)
    assert explain.status_code == 200
    traces = {trace["metric_id"]: trace for trace in explain.json()["traces"]}

    assert {
        "coverage_score",
        "knowledge_gap_silhouette",
        "value_dcf",
        "value_forecast_projection",
        "process_complexity",
    } <= set(traces)

    scorecard = client.get("/api/analytics/scorecard", headers=headers).json()
    assert traces["coverage_score"]["output"]["answer_rate"] == scorecard["answer_rate"]
    assert traces["coverage_score"]["output"]["grounded_rate"] == scorecard["grounded_rate"]

    gaps = client.get("/api/analytics/knowledge-gaps", headers=headers).json()
    assert traces["knowledge_gap_silhouette"]["output"]["silhouette_score"] == gaps["silhouette_score"]

    value = client.get("/api/analytics/value", headers=headers).json()
    active = next(metric for metric in value["metrics"] if metric["scenario_id"] == value["active_scenario_id"])
    assert traces["value_dcf"]["output"]["npv_gbp"] == active["npv_gbp"]
    assert traces["value_dcf"]["output"]["irr"] == active["irr"]
    assert (
        traces["value_forecast_projection"]["output"]["combined_ytd_projection_gbp"]
        == value["telemetry"]["projection"]["combined_ytd_projection_gbp"]
    )

    complexity = client.get("/api/analytics/process-complexity", headers=headers).json()
    assert traces["process_complexity"]["output"]["average_complexity"] == complexity["average_complexity"]
    assert traces["process_complexity"]["output"]["process_count"] == complexity["process_count"]

    single = client.get("/api/analytics/explain/value_dcf", headers=headers)
    assert single.status_code == 200
    assert single.json()["substituted_formula"]
    assert client.get("/api/analytics/explain/not-a-metric", headers=headers).status_code == 404


def _seed_trace_data(client: TestClient) -> None:
    client.app.state.answer.usage_log.append(
        UsageEntry(
            timestamp="2026-07-06T08:00:00+00:00",
            question="Who owns supplier ordering?",
            mode="ask",
            answer_path="oag",
            refused=False,
            confidence="grounded",
            citation_count=2,
        )
    )
    client.app.state.answer.usage_log.append(
        UsageEntry(
            timestamp="2026-07-06T08:05:00+00:00",
            question="Which control is missing?",
            mode="ask",
            answer_path="rag",
            refused=True,
            confidence="none",
            citation_count=0,
        )
    )
    client.app.state.analytics_events.record(
        "value_event_recorded",
        timestamp="2026-07-01T10:00:00+00:00",
        actor_type="operator",
        entity_type="value_event",
        entity_id="value-1",
        process_area="supplier setup",
        outcome="recorded",
        value_driver="time_saved",
        value_estimate=120.0,
        metadata={"label": "Manual review avoided", "scenario_id": "base", "unit": "GBP", "confidence": "review"},
    )
    client.app.state.analytics_events.record(
        "value_event_recorded",
        timestamp="2026-07-03T10:00:00+00:00",
        actor_type="operator",
        entity_type="value_event",
        entity_id="value-2",
        process_area="supplier setup",
        outcome="recorded",
        value_driver="rework_avoided",
        value_estimate=80.0,
        metadata={"label": "Rework avoided", "scenario_id": "base", "unit": "GBP", "confidence": "review"},
    )
