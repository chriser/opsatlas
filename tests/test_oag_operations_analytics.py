"""Live OAG operations analytics tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from assistant.analytics.log import UsageEntry
from assistant.analytics.oag_operations import build_oag_operations_report
from assistant.api.app import create_app
from assistant.api.auth import AuthService
from assistant.sources.register import SourceRegister

PASSWORD = "oag-operations-test-pass"


def _entry(
    timestamp: str,
    question: str,
    answer_path: str,
    *,
    refused: bool = False,
    confidence: str = "grounded",
    citation_type_counts: dict[str, int] | None = None,
    deterministic_ratio: float = 0.0,
    generative_ratio: float = 1.0,
) -> UsageEntry:
    counts = citation_type_counts or {"document": 1}
    return UsageEntry(
        timestamp=timestamp,
        question=question,
        mode="ask",
        answer_path=answer_path,
        citation_type_counts=counts,
        deterministic_evidence_ratio=deterministic_ratio,
        generative_evidence_ratio=generative_ratio,
        deterministic_evidence_flag=deterministic_ratio >= 0.5,
        refused=refused,
        confidence=confidence,
        citation_count=sum(counts.values()) if "none" not in counts else 0,
    )


def test_oag_operations_report_summarises_path_evidence_and_coverage_gaps() -> None:
    entries = [
        _entry(
            "2026-07-06T09:00:00+00:00",
            "Who owns supplier setup?",
            "oag",
            citation_type_counts={"ontology_object": 1},
            deterministic_ratio=1.0,
            generative_ratio=0.0,
        ),
        _entry(
            "2026-07-06T09:05:00+00:00",
            "Why does finance mapping matter?",
            "rag+ontology",
            citation_type_counts={"document": 1, "ontology_object": 1},
            deterministic_ratio=0.5,
            generative_ratio=0.5,
        ),
        _entry("2026-07-07T09:00:00+00:00", "What are supplier-side ordering days?", "rag"),
        _entry(
            "2026-07-07T10:00:00+00:00",
            "What is the VAT number?",
            "rag",
            refused=True,
            confidence="none",
            citation_type_counts={"none": 1},
            deterministic_ratio=0.0,
            generative_ratio=0.0,
        ),
    ]
    traces = [
        {"answer_path": "oag", "latency_ms": 120},
        {"answer_path": "rag+ontology", "latency_ms": 240},
        {"answer_path": "rag", "latency_ms": 180},
    ]

    report = build_oag_operations_report(entries, traces)

    assert report["summary"]["total_queries"] == 4
    assert report["summary"]["oag_assisted_count"] == 2
    assert report["summary"]["rag_fallback_count"] == 2
    assert report["summary"]["deterministic_evidence_ratio"] == 0.5
    assert report["summary"]["ontology_object_citation_rate"] == 0.667
    assert report["daily_path_split"][0]["oag"] == 1
    assert report["oag_adoption_forecast"]["series_id"] == "oag_adoption"
    assert report["oag_adoption_forecast"]["actuals"][0] == {"date": "2026-07-06", "value": 2}
    assert len(report["oag_adoption_forecast"]["forecast"]) == 7
    assert report["path_grounding_matrix"][0]["answer_path"] in {"oag", "rag", "rag+ontology"}
    assert {row["answer_path"] for row in report["latency_by_path"]} == {"oag", "rag", "rag+ontology"}
    assert report["coverage_gaps"][0]["question"] == "What are supplier-side ordering days?"
    assert report["coverage_gaps"][0]["trigger_ref"].startswith("oag-coverage:")
    assert report["coverage_gaps"][0]["eam_gap_ref"].startswith("eam-gap:")


def test_oag_operations_endpoint_is_protected_and_backfill_safe(tmp_path) -> None:
    register = SourceRegister(tmp_path)
    client = TestClient(create_app(register, AuthService(PASSWORD)))

    assert client.get("/api/analytics/oag-operations").status_code == 401

    token = client.post("/api/auth/login", json={"password": PASSWORD}).json()["token"]
    client.app.state.answer.usage_log.append(
        UsageEntry(
            timestamp="2026-07-07T09:00:00+00:00",
            question="Legacy row without enriched telemetry",
            mode="ask",
            answer_path="rag",
            refused=False,
            confidence="grounded",
            citation_count=1,
        )
    )
    response = client.get("/api/analytics/oag-operations", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["total_queries"] == 1
    assert body["oag_adoption_forecast"]["actuals"] == [{"date": "2026-07-07", "value": 0}]
    assert body["coverage_gaps"]
