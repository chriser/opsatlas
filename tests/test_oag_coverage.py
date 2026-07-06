"""Hermetic tests for OAG ontology coverage diagnostics."""

from __future__ import annotations

from assistant.eval.oag_coverage import build_oag_coverage_report, format_oag_coverage_markdown
from assistant.eval.rag_vs_oag import ExpectedFact, RagVsOagDataset, RagVsOagQuestion
from assistant.ontology.query import OntologyQueryService
from assistant.ontology.store import OntologyStore


def test_oag_coverage_reports_present_and_partial_facts(tmp_path) -> None:
    store = OntologyStore(tmp_path / "ontology.db")
    process = store.upsert_object(
        "process",
        "supplier-setup",
        {
            "name": "Supplier Setup",
            "domain": "supplier",
            "capabilities": ["controlled onboarding"],
            "business_rules": [
                "Mapping controls must be complete before downstream use.",
                "Article attributes need a clear purpose and owner.",
            ],
        },
    )
    role = store.upsert_object(
        "role",
        "data governance owner",
        {"name": "Data governance owner"},
    )
    store.link("process_has_role", process.id, role.id)
    query = OntologyQueryService(store)
    dataset = RagVsOagDataset(
        dataset_version="test",
        created_at="2026-07-06",
        source_corpus="test",
        questions=[
            RagVsOagQuestion(
                id="aggregate-001",
                split="holdout",
                category="aggregate",
                question="List readiness elements.",
                expected_path="oag",
                expected_answer_facts=[
                    ExpectedFact(text="mapping controls"),
                    ExpectedFact(text="data governance owner approves purposeful article attributes"),
                ],
                notes="coverage test",
            )
        ],
    )
    benchmark_report = {
        "summary": {"generated_at": "2026-07-06T16:29:44+00:00", "dataset_version": "test"},
        "rows": [
            {
                "id": "aggregate-001",
                "config": "oag_first",
                "split": "holdout",
                "category": "aggregate",
                "answer_path": "rag+ontology",
                "passed": False,
                "facts_missed": [
                    "mapping controls",
                    "data governance owner approves purposeful article attributes",
                ],
            }
        ],
    }

    report = build_oag_coverage_report(benchmark_report, dataset, query)
    markdown = format_oag_coverage_markdown(report)
    rows = {row["expected_fact"]: row for row in report["rows"]}

    assert rows["mapping controls"]["coverage_status"] == "present"
    assert rows["data governance owner approves purposeful article attributes"]["coverage_status"] == "partial"
    assert report["summary"]["coverage_counts"] == {"partial": 1, "present": 1}
    assert "OAG Ontology Coverage Diagnostic" in markdown
    assert "mapping controls" in markdown
