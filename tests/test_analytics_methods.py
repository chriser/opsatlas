"""Analytics methods and models catalogue tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from assistant.analytics.knowledge_gaps import build_gap_clusters
from assistant.analytics.log import UsageEntry
from assistant.analytics.methods import (
    KNOWLEDGE_GAP_CANDIDATE_RULE,
    KNOWLEDGE_GAP_QUALITY_RULE,
    PROCESS_COMPLEXITY_BOUNDARY,
    build_methods_catalogue,
)
from assistant.analytics.process_complexity import build_process_complexity
from assistant.api.app import create_app
from assistant.api.auth import AuthService
from assistant.sources.register import SourceRegister

PASSWORD = "methods-test-pass"

SURFACED_ANALYTICS = {
    "coverage_score",
    "knowledge_gap_clustering",
    "value_dcf",
    "process_complexity_index",
    "key_person_risk_index",
    "forecasting",
    "recurring_questions",
    "failed_retrieval",
}


def test_methods_catalogue_covers_surfaced_analytics() -> None:
    catalogue = build_methods_catalogue()
    methods = {method.id: method for method in catalogue.methods}

    assert SURFACED_ANALYTICS <= set(methods)
    assert catalogue.summary["method_count"] == len(catalogue.methods)
    assert catalogue.summary["implemented_count"] >= 5
    assert catalogue.summary["planned_count"] >= 3

    for method_id in SURFACED_ANALYTICS:
        method = methods[method_id]
        assert method.formula
        assert method.technique
        assert method.model_family
        assert method.inputs
        assert method.assumptions
        assert method.boundaries
        assert method.validation_metric
        assert method.references


def test_methods_endpoint_is_auth_protected(tmp_path) -> None:
    client = TestClient(create_app(SourceRegister(tmp_path), AuthService(PASSWORD)))

    assert client.get("/api/analytics/methods").status_code == 401

    token = client.post("/api/auth/login", json={"password": PASSWORD}).json()["token"]
    response = client.get("/api/analytics/methods", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["method_count"] >= len(SURFACED_ANALYTICS)
    assert any(method["id"] == "value_dcf" for method in body["methods"])


def test_existing_rubrics_use_methods_catalogue_constants() -> None:
    gaps = build_gap_clusters(
        [
            UsageEntry(
                timestamp="2026-07-06T10:00:00+00:00",
                question="Who owns article list governance?",
                mode="ask",
                refused=True,
                confidence="none",
            )
        ]
    )
    complexity = build_process_complexity([])

    assert gaps["rubric"]["candidate_rule"] == KNOWLEDGE_GAP_CANDIDATE_RULE
    assert gaps["rubric"]["quality_rule"] == KNOWLEDGE_GAP_QUALITY_RULE
    assert complexity["rubric"]["evidence_boundary"] == PROCESS_COMPLEXITY_BOUNDARY
