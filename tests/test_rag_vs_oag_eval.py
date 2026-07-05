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
