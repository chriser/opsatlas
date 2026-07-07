"""RAG-vs-OAG benchmark scorecard aggregation for Analytics."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_OAG_BENCHMARK_DIR = Path("docs/benchmark/oag")
TARGET_CONFIGS = ("rag_only", "oag_first")


def build_oag_benchmark_report(scorecard_dir: str | Path = DEFAULT_OAG_BENCHMARK_DIR) -> dict[str, Any]:
    scorecards = load_oag_scorecards(scorecard_dir)
    latest = scorecards[0] if scorecards else None
    return {
        "scorecard_count": len(scorecards),
        "latest": latest,
        "history": [
            _history_item(scorecard)
            for scorecard in scorecards
        ],
        "boundary": (
            "This dashboard reads committed benchmark scorecards only. It does not rerun RAG or OAG, "
            "and diagnostic runs must not be treated as architecture decisions."
        ),
    }


def load_oag_scorecards(scorecard_dir: str | Path = DEFAULT_OAG_BENCHMARK_DIR) -> list[dict[str, Any]]:
    root = Path(scorecard_dir)
    if not root.exists():
        return []
    reports = []
    for path in root.glob("rag-vs-oag-*.json"):
        if "old" in path.parts:
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(raw, dict) or "summary" not in raw:
            continue
        reports.append(_normalise_scorecard(raw, path))
    return sorted(reports, key=lambda report: report["generated_at"], reverse=True)


def _normalise_scorecard(raw: dict[str, Any], path: Path) -> dict[str, Any]:
    summary = raw.get("summary", {})
    configs = list(summary.get("configs", []))
    generated_at = str(summary.get("generated_at") or _file_timestamp(path))
    evidence_grade = _evidence_grade(summary)
    category_lift = _category_lift(raw.get("by_category", {}))
    split_lift = _split_lift(raw.get("by_split", {}))
    return {
        "path": str(path),
        "markdown_path": str(path.with_suffix(".md")),
        "generated_at": generated_at,
        "dataset_version": summary.get("dataset_version", ""),
        "source_corpus": summary.get("source_corpus", ""),
        "question_count": summary.get("question_count", 0),
        "evaluated_question_count": summary.get("evaluated_question_count", 0),
        "split_filter": summary.get("split_filter", "all"),
        "category_filter": summary.get("category_filter", []),
        "id_filter": summary.get("id_filter", []),
        "split_counts": summary.get("split_counts", {}),
        "runs": summary.get("runs", 0),
        "configs": configs,
        "model_info": summary.get("model_info", {}),
        "best_config": summary.get("best_config", ""),
        "winner_config": summary.get("winner_config", ""),
        "diagnostic_run": bool(summary.get("diagnostic_run", False)),
        "diagnostic_reasons": list(summary.get("diagnostic_reasons", [])),
        "evidence_grade": evidence_grade,
        "decision_grade": evidence_grade in {"decision_grade", "holdout_decision"},
        "code_state": summary.get("code_state", {}),
        "latency": raw.get("latency", {}),
        "by_config": raw.get("by_config", {}),
        "by_split": raw.get("by_split", {}),
        "by_split_category": raw.get("by_split_category", {}),
        "by_category": raw.get("by_category", {}),
        "category_lift": category_lift,
        "split_lift": split_lift,
        "path_usage": _matrix_with_totals(raw.get("path_usage", {})),
        "citation_type_usage": _matrix_with_totals(raw.get("citation_type_usage", {})),
        "stability": raw.get("stability", {}),
        "interpretation_targets": raw.get("interpretation_targets", {}),
        "verdict": _verdict(raw, category_lift, split_lift, evidence_grade),
        "rows": [_row_detail(row) for row in raw.get("rows", [])],
    }


def _evidence_grade(summary: dict[str, Any]) -> str:
    configs = set(summary.get("configs", []))
    runs = int(summary.get("runs", 0) or 0)
    split_filter = summary.get("split_filter", "all")
    category_filter = summary.get("category_filter") or []
    id_filter = summary.get("id_filter") or []
    split_counts = summary.get("split_counts", {})
    evaluated_count = int(summary.get("evaluated_question_count", 0) or 0)
    expected_holdout_count = int(split_counts.get("holdout", 0) or 0)
    has_target_configs = set(TARGET_CONFIGS).issubset(configs)
    no_narrow_filters = not category_filter and not id_filter
    if not summary.get("diagnostic_run", False):
        return "decision_grade"
    if (
        runs >= 3
        and has_target_configs
        and split_filter == "holdout"
        and no_narrow_filters
        and expected_holdout_count > 0
        and evaluated_count >= expected_holdout_count
    ):
        return "holdout_decision"
    return "diagnostic"


def _category_lift(by_category: dict[str, Any]) -> list[dict[str, Any]]:
    rag = by_category.get("rag_only", {})
    oag = by_category.get("oag_first", {})
    categories = sorted(set(rag) | set(oag))
    return [
        {
            "category": category,
            "rag_only_accuracy": _accuracy(rag.get(category, {})),
            "oag_first_accuracy": _accuracy(oag.get(category, {})),
            "lift": round(_accuracy(oag.get(category, {})) - _accuracy(rag.get(category, {})), 4),
            "rag_only_total": _total(rag.get(category, {})),
            "oag_first_total": _total(oag.get(category, {})),
        }
        for category in categories
    ]


def _split_lift(by_split: dict[str, Any]) -> list[dict[str, Any]]:
    rag = by_split.get("rag_only", {})
    oag = by_split.get("oag_first", {})
    splits = sorted(set(rag) | set(oag))
    return [
        {
            "split": split,
            "rag_only_accuracy": _accuracy(rag.get(split, {})),
            "oag_first_accuracy": _accuracy(oag.get(split, {})),
            "lift": round(_accuracy(oag.get(split, {})) - _accuracy(rag.get(split, {})), 4),
            "rag_only_total": _total(rag.get(split, {})),
            "oag_first_total": _total(oag.get(split, {})),
        }
        for split in splits
    ]


def _matrix_with_totals(matrix: dict[str, Any]) -> dict[str, Any]:
    return {
        config: {
            "counts": counts,
            "total": sum(int(value or 0) for value in counts.values()),
        }
        for config, counts in matrix.items()
        if isinstance(counts, dict)
    }


def _row_detail(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "run": row.get("run"),
        "config": row.get("config", ""),
        "id": row.get("id", ""),
        "split": row.get("split", ""),
        "category": row.get("category", ""),
        "question": row.get("question", ""),
        "expected_path": row.get("expected_path", ""),
        "answer_path": row.get("answer_path", ""),
        "mode": row.get("mode", ""),
        "refused": bool(row.get("refused", False)),
        "confidence": row.get("confidence", ""),
        "grounding": row.get("grounding", ""),
        "facts_hit": row.get("facts_hit", []),
        "facts_missed": row.get("facts_missed", []),
        "passed": bool(row.get("passed", False)),
        "expected_path_hit": bool(row.get("expected_path_hit", False)),
        "citation_types": row.get("citation_types", []),
        "citation_count": row.get("citation_count", 0),
        "latency_seconds": row.get("latency_seconds", 0),
    }


def _verdict(
    raw: dict[str, Any],
    category_lift: list[dict[str, Any]],
    split_lift: list[dict[str, Any]],
    evidence_grade: str,
) -> dict[str, Any]:
    by_config = raw.get("by_config", {})
    rag_accuracy = _accuracy(by_config.get("rag_only", {}))
    oag_accuracy = _accuracy(by_config.get("oag_first", {}))
    lift = round(oag_accuracy - rag_accuracy, 4)
    positive_categories = [row["category"] for row in category_lift if row["lift"] > 0]
    weaker_categories = [row["category"] for row in category_lift if row["lift"] < 0]
    return {
        "headline": _headline(oag_accuracy, rag_accuracy, evidence_grade),
        "rag_only_accuracy": rag_accuracy,
        "oag_first_accuracy": oag_accuracy,
        "overall_lift": lift,
        "positive_categories": positive_categories,
        "weaker_categories": weaker_categories,
        "split_lift": split_lift,
    }


def _headline(oag_accuracy: float, rag_accuracy: float, evidence_grade: str) -> str:
    if evidence_grade == "diagnostic":
        return "Diagnostic run only: use the metrics to inspect behaviour, not to make an architecture decision."
    if oag_accuracy > rag_accuracy:
        return "OAG-first is ahead of RAG-only on this benchmark evidence."
    if oag_accuracy == rag_accuracy:
        return "OAG-first and RAG-only are tied on this benchmark evidence."
    return "RAG-only is ahead of OAG-first on this benchmark evidence."


def _history_item(scorecard: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": scorecard["path"],
        "generated_at": scorecard["generated_at"],
        "dataset_version": scorecard["dataset_version"],
        "runs": scorecard["runs"],
        "configs": scorecard["configs"],
        "split_filter": scorecard["split_filter"],
        "evaluated_question_count": scorecard["evaluated_question_count"],
        "evidence_grade": scorecard["evidence_grade"],
        "decision_grade": scorecard["decision_grade"],
        "rag_only_accuracy": scorecard["verdict"]["rag_only_accuracy"],
        "oag_first_accuracy": scorecard["verdict"]["oag_first_accuracy"],
        "overall_lift": scorecard["verdict"]["overall_lift"],
    }


def _accuracy(metrics: dict[str, Any]) -> float:
    return round(float(metrics.get("accuracy", 0.0) or 0.0), 4)


def _total(metrics: dict[str, Any]) -> int:
    return int(metrics.get("total", 0) or 0)


def _file_timestamp(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).isoformat()
