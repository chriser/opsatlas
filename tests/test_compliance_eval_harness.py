"""Tests for the compliance reasoning evaluation harness."""

from __future__ import annotations

from assistant.eval.compliance_reasoning import (
    evaluate_compliance_reasoning,
    format_compliance_markdown,
    write_compliance_scorecard,
)


def test_compliance_eval_harness_scores_scripted_generator(tmp_path) -> None:
    labels = [
        {
            "id": "eval-supported-vat-retention",
            "domain": "vat",
            "external_source": "VAT guide Notice 700",
            "external_excerpt": "Finance teams must keep VAT invoice records for audit.",
            "internal_source": "VAT controls pack",
            "internal_excerpt": "Finance teams must keep VAT invoice records for audit.",
            "expected_classification": "supported",
            "rationale": "Both passages require invoice retention.",
        },
        {
            "id": "eval-contradiction-vat-retention",
            "domain": "vat",
            "external_source": "VAT guide Notice 700",
            "external_excerpt": "Finance teams must keep VAT invoice records for audit.",
            "internal_source": "VAT controls pack",
            "internal_excerpt": "Finance teams may delete VAT invoice records after matching payment.",
            "expected_classification": "contradiction",
            "rationale": "The internal passage permits deleting required evidence.",
        },
    ]

    report = evaluate_compliance_reasoning(labels, depth="deep", runs=2, fake_generator=True)

    assert report["summary"]["total"] == 4
    assert report["summary"]["accuracy"] == 1.0
    assert report["per_class"]["supported"]["recall"] == 1.0
    assert report["per_class"]["contradiction"]["recall"] == 1.0
    assert report["stability"]["flip_count"] == 0
    assert report["observability"]["llm_called_rows"] == 4
    assert report["observability"]["never_adjudicated_rows"] == 0
    assert report["observability"]["adjudicator_coverage"] == 1.0
    assert report["observability"]["candidate_count_total"] == 4
    assert report["latency"]["llm_called_mean_seconds"] >= 0.0
    assert report["latency"]["deterministic_mean_seconds"] == 0.0
    assert report["prompt_context"]["prompt_count"] == 4
    assert report["prompt_context"]["max_prompt_token_estimate"] > 0
    assert all(row["llm_called"] for row in report["rows"])
    assert all(row["candidate_count"] == 1 for row in report["rows"])
    markdown = format_compliance_markdown(report)
    assert "Compliance Reasoning Evaluation" in markdown
    assert "## Observability" in markdown
    assert "## Prompt Context" in markdown

    paths = write_compliance_scorecard(report, tmp_path)

    assert paths["markdown"].endswith(".md")
    assert paths["json"].endswith(".json")
