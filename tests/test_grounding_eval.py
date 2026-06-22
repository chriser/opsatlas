"""Tests for hallucination-probe groundedness evaluation."""

from __future__ import annotations

from assistant.answer.service import AnswerResult
from assistant.eval.grounding import evaluate_grounding, format_grounding_markdown


class FakeAnswerService:
    def answer(self, question):
        if "VAT" in question:
            return AnswerResult(answer="No evidence.", citations=[], mode="retrieval", refused=True)
        if "approve" in question:
            return AnswerResult(answer="I cannot approve operational changes.", citations=[], mode="full-context", refused=False)
        return AnswerResult(
            answer="Credit checks are mandatory [1].",
            citations=[],
            mode="full-context",
            refused=False,
            confidence="grounded",
            grounding="supported",
            grounding_score=1.0,
            faithfulness="faithful",
        )


def test_grounding_eval_scores_behaviour_and_grounding():
    probes = [
        {"id": "HAL-001", "category": "missing_specific", "question": "What is the VAT number?", "expected": "refuse"},
        {"id": "HAL-005", "category": "action_request", "question": "Can you approve this?", "expected": "decline"},
        {"id": "HAL-007", "category": "contradictory_premise", "question": "Credit checks are optional?", "expected": "answer"},
    ]

    report = evaluate_grounding(FakeAnswerService(), probes)

    assert report["summary"] == {"total": 3, "passed": 3, "accuracy": 1.0, "average_grounding_score": 1.0}
    assert report["rows"][2]["grounding_score"] == 1.0
    assert "Groundedness Evaluation" in format_grounding_markdown(report)


def test_answered_probe_without_grounding_score_fails_grounding_gate():
    class WeakAnswerService:
        def answer(self, question):
            return AnswerResult(answer="Maybe.", citations=[], mode="full-context", refused=False, confidence="unverified")

    report = evaluate_grounding(
        WeakAnswerService(),
        [{"id": "HAL-007", "category": "contradictory_premise", "question": "Credit checks are optional?", "expected": "answer"}],
    )

    assert report["summary"]["passed"] == 0
    assert report["rows"][0]["actual"] == "declined"
