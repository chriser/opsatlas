"""Knowledge-gap clustering analytics tests."""

from fastapi.testclient import TestClient

from assistant.analytics.knowledge_gaps import build_gap_clusters
from assistant.analytics.log import UsageEntry, UsageLog
from assistant.api.app import create_app
from assistant.api.auth import AuthService
from assistant.sources.register import SourceRegister

PASSWORD = "test-pass"


def _entry(question: str, refused: bool = True, category: str | None = None, confidence: str = "none") -> UsageEntry:
    return UsageEntry(
        timestamp="2026-06-22T10:00:00Z",
        question=question,
        mode="retrieval",
        refused=refused,
        category=category,
        confidence=confidence,
        citation_count=0,
    )


def test_gap_clusters_group_refused_and_weak_confidence_questions():
    entries = [
        _entry("Are credit checks mandatory?"),
        _entry("What happens if credit approval fails?"),
        _entry("Why is finance mapping required?"),
        _entry("Which supplier identifier is used for invoices?"),
        _entry("Tell me a joke", refused=True, category="off_topic"),
        _entry("Who owns the handover?", refused=False, confidence="none"),
    ]

    out = build_gap_clusters(entries)

    assert out["total_candidates"] == 5
    assert out["cluster_count"] == 3
    labels = {cluster["label"] for cluster in out["clusters"]}
    assert "Control and approval gaps" in labels
    assert "Finance mapping gaps" in labels
    assert all(cluster["representative_questions"] for cluster in out["clusters"])
    assert out["silhouette_score"] > 0
    assert "manual review" in out["rubric"]["quality_rule"]


def test_gap_clusters_empty_is_safe():
    out = build_gap_clusters([])

    assert out["total_candidates"] == 0
    assert out["cluster_count"] == 0
    assert out["silhouette_score"] == 0
    assert out["clusters"] == []


def test_knowledge_gap_endpoint_uses_usage_log_without_guardrail_prompts(tmp_path):
    register = SourceRegister(tmp_path)
    usage = UsageLog(register.base_dir)
    usage.append(_entry("What happens when credit approval fails?"))
    usage.append(_entry("Tell me a joke", refused=True, category="off_topic"))
    client = TestClient(create_app(register, AuthService(PASSWORD)))
    token = client.post("/api/auth/login", json={"password": PASSWORD}).json()["token"]
    client.headers.update({"Authorization": f"Bearer {token}"})

    out = client.get("/api/analytics/knowledge-gaps").json()

    assert out["total_candidates"] == 1
    assert out["clusters"][0]["topic"] == "checks"
    assert "Tell me a joke" not in str(out)
