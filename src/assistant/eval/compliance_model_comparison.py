"""Model-comparison helpers for compliance reasoning scorecards."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .compliance_reasoning import DEFAULT_OUTPUT_DIR

DEFAULT_MODEL_MATRIX = (
    "deepseek-r1:8b",
    "deepseek-r1:14b",
    "deepseek-r1:32b",
    "qwen2.5:7b-instruct",
    "qwen2.5:14b-instruct",
)


def build_model_comparison(reports: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a compact comparison table from model scorecard reports."""
    rows = [_model_row(report) for report in reports]
    ranked = sorted(
        rows,
        key=lambda row: (
            row["holdout_model_only_accuracy"],
            row["holdout_accuracy"],
            row["contradiction_precision"],
            row["contradiction_recall"],
            -row["p95_latency_seconds"],
            -row["total_seconds"],
        ),
        reverse=True,
    )
    return {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "models_compared": len(rows),
        "ranking_basis": (
            "Sort by holdout model-only accuracy, holdout guarded accuracy, contradiction precision, "
            "contradiction recall, then lower p95 latency."
        ),
        "recommended_model": ranked[0]["model"] if ranked else "",
        "rows": rows,
        "ranked": ranked,
        "source_scorecards": [
            report.get("outputs", {}).get("json", "") or report.get("source_path", "")
            for report in reports
        ],
    }


def write_model_comparison(comparison: dict[str, Any], output_dir: str | Path = DEFAULT_OUTPUT_DIR) -> dict[str, str]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    stamp = comparison["generated_at"].replace(":", "-")
    markdown_path = output_path / f"model-comparison-{stamp}.md"
    json_path = output_path / f"model-comparison-{stamp}.json"
    markdown_path.write_text(format_model_comparison_markdown(comparison))
    json_path.write_text(json.dumps(comparison, indent=2))
    return {"markdown": str(markdown_path), "json": str(json_path)}


def format_model_comparison_markdown(comparison: dict[str, Any]) -> str:
    rows = comparison["ranked"]
    lines = [
        f"# Compliance Model Comparison - {comparison['models_compared']} models",
        "",
        f"Generated: {comparison['generated_at']}",
        f"Recommended model: `{comparison['recommended_model'] or 'n/a'}`",
        "",
        f"Ranking basis: {comparison['ranking_basis']}",
        "",
        "## Summary",
        "",
        (
            "| Rank | Model | Profile | Overall | Holdout | Holdout model-only | "
            "Contradiction P/R/F1 | Contradiction FP rate | P95 latency | Stability flips | Guard hurt |"
        ),
        "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for index, row in enumerate(rows, start=1):
        lines.append(
            f"| {index} | `{row['model']}` | {row['model_profile']} | "
            f"{row['accuracy']:.1%} | {row['holdout_accuracy']:.1%} | "
            f"{row['holdout_model_only_accuracy']:.1%} | "
            f"{row['contradiction_precision']:.1%}/{row['contradiction_recall']:.1%}/{row['contradiction_f1']:.1%} | "
            f"{row['contradiction_false_positive_rate']:.1%} | "
            f"{row['p95_latency_seconds']:.1f}s | {row['stability_flips']} | {row['guard_hurt_count']} |"
        )

    lines.extend(
        [
            "",
            "## Latency",
            "",
            "| Model | Total runtime | Mean pair | Mean LLM-called | P95 LLM-called |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for row in rows:
        lines.append(
            f"| `{row['model']}` | {row['total_seconds']:.1f}s | {row['mean_latency_seconds']:.1f}s | "
            f"{row['llm_mean_latency_seconds']:.1f}s | {row['llm_p95_latency_seconds']:.1f}s |"
        )

    lines.extend(
        [
            "",
            "## Guard Ablation",
            "",
            "| Model | Model-only | With guards | Holdout model-only | Holdout with guards | Guard changed | Helped | Hurt |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in rows:
        lines.append(
            f"| `{row['model']}` | {row['model_only_accuracy']:.1%} | {row['with_guards_accuracy']:.1%} | "
            f"{row['holdout_model_only_accuracy']:.1%} | {row['holdout_accuracy']:.1%} | "
            f"{row['guard_changed_count']} | {row['guard_helped_count']} | {row['guard_hurt_count']} |"
        )

    lines.extend(
        [
            "",
            "## Interpretation Notes",
            "",
            "- Prefer clean-holdout and model-only performance over saturated training accuracy.",
            "- Do not choose a slower model unless it materially improves holdout quality or contradiction recall.",
            "- Treat contradiction precision as a safety gate: false alarms can erode reviewer trust.",
            "- Record whether the chosen default updates `KP_COMPLIANCE_DEEP_LLM_MODEL` or reaffirms the current default.",
            "",
            "## Source Scorecards",
            "",
        ]
    )
    for path in comparison["source_scorecards"]:
        if path:
            lines.append(f"- `{path}`")
    return "\n".join(lines)


def load_reports(paths: list[str | Path]) -> list[dict[str, Any]]:
    reports = []
    for path in paths:
        report = json.loads(Path(path).read_text())
        report["source_path"] = str(path)
        reports.append(report)
    return reports


def _model_row(report: dict[str, Any]) -> dict[str, Any]:
    summary = report["summary"]
    latency = report["latency"]
    per_class = report["per_class"]
    contradiction = per_class.get("contradiction", {})
    split_metrics = report.get("split_metrics", {})
    holdout = split_metrics.get("holdout", {})
    ablation = report.get("ablation", {})
    holdout_ablation = ablation.get("by_split", {}).get("holdout", {})
    stability = report.get("stability", {})
    rows = report.get("rows", [])
    return {
        "model": summary.get("model") or summary.get("model_profile", ""),
        "model_profile": summary.get("model_profile", ""),
        "accuracy": float(summary.get("accuracy", 0.0)),
        "model_only_accuracy": float(ablation.get("model_only_accuracy", 0.0)),
        "with_guards_accuracy": float(ablation.get("with_guards_accuracy", summary.get("accuracy", 0.0))),
        "holdout_accuracy": float(holdout.get("accuracy", 0.0)),
        "holdout_model_only_accuracy": float(holdout_ablation.get("model_only_accuracy", 0.0)),
        "contradiction_precision": float(contradiction.get("precision", 0.0)),
        "contradiction_recall": float(contradiction.get("recall", 0.0)),
        "contradiction_f1": float(contradiction.get("f1", 0.0)),
        "contradiction_false_positive_rate": _contradiction_false_positive_rate(rows),
        "total_seconds": float(latency.get("total_seconds", 0.0)),
        "mean_latency_seconds": float(latency.get("mean_seconds", 0.0)),
        "p95_latency_seconds": float(latency.get("p95_seconds", 0.0)),
        "llm_mean_latency_seconds": float(latency.get("llm_called_mean_seconds", 0.0)),
        "llm_p95_latency_seconds": float(latency.get("llm_called_p95_seconds", 0.0)),
        "stability_flips": int(stability.get("flip_count", 0)),
        "guard_changed_count": int(ablation.get("guard_changed_count", 0)),
        "guard_helped_count": int(ablation.get("guard_helped_count", 0)),
        "guard_hurt_count": int(ablation.get("guard_hurt_count", 0)),
    }


def _contradiction_false_positive_rate(rows: list[dict[str, Any]]) -> float:
    non_contradictions = [row for row in rows if row.get("expected") != "contradiction"]
    if not non_contradictions:
        return 0.0
    false_positives = sum(1 for row in non_contradictions if row.get("actual") == "contradiction")
    return round(false_positives / len(non_contradictions), 3)
