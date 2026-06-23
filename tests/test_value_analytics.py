"""Value assumptions ledger and dashboard metric tests."""

from fastapi.testclient import TestClient

from assistant.analytics.events import AnalyticsEvent
from assistant.api.app import create_app
from assistant.api.auth import AuthService
from assistant.sources.register import SourceRegister
from assistant.value.ledger import build_value_report

PASSWORD = "value-test-pass"


def test_value_report_calculates_base_scenario_from_assumptions():
    report = build_value_report([])
    base = next(metric for metric in report.metrics if metric.scenario_id == "base")

    assert report.active_scenario_id == "base"
    assert base.gross_annual_benefit_gbp == 714000
    assert base.net_annual_benefit_gbp == 364000
    assert base.simple_payback_years == 3.43
    assert 200000 <= base.npv_gbp <= 205000
    assert base.irr is not None and 0.13 <= base.irr <= 0.15
    assert {assumption.metric for assumption in report.assumptions if assumption.scenario_id == "base"} >= {
        "annual_workstreams",
        "affected_share",
        "delay_reduction_months",
        "monthly_delay_value_gbp",
    }


def test_value_report_exposes_scenario_assumption_matrix():
    report = build_value_report([])
    scenario_ids = {scenario.scenario_id for scenario in report.scenarios}
    annual_workstreams = next(row for row in report.assumption_matrix if row.metric == "annual_workstreams")

    assert {row.metric for row in report.assumption_matrix} >= {
        "annual_workstreams",
        "affected_share",
        "delay_reduction_months",
        "monthly_delay_value_gbp",
    }
    assert set(annual_workstreams.scenario_values) == scenario_ids
    assert annual_workstreams.driver == "portfolio_scale"
    assert annual_workstreams.scenario_values["conservative"].value == 4
    assert annual_workstreams.scenario_values["base"].value == 5
    assert annual_workstreams.scenario_values["stretch"].value == 8
    assert annual_workstreams.value_spread == 4
    assert annual_workstreams.scenario_values["base"].label == "Relevant annual workstreams"
    assert annual_workstreams.scenario_values["base"].source == "docs/evidence/value-hypothesis.md"
    assert annual_workstreams.scenario_values["base"].rationale


def test_value_report_aggregates_observed_value_events():
    events = [
        AnalyticsEvent(
            event_type="value_event_recorded",
            timestamp="2026-06-22T09:00:00Z",
            process_area="supplier setup",
            value_driver="time_saved",
            value_estimate=1250,
            metadata={"label": "SME clarification avoided", "scenario_id": "base", "unit": "GBP", "confidence": "review"},
        ),
        AnalyticsEvent(
            event_type="value_event_recorded",
            timestamp="2026-06-22T10:00:00Z",
            process_area="article setup",
            value_driver="rework_avoided",
            value_estimate=750,
            metadata={"label": "Rework avoided", "scenario_id": "base", "unit": "GBP", "confidence": "review"},
        ),
    ]

    report = build_value_report(events)

    assert report.telemetry["event_count"] == 2
    assert report.telemetry["observed_total_gbp"] == 2000
    assert report.telemetry["synthetic_event_count"] == 0
    assert report.telemetry["by_driver"][0] == {"value_driver": "time_saved", "count": 1, "value_estimate": 1250}
    assert report.telemetry["recent_events"][0]["label"] == "Rework avoided"


def test_value_report_separates_synthetic_historical_value_events():
    events = [
        AnalyticsEvent(
            event_type="value_event_recorded",
            timestamp="2026-06-22T09:00:00Z",
            process_area="supplier setup",
            value_driver="time_saved",
            value_estimate=1000,
            metadata={"label": "Observed event", "scenario_id": "base", "unit": "GBP", "confidence": "review"},
        ),
        AnalyticsEvent(
            event_type="value_event_recorded",
            timestamp="2026-05-10T09:00:00Z",
            process_area="supplier setup",
            value_driver="time_saved",
            value_estimate=250,
            metadata={
                "label": "Synthetic simulator value signal",
                "scenario_id": "base",
                "unit": "GBP",
                "confidence": "synthetic",
                "synthetic_historical": True,
                "evidence_type": "synthetic_period_simulator",
                "run_id": "run-1",
            },
        ),
        AnalyticsEvent(
            event_type="value_event_recorded",
            timestamp="2026-06-10T09:00:00Z",
            process_area="article setup",
            value_driver="rework_avoided",
            value_estimate=500,
            metadata={
                "label": "Synthetic simulator value signal",
                "scenario_id": "base",
                "unit": "GBP",
                "confidence": "synthetic",
                "synthetic_historical": True,
                "evidence_type": "synthetic_period_simulator",
                "run_id": "run-1",
            },
        ),
    ]

    report = build_value_report(events)

    assert report.telemetry["event_count"] == 1
    assert report.telemetry["observed_total_gbp"] == 1000
    assert report.telemetry["synthetic_event_count"] == 2
    assert report.telemetry["synthetic_total_gbp"] == 750
    assert report.telemetry["combined_total_gbp"] == 1750
    by_month = {row["month"]: row for row in report.telemetry["monthly_trend"]}
    assert by_month["2026-05"]["synthetic_gbp"] == 250
    assert by_month["2026-06"]["observed_gbp"] == 1000
    assert by_month["2026-06"]["synthetic_gbp"] == 500
    assert report.telemetry["projection"]["synthetic_ytd_projection_gbp"] == 4500
    assert {event["synthetic_historical"] for event in report.telemetry["recent_events"]} == {False, True}


def test_value_endpoint_is_protected_and_records_operator_value_event(tmp_path):
    register = SourceRegister(tmp_path)
    client = TestClient(create_app(register, AuthService(PASSWORD)))

    assert client.get("/api/analytics/value").status_code == 401

    token = client.post("/api/auth/login", json={"password": PASSWORD}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        "/api/analytics/value/events",
        headers=headers,
        json={
            "label": "Manual clarification avoided",
            "value_driver": "time_saved",
            "value_estimate": 500,
            "process_area": "supplier setup",
            "scenario_id": "base",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["telemetry"]["event_count"] == 1
    assert body["telemetry"]["observed_total_gbp"] == 500
    assert body["telemetry"]["recent_events"][0]["process_area"] == "supplier setup"
    endpoint_body = client.get("/api/analytics/value", headers=headers).json()
    assert endpoint_body["telemetry"]["event_count"] == 1
    assert endpoint_body["assumption_matrix"][0]["scenario_values"]["base"]["source"] == "docs/evidence/value-hypothesis.md"
