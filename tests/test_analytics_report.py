"""Exportable analytics report tests."""

from fastapi.testclient import TestClient

from assistant.analytics.report import build_analytics_report
from assistant.api.app import create_app
from assistant.api.auth import AuthService
from assistant.sources.register import SourceRegister

PASSWORD = "report-test-pass"


def test_analytics_report_contains_method_summary_without_raw_gap_questions():
    report = build_analytics_report(
        scorecard={"total_queries": 3, "answer_rate": 0.67, "grounded_rate": 0.67},
        history={"event_count": 4},
        governance={"open_count": 1, "resolved_count": 2, "mean_time_to_resolve_hours": 5},
        gaps={
            "cluster_count": 1,
            "total_candidates": 2,
            "silhouette_score": 0.42,
            "clusters": [
                {
                    "label": "Control gaps",
                    "process_area": "Supplier setup",
                    "question_count": 2,
                    "friction_score": 55,
                    "representative_questions": ["raw prompt should not appear"],
                }
            ],
        },
        complexity={
            "average_complexity": 61,
            "processes": [
                {
                    "name": "Supplier setup",
                    "complexity_score": 75,
                    "complexity_band": "high",
                    "key_person_risk_score": 40,
                    "key_person_risk_band": "medium",
                    "indicators": ["Multiple role hand-offs"],
                }
            ],
        },
        value={
            "active_scenario_id": "base",
            "telemetry": {"event_count": 1},
            "metrics": [
                {
                    "scenario_id": "base",
                    "label": "P50 base",
                    "gross_annual_benefit_gbp": 714000,
                    "net_annual_benefit_gbp": 364000,
                    "simple_payback_years": 3.43,
                    "npv_gbp": 203000,
                    "irr": 0.14,
                }
            ],
        },
        validation={
            "summary": {"validation_protocol_count": 2},
            "validation_protocols": [
                {"protocol_id": "VAL-RAG-001", "component": "RAG", "status": "active", "boundary": "Approved sources only."}
            ],
            "caveats": ["Assumptions-led."],
        },
        generated_at="2026-06-22T10:00:00Z",
    )

    assert "# AI Knowledge and Analytics Assistant - Analytics Evidence Report" in report
    assert "## Analytics Method" in report
    assert "P50 base" in report
    assert "VAL-RAG-001" in report
    assert "raw prompt should not appear" not in report


def test_analytics_report_endpoint_is_protected_and_returns_markdown(tmp_path):
    register = SourceRegister(tmp_path)
    client = TestClient(create_app(register, AuthService(PASSWORD)))

    assert client.get("/api/analytics/report.md").status_code == 401

    token = client.post("/api/auth/login", json={"password": PASSWORD}).json()["token"]
    response = client.get("/api/analytics/report.md", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "attachment" in response.headers["content-disposition"]
    assert "Analytics Evidence Report" in response.text
    assert "Validation Protocols" in response.text
