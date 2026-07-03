"""Evaluation harness for compliance reasoning model profiles."""

from __future__ import annotations

import json
import os
import re
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from services.compliance_reasoning.agent import AgenticComplianceEngine, OllamaComplianceGenerator
from services.compliance_reasoning.engine import DeterministicComplianceEngine
from services.compliance_reasoning.models import (
    ComplianceReviewRequest,
    EvidenceDocument,
    EvidenceSection,
    FindingClassification,
    ReviewDepth,
    ReviewOptions,
)

DEFAULT_LABELS_PATH = Path("tests/evaluation/compliance_reasoning_labels.json")
DEFAULT_OUTPUT_DIR = Path("docs/benchmark/compliance")
REQUIRED_CLASSIFICATIONS = {
    "contradiction",
    "supported",
    "too_vague",
    "missing_obligation",
    "missing_detail",
    "not_related",
}


class ComplianceReasoningLabel(BaseModel):
    """One labelled external/internal evidence pair for reasoning evaluation."""

    model_config = ConfigDict(extra="forbid")

    id: str
    domain: str
    external_source: str
    external_excerpt: str
    internal_source: str
    internal_excerpt: str
    expected_classification: FindingClassification
    rationale: str

    @field_validator(
        "id",
        "domain",
        "external_source",
        "external_excerpt",
        "internal_source",
        "internal_excerpt",
        "rationale",
    )
    @classmethod
    def value_must_be_present(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must be present")
        return stripped


class ScriptedComplianceGenerator:
    """Deterministic model double used only to smoke-test the harness."""

    def __init__(self, classification: str) -> None:
        self.classification = classification
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        classification = self.classification
        same_obligation = classification != "not_related"
        if classification == "missing_obligation":
            # External adjudication cannot directly emit missing_obligation;
            # production creates it when no aligned internal claim exists.
            classification = "needs_human_review"
        severity = "low" if classification in {"not_related", "supported"} else "medium"
        return json.dumps(
            {
                "same_obligation": same_obligation,
                "classification": classification,
                "severity": severity,
                "confidence": 0.9,
                "rationale": "Scripted compliance generator response for harness validation.",
                "advisor_summary": "Scripted harness response.",
                "why_it_matters": "The fake generator validates harness plumbing only.",
                "recommended_action": "No action required." if classification == "supported" else "Review the labelled pair.",
                "proposed_internal_text": "",
                "confidence_interpretation": "Scripted response; not a quality benchmark.",
                "evidence_highlights": ["scripted external", "scripted internal"],
            }
        )


def load_compliance_labels(path: str | Path = DEFAULT_LABELS_PATH) -> list[ComplianceReasoningLabel]:
    raw_labels = json.loads(Path(path).read_text())
    if not isinstance(raw_labels, list):
        raise ValueError("Compliance reasoning label dataset must be a JSON list.")
    return [ComplianceReasoningLabel.model_validate(item) for item in raw_labels]


def evaluate_compliance_reasoning(
    labels: list[ComplianceReasoningLabel | dict[str, Any]],
    *,
    depth: ReviewDepth = "balanced",
    model: str = "",
    runs: int = 3,
    fake_generator: bool = False,
    throttle_deep: bool = False,
) -> dict[str, Any]:
    parsed_labels = [
        label if isinstance(label, ComplianceReasoningLabel) else ComplianceReasoningLabel.model_validate(label)
        for label in labels
    ]
    if runs < 1:
        raise ValueError("runs must be at least 1.")
    rows: list[dict[str, Any]] = []
    started = time.perf_counter()
    model_profile = ""

    engine = None if fake_generator else _build_engine(depth=depth, model=model, throttle_deep=throttle_deep)
    for run_number in range(1, runs + 1):
        for label in parsed_labels:
            active_engine = _build_engine_for_fake_label(label, depth=depth, throttle_deep=throttle_deep) if fake_generator else engine
            assert active_engine is not None
            request = _request_for_label(label, depth=depth, throttle_deep=throttle_deep)
            if not model_profile:
                model_profile = _model_profile(active_engine, request, fake_generator=fake_generator)
            external = request.external_documents[0]
            internal = request.internal_documents[0]
            pair_started = time.perf_counter()
            pair = active_engine.review_document_pair(external, internal, request)
            latency_seconds = time.perf_counter() - pair_started
            actual = _classification_from_pair(pair)
            rows.append(
                {
                    "run": run_number,
                    "id": label.id,
                    "domain": label.domain,
                    "expected": label.expected_classification,
                    "actual": actual,
                    "passed": actual == label.expected_classification,
                    "latency_seconds": round(latency_seconds, 3),
                    "finding_count": len(pair.get("findings", [])),
                    "pair_relevance_score": round(float(pair.get("relevance_score", 0.0)), 3),
                    "rationale": pair.get("rationale", ""),
                }
            )

    total_seconds = time.perf_counter() - started
    return _build_report(
        rows,
        labels=parsed_labels,
        depth=depth,
        model=model,
        model_profile=model_profile,
        runs=runs,
        fake_generator=fake_generator,
        throttle_deep=throttle_deep,
        total_seconds=total_seconds,
    )


def format_compliance_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    latency = report["latency"]
    lines = [
        f"# Compliance Reasoning Evaluation - {summary['passed']}/{summary['total']} passed ({summary['accuracy']:.0%})",
        "",
        f"Generated: {summary['generated_at']}",
        f"Depth: {summary['depth']}",
        f"Model profile: {summary['model_profile']}",
        f"Runs: {summary['runs']}",
        f"Fake generator: {summary['fake_generator']}",
        f"Throttle deep: {summary['throttle_deep']}",
        "",
        f"Total runtime: {latency['total_seconds']:.1f}s",
        f"Mean pair latency: {latency['mean_seconds']:.1f}s",
        f"P95 pair latency: {latency['p95_seconds']:.1f}s",
        "",
        "## Per-Class Metrics",
        "",
        "| Class | Precision | Recall | F1 | Support |",
        "|---|---:|---:|---:|---:|",
    ]
    for class_name, metrics in report["per_class"].items():
        lines.append(
            f"| {class_name} | {metrics['precision']:.0%} | {metrics['recall']:.0%} | "
            f"{metrics['f1']:.0%} | {metrics['support']} |"
        )

    classes = report["classes"]
    lines.extend(["", "## Confusion Matrix", "", "| Expected \\ Actual | " + " | ".join(classes) + " |"])
    lines.append("|---|" + "|".join("---:" for _ in classes) + "|")
    for expected in classes:
        row = report["confusion_matrix"].get(expected, {})
        lines.append("| " + expected + " | " + " | ".join(str(row.get(actual, 0)) for actual in classes) + " |")

    stability = report["stability"]
    lines.extend(
        [
            "",
            "## Stability",
            "",
            f"Labels with classification flips: {stability['flip_count']}/{stability['label_count']}",
            f"Classification variance: {stability['classification_variance']:.0%}",
            "",
            "## Pair Results",
            "",
            "| Run | ID | Domain | Expected | Actual | Pass | Latency |",
            "|---:|---|---|---|---|:--:|---:|",
        ]
    )
    for row in report["rows"]:
        mark = "PASS" if row["passed"] else "FAIL"
        lines.append(
            f"| {row['run']} | {row['id']} | {row['domain']} | {row['expected']} | "
            f"{row['actual']} | {mark} | {row['latency_seconds']:.1f}s |"
        )
    return "\n".join(lines)


def write_compliance_scorecard(report: dict[str, Any], output_dir: str | Path = DEFAULT_OUTPUT_DIR) -> dict[str, str]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    stem = _safe_filename(
        f"{report['summary']['depth']}-{report['summary']['model_profile']}-{report['summary']['generated_at'].replace(':', '-')}"
    )
    markdown_path = output_path / f"{stem}.md"
    json_path = output_path / f"{stem}.json"
    markdown_path.write_text(format_compliance_markdown(report))
    json_path.write_text(json.dumps(report, indent=2))
    return {"markdown": str(markdown_path), "json": str(json_path)}


def _build_engine(depth: ReviewDepth, model: str, throttle_deep: bool) -> DeterministicComplianceEngine:
    if depth == "fast":
        return DeterministicComplianceEngine()
    model_name = model or _model_from_env(depth, throttle_deep=throttle_deep)
    profile = "DEEP_THROTTLED" if depth == "deep" and throttle_deep else depth.upper()
    generator = OllamaComplianceGenerator(
        base_url=os.environ.get("KP_OLLAMA_URL", "http://127.0.0.1:11434"),
        model=model_name,
        num_ctx=int(os.environ.get(f"KP_COMPLIANCE_{profile}_LLM_NUM_CTX", os.environ.get("KP_COMPLIANCE_LLM_NUM_CTX", "8192"))),
        timeout=float(os.environ.get(f"KP_COMPLIANCE_{profile}_LLM_TIMEOUT", os.environ.get("KP_COMPLIANCE_LLM_TIMEOUT", "120"))),
    )
    return AgenticComplianceEngine(
        generator=generator,
        model_name=model_name,
        depth_generators={depth: generator},
        depth_model_names={depth: model_name},
    )


def _build_engine_for_fake_label(
    label: ComplianceReasoningLabel,
    *,
    depth: ReviewDepth,
    throttle_deep: bool,
) -> DeterministicComplianceEngine:
    if depth == "fast":
        return DeterministicComplianceEngine()
    generator = ScriptedComplianceGenerator(label.expected_classification)
    return AgenticComplianceEngine(
        generator=generator,
        model_name="scripted-fake",
        depth_generators={depth: generator},
        depth_model_names={depth: "scripted-fake"},
    )


def _request_for_label(label: ComplianceReasoningLabel, *, depth: ReviewDepth, throttle_deep: bool) -> ComplianceReviewRequest:
    external = EvidenceDocument(
        id=f"{label.id}-external",
        title=label.external_source,
        source_type="external",
        content_sha256=f"label-{label.id}-external",
        sections=[
            EvidenceSection(
                id=f"{label.id}-external-s1",
                heading=label.external_source,
                citation=label.external_source,
                ordinal=1,
                text=label.external_excerpt,
            )
        ],
    )
    internal = EvidenceDocument(
        id=f"{label.id}-internal",
        title=label.internal_source,
        source_type="internal",
        content_sha256=f"label-{label.id}-internal",
        sections=[
            EvidenceSection(
                id=f"{label.id}-internal-s1",
                heading=label.internal_source,
                citation=label.internal_source,
                ordinal=1,
                text=label.internal_excerpt,
            )
        ],
    )
    return ComplianceReviewRequest(
        external_documents=[external],
        internal_documents=[internal],
        options=ReviewOptions(
            include_supported_findings=True,
            include_missing_obligations=True,
            include_not_related_pairs=True,
            min_pair_relevance_score=0.0,
            max_findings=10,
            force_rerun=True,
            review_depth=depth,
            throttle_deep=throttle_deep,
        ),
    )


def _classification_from_pair(pair: dict[str, Any]) -> str:
    findings = pair.get("findings", [])
    if findings:
        first = findings[0]
        if isinstance(first, dict):
            return str(first.get("classification", "supported"))
        return str(getattr(first, "classification", "supported"))
    return str(pair.get("classification") or "supported")


def _build_report(
    rows: list[dict[str, Any]],
    *,
    labels: list[ComplianceReasoningLabel],
    depth: str,
    model: str,
    model_profile: str,
    runs: int,
    fake_generator: bool,
    throttle_deep: bool,
    total_seconds: float,
) -> dict[str, Any]:
    classes = _ordered_classes(labels, rows)
    confusion_matrix = _confusion_matrix(rows, classes)
    per_class = _per_class_metrics(confusion_matrix, classes)
    passed = sum(1 for row in rows if row["passed"])
    latencies = [float(row["latency_seconds"]) for row in rows]
    return {
        "summary": {
            "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "total": len(rows),
            "passed": passed,
            "accuracy": round(passed / len(rows), 3) if rows else 0.0,
            "depth": depth,
            "model": model,
            "model_profile": model_profile or ("scripted-fake" if fake_generator else "deterministic-fallback"),
            "runs": runs,
            "fake_generator": fake_generator,
            "throttle_deep": throttle_deep,
        },
        "classes": classes,
        "per_class": per_class,
        "confusion_matrix": confusion_matrix,
        "latency": {
            "total_seconds": round(total_seconds, 3),
            "mean_seconds": round(statistics.mean(latencies), 3) if latencies else 0.0,
            "p95_seconds": round(_percentile(latencies, 0.95), 3) if latencies else 0.0,
        },
        "stability": _stability(rows, labels),
        "rows": rows,
    }


def _confusion_matrix(rows: list[dict[str, Any]], classes: list[str]) -> dict[str, dict[str, int]]:
    matrix = {expected: {actual: 0 for actual in classes} for expected in classes}
    for row in rows:
        expected = row["expected"]
        actual = row["actual"]
        if expected not in matrix:
            matrix[expected] = {class_name: 0 for class_name in classes}
        if actual not in matrix[expected]:
            matrix[expected][actual] = 0
        matrix[expected][actual] += 1
    return matrix


def _per_class_metrics(confusion_matrix: dict[str, dict[str, int]], classes: list[str]) -> dict[str, dict[str, float | int]]:
    metrics: dict[str, dict[str, float | int]] = {}
    for class_name in classes:
        tp = confusion_matrix.get(class_name, {}).get(class_name, 0)
        fp = sum(row.get(class_name, 0) for expected, row in confusion_matrix.items() if expected != class_name)
        fn = sum(count for actual, count in confusion_matrix.get(class_name, {}).items() if actual != class_name)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
        metrics[class_name] = {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "support": tp + fn,
        }
    return metrics


def _stability(rows: list[dict[str, Any]], labels: list[ComplianceReasoningLabel]) -> dict[str, Any]:
    predictions_by_label: dict[str, set[str]] = {label.id: set() for label in labels}
    for row in rows:
        predictions_by_label.setdefault(row["id"], set()).add(row["actual"])
    flip_count = sum(1 for predictions in predictions_by_label.values() if len(predictions) > 1)
    label_count = len(predictions_by_label)
    return {
        "label_count": label_count,
        "flip_count": flip_count,
        "classification_variance": round(flip_count / label_count, 3) if label_count else 0.0,
        "flipped_label_ids": sorted(label_id for label_id, predictions in predictions_by_label.items() if len(predictions) > 1),
    }


def _ordered_classes(labels: list[ComplianceReasoningLabel], rows: list[dict[str, Any]]) -> list[str]:
    priority = [
        "contradiction",
        "missing_obligation",
        "missing_detail",
        "too_vague",
        "supported",
        "not_related",
        "needs_human_review",
    ]
    seen = {label.expected_classification for label in labels}
    seen.update(str(row["actual"]) for row in rows)
    return [class_name for class_name in priority if class_name in seen] + sorted(seen.difference(priority))


def _percentile(values: list[float], percentile: float) -> float:
    sorted_values = sorted(values)
    index = min(len(sorted_values) - 1, max(0, int(round((len(sorted_values) - 1) * percentile))))
    return sorted_values[index]


def _model_profile(engine: DeterministicComplianceEngine, request: ComplianceReviewRequest, *, fake_generator: bool) -> str:
    if fake_generator:
        return f"{request.options.review_depth}=scripted-fake"
    profile_getter = getattr(engine, "model_profile_for_request", None)
    if callable(profile_getter):
        return str(profile_getter(request))
    return str(getattr(engine, "model_profile", "deterministic-fallback"))


def _model_from_env(depth: ReviewDepth, *, throttle_deep: bool) -> str:
    if depth == "balanced":
        return os.environ.get("KP_COMPLIANCE_BALANCED_LLM_MODEL", "deepseek-r1:8b")
    if throttle_deep:
        return os.environ.get("KP_COMPLIANCE_DEEP_THROTTLED_LLM_MODEL", os.environ.get("KP_COMPLIANCE_DEEP_LLM_MODEL", "deepseek-r1:14b"))
    return os.environ.get("KP_COMPLIANCE_DEEP_LLM_MODEL", os.environ.get("KP_COMPLIANCE_LLM_MODEL", "deepseek-r1:14b"))


def _safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-").lower()
