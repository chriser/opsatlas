"""Tests for the compliance reasoning evaluation harness."""

from __future__ import annotations

from assistant.eval.compliance_model_comparison import (
    build_model_comparison,
    format_model_comparison_markdown,
    write_model_comparison,
)
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
    assert report["split_metrics"]["training"]["accuracy"] == 1.0
    assert report["ablation"]["model_only_accuracy"] == 1.0
    assert report["ablation"]["with_guards_accuracy"] == 1.0
    assert report["ablation"]["guard_changed_count"] == 0
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
    assert "## Guard Ablation" in markdown
    assert "## Observability" in markdown
    assert "## Prompt Context" in markdown

    paths = write_compliance_scorecard(report, tmp_path)

    assert paths["markdown"].endswith(".md")
    assert paths["json"].endswith(".json")


def test_compliance_model_comparison_ranks_holdout_and_latency(tmp_path) -> None:
    strong = _comparison_report(
        "qwen2.5:14b-instruct",
        accuracy=0.9,
        holdout_accuracy=0.83,
        holdout_model_only_accuracy=0.9,
        contradiction_precision=1.0,
        contradiction_recall=0.8,
        p95_latency=8.0,
    )
    slower = _comparison_report(
        "deepseek-r1:14b",
        accuracy=0.91,
        holdout_accuracy=0.83,
        holdout_model_only_accuracy=0.9,
        contradiction_precision=1.0,
        contradiction_recall=0.8,
        p95_latency=18.0,
    )
    weak = _comparison_report(
        "deepseek-r1:8b",
        accuracy=0.86,
        holdout_accuracy=0.75,
        holdout_model_only_accuracy=0.83,
        contradiction_precision=1.0,
        contradiction_recall=0.7,
        p95_latency=5.0,
    )

    comparison = build_model_comparison([slower, weak, strong])

    assert comparison["recommended_model"] == "qwen2.5:14b-instruct"
    assert [row["model"] for row in comparison["ranked"]] == [
        "qwen2.5:14b-instruct",
        "deepseek-r1:14b",
        "deepseek-r1:8b",
    ]
    markdown = format_model_comparison_markdown(comparison)
    assert "Compliance Model Comparison" in markdown
    assert "Holdout model-only" in markdown
    assert "Contradiction FP rate" in markdown

    paths = write_model_comparison(comparison, tmp_path)

    assert paths["markdown"].endswith(".md")
    assert paths["json"].endswith(".json")


def _comparison_report(
    model: str,
    *,
    accuracy: float,
    holdout_accuracy: float,
    holdout_model_only_accuracy: float,
    contradiction_precision: float,
    contradiction_recall: float,
    p95_latency: float,
) -> dict:
    return {
        "summary": {
            "generated_at": "2026-07-04T00:00:00+00:00",
            "model": model,
            "model_profile": f"balanced=ollama:deepseek-r1:8b;deep=ollama:{model}",
            "accuracy": accuracy,
        },
        "per_class": {
            "contradiction": {
                "precision": contradiction_precision,
                "recall": contradiction_recall,
                "f1": round(2 * contradiction_precision * contradiction_recall / (contradiction_precision + contradiction_recall), 3),
            }
        },
        "split_metrics": {
            "holdout": {
                "accuracy": holdout_accuracy,
            }
        },
        "ablation": {
            "model_only_accuracy": accuracy - 0.05,
            "with_guards_accuracy": accuracy,
            "guard_changed_count": 3,
            "guard_helped_count": 2,
            "guard_hurt_count": 1,
            "by_split": {
                "holdout": {
                    "model_only_accuracy": holdout_model_only_accuracy,
                }
            },
        },
        "latency": {
            "total_seconds": 100.0,
            "mean_seconds": 3.0,
            "p95_seconds": p95_latency,
            "llm_called_mean_seconds": 4.0,
            "llm_called_p95_seconds": p95_latency,
        },
        "stability": {
            "flip_count": 0,
        },
        "rows": [
            {"expected": "supported", "actual": "supported"},
            {"expected": "not_related", "actual": "not_related"},
            {"expected": "supported", "actual": "contradiction"},
        ],
    }
