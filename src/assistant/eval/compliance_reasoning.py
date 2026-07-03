"""Evaluation harness for compliance reasoning model profiles."""

from __future__ import annotations

import json
import os
import re
import statistics
import time
from collections import Counter
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
PROMPT_CONTEXT_WARNING_THRESHOLD = 0.8
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
        self.model = "scripted-fake"
        self.num_ctx = 8192
        self.temperature = 0.0
        self.prompt_observations: list[dict[str, int | float | str | bool]] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        self.prompt_observations.append(_prompt_observation(prompt, model=self.model, num_ctx=self.num_ctx, temperature=self.temperature))
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
            prompt_snapshot = _prompt_observation_count(active_engine, request)
            pair_started = time.perf_counter()
            pair = active_engine.review_document_pair(external, internal, request)
            latency_seconds = time.perf_counter() - pair_started
            actual = _classification_from_pair(pair)
            diagnostics = _pair_diagnostics(pair)
            prompt_observations = _prompt_observation_delta(active_engine, request, prompt_snapshot)
            prompt_summary = _prompt_summary(prompt_observations)
            llm_called = bool(diagnostics.get("llm_called") or prompt_summary["prompt_count"] > 0)
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
                    "llm_called": llm_called,
                    "candidate_count": int(diagnostics.get("candidate_count", 0)),
                    "adjudication_count": int(diagnostics.get("adjudication_count", 0)),
                    "fallback_decision_count": int(diagnostics.get("fallback_decision_count", 0)),
                    "non_accepted_decision_count": int(diagnostics.get("non_accepted_decision_count", 0)),
                    "no_candidate_obligation_count": int(diagnostics.get("no_candidate_obligation_count", 0)),
                    "missing_obligation_fallback_count": int(diagnostics.get("missing_obligation_fallback_count", 0)),
                    "gate_demotion_reason": str(diagnostics.get("gate_demotion_reason", "")),
                    "gate_demotion_reasons": list(diagnostics.get("gate_demotion_reasons", [])),
                    "no_alignment_reason": str(diagnostics.get("no_alignment_reason", "")),
                    **prompt_summary,
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
        f"Mean LLM-called latency: {latency['llm_called_mean_seconds']:.1f}s",
        f"Mean deterministic latency: {latency['deterministic_mean_seconds']:.1f}s",
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

    observability = report["observability"]
    lines.extend(
        [
            "",
            "## Observability",
            "",
            f"Rows that called the LLM: {observability['llm_called_rows']}/{observability['total_rows']}",
            f"Adjudicator coverage: {observability['adjudicator_coverage']:.0%}",
            f"Never adjudicated rows: {observability['never_adjudicated_rows']}",
            f"Total candidate count: {observability['candidate_count_total']}",
            f"Total adjudication calls: {observability['adjudication_count_total']}",
            "",
            "| Expected class | Never adjudicated |",
            "|---|---:|",
        ]
    )
    for class_name, count in observability["never_adjudicated_by_expected"].items():
        lines.append(f"| {class_name} | {count} |")

    lines.extend(["", "### Gate Demotions", "", "| Reason | Count |", "|---|---:|"])
    if observability["gate_demotion_reasons"]:
        for reason, count in observability["gate_demotion_reasons"].items():
            lines.append(f"| {reason} | {count} |")
    else:
        lines.append("| none | 0 |")

    prompt_context = report["prompt_context"]
    lines.extend(
        [
            "",
            "## Prompt Context",
            "",
            f"Prompt calls observed: {prompt_context['prompt_count']}",
            f"Mean prompt-token estimate: {prompt_context['mean_prompt_token_estimate']:.0f}",
            f"Max prompt-token estimate: {prompt_context['max_prompt_token_estimate']}",
            f"Near context limit prompts: {prompt_context['near_context_limit_count']}",
            f"Context warning threshold: {prompt_context['context_warning_threshold']:.0%} of num_ctx",
        ]
    )

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
            "| Run | ID | Domain | Expected | Actual | Pass | LLM | Candidates | Gate reason | Latency |",
            "|---:|---|---|---|---|:--:|:--:|---:|---|---:|",
        ]
    )
    for row in report["rows"]:
        mark = "PASS" if row["passed"] else "FAIL"
        llm_mark = "yes" if row["llm_called"] else "no"
        gate_reason = row["gate_demotion_reason"] or row["no_alignment_reason"] or ""
        lines.append(
            f"| {row['run']} | {row['id']} | {row['domain']} | {row['expected']} | "
            f"{row['actual']} | {mark} | {llm_mark} | {row['candidate_count']} | "
            f"{gate_reason} | {row['latency_seconds']:.1f}s |"
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


def _pair_diagnostics(pair: dict[str, Any]) -> dict[str, Any]:
    diagnostics = pair.get("diagnostics", {})
    return diagnostics if isinstance(diagnostics, dict) else {}


def _prompt_observation_count(engine: DeterministicComplianceEngine, request: ComplianceReviewRequest) -> int:
    observations = _prompt_observations(engine, request)
    return len(observations)


def _prompt_observation_delta(
    engine: DeterministicComplianceEngine,
    request: ComplianceReviewRequest,
    start: int,
) -> list[dict[str, Any]]:
    observations = _prompt_observations(engine, request)
    return observations[start:]


def _prompt_observations(engine: DeterministicComplianceEngine, request: ComplianceReviewRequest) -> list[dict[str, Any]]:
    generator = _engine_generator(engine, request)
    observations = getattr(generator, "prompt_observations", [])
    return observations if isinstance(observations, list) else []


def _engine_generator(engine: DeterministicComplianceEngine, request: ComplianceReviewRequest) -> object | None:
    agent_getter = getattr(engine, "_agent_for_request", None)
    if not callable(agent_getter):
        return None
    agent = agent_getter(request)
    return getattr(agent, "generator", None)


def _prompt_observation(
    prompt: str,
    *,
    model: str,
    num_ctx: int,
    temperature: float,
) -> dict[str, int | float | str | bool]:
    token_estimate = max(1, int(len(prompt) / 4))
    threshold = int(num_ctx * PROMPT_CONTEXT_WARNING_THRESHOLD) if num_ctx > 0 else 0
    return {
        "model": model,
        "prompt_token_estimate": token_estimate,
        "num_ctx": num_ctx,
        "temperature": temperature,
        "near_context_limit": bool(threshold and token_estimate >= threshold),
        "context_warning_threshold": PROMPT_CONTEXT_WARNING_THRESHOLD,
    }


def _prompt_summary(observations: list[dict[str, Any]]) -> dict[str, Any]:
    estimates = [int(item.get("prompt_token_estimate", 0)) for item in observations]
    return {
        "prompt_count": len(observations),
        "max_prompt_token_estimate": max(estimates) if estimates else 0,
        "mean_prompt_token_estimate": round(statistics.mean(estimates), 3) if estimates else 0.0,
        "near_context_limit_count": sum(1 for item in observations if item.get("near_context_limit")),
        "num_ctx": max((int(item.get("num_ctx", 0)) for item in observations), default=0),
    }


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
        "latency": _latency_summary(rows, total_seconds),
        "observability": _observability_summary(rows, classes),
        "prompt_context": _prompt_context_summary(rows),
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


def _latency_summary(rows: list[dict[str, Any]], total_seconds: float) -> dict[str, float]:
    latencies = [float(row["latency_seconds"]) for row in rows]
    llm_latencies = [float(row["latency_seconds"]) for row in rows if row.get("llm_called")]
    deterministic_latencies = [float(row["latency_seconds"]) for row in rows if not row.get("llm_called")]
    return {
        "total_seconds": round(total_seconds, 3),
        "mean_seconds": round(statistics.mean(latencies), 3) if latencies else 0.0,
        "p95_seconds": round(_percentile(latencies, 0.95), 3) if latencies else 0.0,
        "llm_called_mean_seconds": round(statistics.mean(llm_latencies), 3) if llm_latencies else 0.0,
        "llm_called_p95_seconds": round(_percentile(llm_latencies, 0.95), 3) if llm_latencies else 0.0,
        "deterministic_mean_seconds": round(statistics.mean(deterministic_latencies), 3) if deterministic_latencies else 0.0,
        "deterministic_p95_seconds": round(_percentile(deterministic_latencies, 0.95), 3) if deterministic_latencies else 0.0,
    }


def _observability_summary(rows: list[dict[str, Any]], classes: list[str]) -> dict[str, Any]:
    total_rows = len(rows)
    llm_called_rows = sum(1 for row in rows if row.get("llm_called"))
    never_adjudicated_by_expected = {
        class_name: sum(1 for row in rows if row["expected"] == class_name and not row.get("llm_called"))
        for class_name in classes
    }
    gate_reason_counts = Counter(
        reason
        for row in rows
        for reason in row.get("gate_demotion_reasons", [])
        if str(reason).strip()
    )
    return {
        "total_rows": total_rows,
        "llm_called_rows": llm_called_rows,
        "never_adjudicated_rows": total_rows - llm_called_rows,
        "adjudicator_coverage": round(llm_called_rows / total_rows, 3) if total_rows else 0.0,
        "candidate_count_total": sum(int(row.get("candidate_count", 0)) for row in rows),
        "adjudication_count_total": sum(int(row.get("adjudication_count", 0)) for row in rows),
        "fallback_decision_count_total": sum(int(row.get("fallback_decision_count", 0)) for row in rows),
        "missing_obligation_fallback_count_total": sum(int(row.get("missing_obligation_fallback_count", 0)) for row in rows),
        "never_adjudicated_by_expected": never_adjudicated_by_expected,
        "gate_demotion_reasons": dict(gate_reason_counts),
    }


def _prompt_context_summary(rows: list[dict[str, Any]]) -> dict[str, float | int]:
    prompt_count = 0
    estimated_token_total = 0.0
    near_limit_count = 0
    max_num_ctx = 0
    max_prompt_token_estimate = 0
    for row in rows:
        count = int(row.get("prompt_count", 0))
        prompt_count += count
        estimated_token_total += float(row.get("mean_prompt_token_estimate", 0.0)) * count
        near_limit_count += int(row.get("near_context_limit_count", 0))
        max_num_ctx = max(max_num_ctx, int(row.get("num_ctx", 0)))
        max_prompt_token_estimate = max(max_prompt_token_estimate, int(row.get("max_prompt_token_estimate", 0)))
    return {
        "prompt_count": prompt_count,
        "mean_prompt_token_estimate": round(estimated_token_total / prompt_count, 3) if prompt_count else 0.0,
        "max_prompt_token_estimate": max_prompt_token_estimate,
        "near_context_limit_count": near_limit_count,
        "num_ctx": max_num_ctx,
        "context_warning_threshold": PROMPT_CONTEXT_WARNING_THRESHOLD,
    }


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
