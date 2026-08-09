"""Capability traceability and validation protocol evidence tests."""

from pathlib import Path

from fastapi.testclient import TestClient

from assistant.api.app import create_app
from assistant.api.auth import AuthService
from assistant.evidence.validation import build_validation_evidence_report
from assistant.sources.register import SourceRegister

PASSWORD = "validation-test-pass"


def test_validation_evidence_report_contains_traceability_and_protocols():
    report = build_validation_evidence_report()

    assert report.summary["ksb_count"] >= 6
    assert report.summary["validation_protocol_count"] >= 11
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
    assert any(protocol.protocol_id == "VAL-ANL-FORECAST-001" for protocol in report.validation_protocols)
    assert any(protocol.protocol_id == "VAL-ANL-CLUSTER-001" for protocol in report.validation_protocols)
    assert any(protocol.protocol_id == "VAL-ANL-EXPORT-001" for protocol in report.validation_protocols)
    assert any(protocol.protocol_id == "VAL-ANL-VALUE-001" for protocol in report.validation_protocols)
    assert {note.category for note in report.ethics_notes} == {
        "Bias and analytical limitation",
        "GDPR and data protection",
        "Sustainability and compute footprint",
    }
    assert any("project-local evidence mappings" in caveat for caveat in report.caveats)
    assert not any("assessment" in caveat.lower() for caveat in report.caveats)


def test_validation_evidence_references_current_repository_files():
    report = build_validation_evidence_report()
    repository_root = Path(__file__).resolve().parents[1]
    references = [reference for row in report.ksb_rows for reference in row.evidence_refs]
    references.extend(reference for row in report.ksb_rows for event in row.evidence_history for reference in event.evidence_refs)
    references.extend(reference for protocol in report.validation_protocols for reference in protocol.current_evidence)
    references.extend(reference for note in report.ethics_notes for reference in note.evidence_refs)

    assert references
    assert all((repository_root / reference.path).is_file() for reference in references)
    assert not any("2026-07-06T19-47-56" in reference.path for reference in references)
    assert any(reference.path == "docs/benchmark/oag/rag-vs-oag-final-benchmark.md" for reference in references)
    assert not any("52-pack" in row.next_evidence for row in report.ksb_rows)


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
    forecast_protocol = next(protocol for protocol in body["validation_protocols"] if protocol["protocol_id"] == "VAL-ANL-FORECAST-001")
    export_protocol = next(protocol for protocol in body["validation_protocols"] if protocol["protocol_id"] == "VAL-ANL-EXPORT-001")
    assert "series_points" in forecast_protocol["current_metrics"]
    assert export_protocol["current_metrics"]["dataset_count"] >= 1
    assert len(body["ethics_notes"]) == 3
    assert body["ethics_notes"][0]["current_signal"]
    assert body["ksb_rows"][0]["evidence_refs"][0]["kind"] in {"test", "doc", "data", "code"}
    assert body["ksb_rows"][0]["official_references"][0]["mapping_status"] == "mapped_provisional"
    assert body["ksb_rows"][0]["evidence_history"][0]["event_date"]
    assert body["validation_protocols"][0]["acceptance_rule"]
