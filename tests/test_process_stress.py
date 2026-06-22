"""Process stress-test simulation tests."""

from fastapi.testclient import TestClient

from assistant.api.app import create_app
from assistant.api.auth import AuthService
from assistant.process.models import ProcessRecord, ProcessRule
from assistant.process.stress import build_process_stress_report
from assistant.sources.register import SourceRegister

PASSWORD = "stress-test-pass"


def _record() -> ProcessRecord:
    return ProcessRecord(
        id="proc-1",
        source_id="src-1",
        source_title="Supplier setup pack",
        name="Supplier setup",
        roles=["requester", "support_team", "finance_owner", "approver"],
        systems=["request portal", "document repository", "finance system"],
        controls=["credit check", "approval gate"],
        dependencies=["finance-validation", "supplier-data"],
        business_rules=[
            "Requests fail closed until validation is complete.",
            "Manual exceptions require approval and evidence retention.",
        ],
        rules=[
            ProcessRule(topic="intake", role="requester", rule="requester opens supplier setup request", confidence="high"),
            ProcessRule(topic="validation", role="support_team", rule="support validates mandatory evidence", confidence="high"),
            ProcessRule(topic="approval", role="finance_owner", rule="finance owner checks payment mapping", confidence="medium"),
            ProcessRule(topic="exception", role="support_team", rule="manual exception requires approval", confidence="medium"),
        ],
    )


def test_process_stress_report_extracts_rules_and_scenarios():
    report = build_process_stress_report([_record()])

    assert report.process_count == 1
    assert report.scenario_count == 4
    assert report.rules[0].handoff_count == 3
    assert report.rules[0].system_count == 3
    assert report.rules[0].exception_term_count >= 2
    assert "Multiple role hand-offs" in report.rules[0].stress_factors
    assert report.highest_risk is not None
    assert report.highest_risk.queue_pressure_score >= 70
    assert report.highest_risk.optimisation_actions
    assert report.rubric["boundary"].startswith("Scenario-planning")


def test_process_stress_endpoint_is_protected_and_empty_safe(tmp_path):
    register = SourceRegister(tmp_path)
    client = TestClient(create_app(register, AuthService(PASSWORD)))

    assert client.get("/api/process/stress-test").status_code == 401

    token = client.post("/api/auth/login", json={"password": PASSWORD}).json()["token"]
    response = client.get("/api/process/stress-test", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["process_count"] == 0
    assert body["scenario_count"] == 4
    assert body["highest_risk"] is None
