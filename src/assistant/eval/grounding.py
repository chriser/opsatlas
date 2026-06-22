"""Groundedness evaluation helpers for hallucination probes."""

from __future__ import annotations

from .runner import EXPECTED_MAP, classify_response


def evaluate_grounding(answer_service, probes: list[dict]) -> dict:
    rows = []
    for probe in probes:
        result = answer_service.answer(probe["question"])
        actual = classify_response(result)
        expected = EXPECTED_MAP.get(probe.get("expected", "answer"), "answered")
        grounding_score = float(getattr(result, "grounding_score", 0.0) or 0.0)
        grounding_ok = expected != "answered" or grounding_score >= 0.5
        passed = actual == expected and grounding_ok
        rows.append(
            {
                "id": probe["id"],
                "category": probe["category"],
                "question": probe["question"],
                "expected": expected,
                "actual": actual,
                "passed": passed,
                "grounding": getattr(result, "grounding", "n/a"),
                "grounding_score": grounding_score,
                "faithfulness": getattr(result, "faithfulness", "n/a"),
                "hallucination_risk": probe.get("hallucination_risk", ""),
            }
        )
    passed = sum(1 for row in rows if row["passed"])
    answered = [row for row in rows if row["actual"] == "answered"]
    return {
        "summary": {
            "total": len(rows),
            "passed": passed,
            "accuracy": round(passed / len(rows), 3) if rows else 0.0,
            "average_grounding_score": round(sum(row["grounding_score"] for row in answered) / len(answered), 3) if answered else 0.0,
        },
        "rows": rows,
    }


def format_grounding_markdown(report: dict) -> str:
    summary = report["summary"]
    lines = [
        f"# Groundedness Evaluation — {summary['passed']}/{summary['total']} passed ({summary['accuracy']:.0%})",
        "",
        f"Average grounding score for answered probes: {summary['average_grounding_score']:.0%}",
        "",
        "| ID | Expected | Actual | Grounding | Score | Pass | Risk |",
        "|---|---|---|---|---:|:--:|---|",
    ]
    for row in report["rows"]:
        mark = "PASS" if row["passed"] else "FAIL"
        risk = row["hallucination_risk"].replace("|", "/")[:80]
        lines.append(
            f"| {row['id']} | {row['expected']} | {row['actual']} | {row['grounding']} | "
            f"{row['grounding_score']:.0%} | {mark} | {risk} |"
        )
    return "\n".join(lines)
