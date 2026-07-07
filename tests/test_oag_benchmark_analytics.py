"""Analytics aggregation tests for committed RAG-vs-OAG scorecards."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from assistant.analytics.oag_benchmark import build_oag_benchmark_report
from assistant.api.app import create_app
from assistant.api.auth import AuthService
from assistant.sources.register import SourceRegister

PASSWORD = "oag-benchmark-test-pass"


def _write_scorecard(path: Path, *, generated_at: str, runs: int, diagnostic: bool, split_filter: str = "holdout") -> None:
    report = {
        "summary": {
            "generated_at": generated_at,
            "dataset_version": "rag-vs-oag-test",
            "source_corpus": "test corpus",
            "question_count": 4,
            "evaluated_question_count": 2,
            "split_filter": split_filter,
            "category_filter": [],
            "id_filter": [],
            "split_counts": {"holdout": 2, "tuning": 2},
            "runs": runs,
            "configs": ["rag_only", "oag_first"],
            "fake_generator": False,
            "model_info": {"backend": "scripted", "llm": "fixture", "embed": "none"},
            "best_config": "oag_first",
            "winner_config": "" if diagnostic else "oag_first",
            "diagnostic_run": diagnostic,
            "diagnostic_reasons": ["split filter is holdout"] if diagnostic else [],
            "code_state": {"available": True, "short_commit": "abc123"},
        },
        "latency": {"total_seconds": 9.0, "mean_seconds": 1.5, "p95_seconds": 2.0},
        "by_config": {
            "rag_only": {"total": 2, "passed": 1, "accuracy": 0.5, "path_accuracy": 1.0},
            "oag_first": {"total": 2, "passed": 2, "accuracy": 1.0, "path_accuracy": 1.0},
        },
        "by_split": {
            "rag_only": {"holdout": {"total": 2, "passed": 1, "accuracy": 0.5}},
            "oag_first": {"holdout": {"total": 2, "passed": 2, "accuracy": 1.0}},
        },
        "by_split_category": {},
        "by_category": {
            "rag_only": {"structured_relationship": {"total": 2, "passed": 1, "accuracy": 0.5}},
            "oag_first": {"structured_relationship": {"total": 2, "passed": 2, "accuracy": 1.0}},
        },
        "path_usage": {"rag_only": {"rag": 2}, "oag_first": {"oag": 2}},
        "citation_type_usage": {"rag_only": {"document": 2}, "oag_first": {"ontology_object": 2}},
        "stability": {"rag_only": {"unstable_count": 0}, "oag_first": {"unstable_count": 0}},
        "interpretation_targets": {"structured_relationship_lift": 0.5},
        "rows": [
            {
                "run": 1,
                "config": "oag_first",
                "id": "holdout-001",
                "split": "holdout",
                "category": "structured_relationship",
                "question": "Who owns the control?",
                "expected_path": "oag",
                "answer_path": "oag",
                "mode": "oag",
                "refused": False,
                "confidence": "grounded",
                "grounding": "n/a",
                "facts_hit": ["control owner"],
                "facts_missed": [],
                "passed": True,
                "expected_path_hit": True,
                "citation_types": ["ontology_object"],
                "citation_count": 1,
                "latency_seconds": 1.2,
                "answer": "control owner [1]",
            }
        ],
    }
    path.write_text(json.dumps(report), encoding="utf-8")


def test_oag_benchmark_report_reads_latest_scorecard_and_marks_decision_grade(tmp_path: Path) -> None:
    _write_scorecard(
        tmp_path / "rag-vs-oag-rag_only-oag_first-2026-07-06T19-47-56+00-00.json",
        generated_at="2026-07-06T19:47:56+00:00",
        runs=3,
        diagnostic=True,
    )
    _write_scorecard(
        tmp_path / "rag-vs-oag-rag_only-oag_first-2026-07-06T18-00-00+00-00.json",
        generated_at="2026-07-06T18:00:00+00:00",
        runs=1,
        diagnostic=True,
    )

    report = build_oag_benchmark_report(tmp_path)

    assert report["scorecard_count"] == 2
    assert report["latest"]["generated_at"] == "2026-07-06T19:47:56+00:00"
    assert report["latest"]["diagnostic_run"] is True
    assert report["latest"]["evidence_grade"] == "holdout_decision"
    assert report["latest"]["decision_grade"] is True
    assert report["latest"]["category_lift"] == [
        {
            "category": "structured_relationship",
            "rag_only_accuracy": 0.5,
            "oag_first_accuracy": 1.0,
            "lift": 0.5,
            "rag_only_total": 2,
            "oag_first_total": 2,
        }
    ]
    assert report["latest"]["path_usage"]["oag_first"]["total"] == 2
    assert report["latest"]["citation_type_usage"]["oag_first"]["counts"]["ontology_object"] == 2
    assert report["latest"]["rows"][0]["facts_hit"] == ["control owner"]
    assert report["history"][1]["evidence_grade"] == "diagnostic"


def test_oag_benchmark_endpoint_is_protected(tmp_path: Path) -> None:
    register = SourceRegister(tmp_path)
    client = TestClient(create_app(register, AuthService(PASSWORD)))

    assert client.get("/api/analytics/oag-benchmark").status_code == 401

    token = client.post("/api/auth/login", json={"password": PASSWORD}).json()["token"]
    response = client.get("/api/analytics/oag-benchmark", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert {"scorecard_count", "latest", "history", "boundary"}.issubset(body)
