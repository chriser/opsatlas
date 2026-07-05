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
    assert report["path_usage"]["oag_first"]["rag+ontology"] == 2
    assert report["stability"]["oag_first"]["unstable_count"] == 0
    assert "RAG vs OAG Benchmark" in markdown
    assert paths["json"].endswith(".json")
    assert paths["markdown"].endswith(".md")


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
