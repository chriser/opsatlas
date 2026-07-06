"""Hermetic tests for the RAG-vs-OAG benchmark harness."""

from __future__ import annotations

from assistant.answer.prompt import REFUSAL
from assistant.answer.service import AnswerResult
from assistant.eval.rag_vs_oag import (
    ExpectedFact,
    RagVsOagDataset,
    RagVsOagQuestion,
    evaluate_rag_vs_oag,
    format_rag_vs_oag_markdown,
    rescore_rag_vs_oag_report,
    score_rag_vs_oag_answer,
    write_rag_vs_oag_scorecard,
)


def _label(
    question_id: str,
    category: str,
    question: str,
    facts: list[ExpectedFact],
    *,
    expected_path: str = "oag",
) -> RagVsOagQuestion:
    return RagVsOagQuestion(
        id=question_id,
        category=category,
        question=question,
        expected_path=expected_path,
        expected_answer_facts=facts,
        notes="test label",
    )


def test_score_hits_aliases_and_misses_unmentioned_facts() -> None:
    label = _label(
        "structured-001",
        "structured_entity",
        "Who owns setup?",
        [
            ExpectedFact(text="finance owner owns setup", aliases=["finance approver owns supplier setup"]),
            ExpectedFact(text="credit checks are mandatory gates"),
        ],
    )
    result = AnswerResult(
        answer="The finance approver owns supplier setup.",
        citations=[],
        mode="test",
        refused=False,
        answer_path="oag",
    )

    score = score_rag_vs_oag_answer(label, result)

    assert score["facts_hit"] == ["finance owner owns setup"]
    assert score["facts_missed"] == ["credit checks are mandatory gates"]
    assert score["passed"] is False
    assert score["expected_path_hit"] is True


def test_score_accepts_content_token_match_for_rephrased_fact() -> None:
    label = _label(
        "structured-001",
        "structured_entity",
        "Who creates supplier records?",
        [
            ExpectedFact(
                text="trading support assistant or master data operator creates the supplier record",
            )
        ],
    )
    result = AnswerResult(
        answer=(
            "The task of creating supplier records in the operational master data tool "
            "is performed by the Trading support assistant / master data operator [1]."
        ),
        citations=[],
        mode="test",
        refused=False,
        answer_path="oag",
    )

    score = score_rag_vs_oag_answer(label, result)

    assert score["passed"] is True
    assert score["fact_details"][0]["match_method"] == "content_tokens"
    assert score["fact_details"][0]["token_coverage"] >= 0.72


def test_out_of_scope_refusal_passes_without_exact_fact_wording() -> None:
    label = _label(
        "out-001",
        "out_of_scope",
        "What is the VAT number?",
        [ExpectedFact(text="refuse because no real VAT number is available")],
        expected_path="either",
    )
    result = AnswerResult(answer=REFUSAL, citations=[], mode="test", refused=True, answer_path="rag")

    score = score_rag_vs_oag_answer(label, result)

    assert score["passed"] is True
    assert score["expected_path_hit"] is True


def test_fake_generator_report_covers_configs_paths_and_stability(tmp_path) -> None:
    dataset = RagVsOagDataset(
        dataset_version="rag-vs-oag-test",
        created_at="2026-07-05",
        source_corpus="test",
        questions=[
            _label(
                "rel-001",
                "structured_relationship",
                "Which controls must pass?",
                [ExpectedFact(text="credit checks are mandatory gates")],
            ),
            _label(
                "narrative-001",
                "narrative",
                "Why do checks matter?",
                [ExpectedFact(text="credit checks are mandatory gates")],
                expected_path="rag",
            ),
            _label(
                "mixed-001",
                "mixed",
                "Who owns setup and why?",
                [
                    ExpectedFact(text="finance owner owns setup"),
                    ExpectedFact(text="credit checks are mandatory gates"),
                ],
                expected_path="either",
            ),
        ],
    )

    report = evaluate_rag_vs_oag(dataset, runs=2, fake_generator=True)
    paths = write_rag_vs_oag_scorecard(report, tmp_path)
    markdown = format_rag_vs_oag_markdown(report)

    assert report["by_config"]["oag_first"]["passed"] == 6
    assert report["by_config"]["oag_only"]["passed"] == 2
    assert report["summary"]["split_counts"] == {"tuning": 3}
    assert "code_state" in report["summary"]
    assert {"available", "commit", "branch", "dirty"}.issubset(report["summary"]["code_state"])
    assert report["by_split"]["oag_first"]["tuning"]["passed"] == 6
    assert report["path_usage"]["oag_first"]["rag+ontology"] == 2
    assert report["stability"]["oag_first"]["unstable_count"] == 0
    assert "Accuracy By Split" in markdown
    assert "Verdict status: diagnostic only" in markdown
    assert "Metric leader: oag_first" in markdown
    assert "Code state:" in markdown
    assert "RAG vs OAG Benchmark" in markdown
    assert paths["json"].endswith(".json")
    assert paths["markdown"].endswith(".md")


def test_evaluate_can_filter_to_holdout_split() -> None:
    dataset = RagVsOagDataset(
        dataset_version="rag-vs-oag-test",
        created_at="2026-07-06",
        source_corpus="test",
        questions=[
            _label("tuning-001", "structured_entity", "Who owns tuning?", [ExpectedFact(text="tuning owner owns setup")]),
            RagVsOagQuestion(
                id="holdout-001",
                split="holdout",
                category="structured_entity",
                question="Who owns holdout?",
                expected_path="oag",
                expected_answer_facts=[ExpectedFact(text="holdout owner owns setup")],
                notes="holdout label",
            ),
        ],
    )

    report = evaluate_rag_vs_oag(dataset, runs=1, fake_generator=True, split="holdout")

    assert report["summary"]["question_count"] == 2
    assert report["summary"]["evaluated_question_count"] == 1
    assert report["summary"]["split_filter"] == "holdout"
    assert {row["id"] for row in report["rows"]} == {"holdout-001"}
    assert set(report["by_split"]["oag_first"]) == {"holdout"}


def test_evaluate_can_filter_to_category_and_ids() -> None:
    dataset = RagVsOagDataset(
        dataset_version="rag-vs-oag-test",
        created_at="2026-07-06",
        source_corpus="test",
        questions=[
            _label(
                "aggregate-001",
                "aggregate",
                "List readiness elements.",
                [ExpectedFact(text="mapping controls")],
            ),
            _label(
                "aggregate-002",
                "aggregate",
                "List publication areas.",
                [ExpectedFact(text="point-of-sale systems")],
            ),
            _label(
                "narrative-001",
                "narrative",
                "Why do checks matter?",
                [ExpectedFact(text="credit checks are mandatory gates")],
                expected_path="rag",
            ),
        ],
    )

    report = evaluate_rag_vs_oag(
        dataset,
        runs=1,
        fake_generator=True,
        categories={"aggregate"},
        ids={"aggregate-002"},
    )
    markdown = format_rag_vs_oag_markdown(report)

    assert report["summary"]["evaluated_question_count"] == 1
    assert report["summary"]["category_filter"] == ["aggregate"]
    assert report["summary"]["id_filter"] == ["aggregate-002"]
    assert {row["id"] for row in report["rows"]} == {"aggregate-002"}
    assert "Category filter: aggregate" in markdown
    assert "ID filter: aggregate-002" in markdown


def test_full_three_run_unfiltered_report_is_decision_grade() -> None:
    dataset = RagVsOagDataset(
        dataset_version="rag-vs-oag-test",
        created_at="2026-07-06",
        source_corpus="test",
        questions=[
            _label(
                "rel-001",
                "structured_relationship",
                "Which controls must pass?",
                [ExpectedFact(text="credit checks are mandatory gates")],
            )
        ],
    )

    report = evaluate_rag_vs_oag(dataset, runs=3, fake_generator=True)
    markdown = format_rag_vs_oag_markdown(report)

    assert report["summary"]["diagnostic_run"] is False
    assert report["summary"]["winner_config"] == "oag_first"
    assert "DIAGNOSTIC RUN" not in markdown
    assert "Verdict status: decision-grade" in markdown


def test_rescore_existing_report_uses_current_scoring() -> None:
    dataset = RagVsOagDataset(
        dataset_version="rag-vs-oag-test",
        created_at="2026-07-05",
        source_corpus="test",
        questions=[
            _label(
                "structured-001",
                "structured_entity",
                "Who creates supplier records?",
                [
                    ExpectedFact(
                        text="trading support assistant or master data operator creates the supplier record",
                    )
                ],
            )
        ],
    )
    report = {
        "summary": {
            "generated_at": "2026-07-05T16:52:10+00:00",
            "dataset_version": "rag-vs-oag-test",
            "source_corpus": "test",
            "question_count": 1,
            "runs": 1,
            "configs": ["oag_first"],
            "fake_generator": False,
            "model_info": {"backend": "test", "llm": "test", "embed": "test"},
            "best_config": "oag_first",
        },
        "latency": {"total_seconds": 1.0},
        "rows": [
            {
                "run": 1,
                "config": "oag_first",
                "id": "structured-001",
                "category": "structured_entity",
                "question": "Who creates supplier records?",
                "expected_path": "oag",
                "answer_path": "oag",
                "mode": "test",
                "refused": False,
                "confidence": "grounded",
                "grounding": "n/a",
                "facts_hit": [],
                "facts_missed": ["trading support assistant or master data operator creates the supplier record"],
                "fact_details": [],
                "passed": False,
                "expected_path_hit": True,
                "citation_types": ["ontology_object"],
                "citation_count": 1,
                "latency_seconds": 0.5,
                "answer": (
                    "The task of creating supplier records is performed by the "
                    "Trading support assistant / master data operator [1]."
                ),
            }
        ],
    }

    rescored = rescore_rag_vs_oag_report(report, dataset)

    assert rescored["summary"]["rescored_from"] == "2026-07-05T16:52:10+00:00"
    assert rescored["by_config"]["oag_first"]["passed"] == 1
    assert rescored["rows"][0]["passed"] is True
