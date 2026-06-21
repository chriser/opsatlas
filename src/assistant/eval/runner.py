"""Score the assistant's responses against the benchmark rubric.

Each response is classified deterministically into answered / refused / declined /
guardrail, then compared to the question's expected behaviour.
"""

from __future__ import annotations

# questions.json "expected" -> the response class we expect.
EXPECTED_MAP = {
    "answer": "answered",
    "refuse": "refused",
    "decline": "declined",
    "guardrail": "guardrail",
}


def classify_response(result) -> str:
    """Bucket an AnswerResult into one of the rubric classes."""
    if result.category:  # a guardrail fired (off-topic / unsafe)
        return "guardrail"
    if result.refused:  # genuine "not in the knowledge base"
        return "refused"
    if result.confidence == "grounded":  # answered, with cited evidence
        return "answered"
    return "declined"  # responded but not grounded (e.g. a scoped decline)


def run_eval(answer_service, questions: list[dict]) -> dict:
    rows = []
    for q in questions:
        result = answer_service.answer(q["question"])
        actual = classify_response(result)
        expected = EXPECTED_MAP.get(q.get("expected", "answer"), "answered")
        rows.append({
            "id": q.get("id"),
            "category": q.get("category"),
            "question": q["question"],
            "expected": expected,
            "actual": actual,
            "passed": actual == expected,
            "mode": result.mode,
            "answer": result.answer,
        })
    passed = sum(1 for r in rows if r["passed"])
    total = len(rows)
    return {
        "summary": {"total": total, "passed": passed, "accuracy": round(passed / total, 3) if total else 0.0},
        "rows": rows,
    }


def format_markdown(report: dict) -> str:
    s = report["summary"]
    lines = [
        f"# Evaluation — {s['passed']}/{s['total']} passed ({s['accuracy']:.0%})",
        "",
        "| # | Expected | Actual | Pass | Question |",
        "|---|---|---|:--:|---|",
    ]
    for r in report["rows"]:
        mark = "PASS" if r["passed"] else "FAIL"
        lines.append(f"| {r['id']} | {r['expected']} | {r['actual']} | {mark} | {r['question'][:60]} |")
    return "\n".join(lines)
