"""Tests for the evaluation scoring (hermetic)."""

from assistant.answer.service import AnswerResult
from assistant.eval.runner import classify_response, format_markdown, run_eval


def _result(refused=False, category=None, confidence="none") -> AnswerResult:
    return AnswerResult(answer="x", citations=[], mode="full-context", refused=refused, category=category, confidence=confidence)


def test_classify_response_buckets():
    assert classify_response(_result(confidence="grounded")) == "answered"
    assert classify_response(_result(refused=True)) == "refused"
    assert classify_response(_result(refused=True, category="off_topic")) == "guardrail"
    assert classify_response(_result(refused=False, confidence="unverified")) == "declined"


class FakeAnswerService:
    """Maps a question to a canned result by its expected behaviour keyword."""

    def answer(self, question, top_k=5):
        if "VAT" in question:
            return _result(refused=True)
        if "weather" in question:
            return _result(refused=True, category="off_topic")
        return _result(confidence="grounded")


def test_run_eval_scores_against_rubric():
    questions = [
        {"id": 1, "question": "Who starts setup?", "expected": "answer"},
        {"id": 2, "question": "What is the VAT number?", "expected": "refuse"},
        {"id": 3, "question": "What's the weather?", "expected": "guardrail"},
        {"id": 4, "question": "Who starts setup?", "expected": "refuse"},  # should FAIL (answered)
    ]
    report = run_eval(FakeAnswerService(), questions)
    assert report["summary"]["total"] == 4
    assert report["summary"]["passed"] == 3
    assert report["rows"][3]["passed"] is False
    assert "passed" in format_markdown(report).lower() or "Evaluation" in format_markdown(report)
