"""KSB traceability and validation protocol evidence tests."""

from fastapi.testclient import TestClient

from assistant.api.app import create_app
from assistant.api.auth import AuthService
from assistant.evidence.validation import build_validation_evidence_report
from assistant.sources.register import SourceRegister

PASSWORD = "validation-test-pass"


def test_validation_evidence_report_contains_traceability_and_protocols():
    report = build_validation_evidence_report()

    assert report.summary["ksb_count"] >= 6
    assert report.summary["validation_protocol_count"] >= 5
    assert report.summary["ksb_by_status"]["implemented"] >= 6
    assert report.summary["official_reference_count"] >= 6
    assert report.summary["evidence_history_event_count"] >= 12
    assert report.summary["evidence_reference_count"] >= 20
    assert any(row.ksb_id == "KSB-P3" and "AI/RAG/OAG" in row.capability for row in report.ksb_rows)
    assert all(row.official_references for row in report.ksb_rows)
    assert all(row.evidence_history for row in report.ksb_rows)
    assert any(row.ksb_id == "KSB-P3" and "RAG-vs-OAG comparative benchmark" in row.delivered_features for row in report.ksb_rows)
    assert any(protocol.protocol_id == "VAL-OAG-001" for protocol in report.validation_protocols)
    assert any(protocol.protocol_id == "VAL-REG-001" for protocol in report.validation_protocols)
    assert any("official assessment KSB IDs" in caveat for caveat in report.caveats)


def test_validation_evidence_endpoint_is_protected(tmp_path):
    register = SourceRegister(tmp_path)
    client = TestClient(create_app(register, AuthService(PASSWORD)))

    assert client.get("/api/analytics/validation-evidence").status_code == 401

    token = client.post("/api/auth/login", json={"password": PASSWORD}).json()["token"]
    response = client.get("/api/analytics/validation-evidence", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["ksb_count"] >= 6
    assert body["summary"]["official_reference_count"] >= 6
    assert body["summary"]["evidence_history_event_count"] >= 12
    assert any(protocol["protocol_id"] == "VAL-OAG-001" for protocol in body["validation_protocols"])
    assert body["ksb_rows"][0]["evidence_refs"][0]["kind"] in {"test", "doc", "data", "code"}
    assert body["ksb_rows"][0]["official_references"][0]["mapping_status"] == "mapped_provisional"
    assert body["ksb_rows"][0]["evidence_history"][0]["event_date"]
    assert body["validation_protocols"][0]["acceptance_rule"]
