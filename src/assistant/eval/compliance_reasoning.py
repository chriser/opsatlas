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

from services.compliance_reasoning.agent import AgenticComplianceEngine, OllamaComplianceEmbedder, OllamaComplianceGenerator
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
    split: str = "training"

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

    @field_validator("split")
    @classmethod
    def split_must_be_supported(cls, value: str) -> str:
        stripped = value.strip() or "training"
        if stripped not in {"training", "in_domain", "holdout"}:
            raise ValueError("split must be 'training', 'in_domain' or 'holdout'.")
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
        same_obligation = classification not in {"missing_obligation", "not_related"}
        if classification in {"not_related", "supported"}:
            severity = "low"
        elif classification == "missing_obligation":
            severity = "high"
        else:
            severity = "medium"
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
    disable_safety_gates: bool = False,
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
            request = _request_for_label(
                label,
                depth=depth,
                throttle_deep=throttle_deep,
                disable_safety_gates=disable_safety_gates,
            )
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
            model_only_actual = _model_only_classification(diagnostics, fallback_actual=actual)
            prompt_observations = _prompt_observation_delta(active_engine, request, prompt_snapshot)
            prompt_summary = _prompt_summary(prompt_observations)
            llm_called = bool(diagnostics.get("llm_called") or prompt_summary["prompt_count"] > 0)
            rows.append(
                {
                    "run": run_number,
                    "id": label.id,
                    "domain": label.domain,
                    "split": label.split,
                    "expected": label.expected_classification,
                    "actual": actual,
                    "passed": actual == label.expected_classification,
                    "model_only_actual": model_only_actual,
                    "model_only_passed": model_only_actual == label.expected_classification,
                    "guard_changed_classification": model_only_actual != actual,
                    "latency_seconds": round(latency_seconds, 3),
                    "finding_count": len(pair.get("findings", [])),
                    "pair_relevance_score": round(float(pair.get("relevance_score", 0.0)), 3),
                    "rationale": pair.get("rationale", ""),
                    "llm_called": llm_called,
                    "candidate_count": int(diagnostics.get("candidate_count", 0)),
                    "candidate_comparison_count": int(diagnostics.get("candidate_comparison_count", 0)),
                    "lexical_candidate_count": int(diagnostics.get("lexical_candidate_count", 0)),
                    "anchor_candidate_count": int(diagnostics.get("anchor_candidate_count", 0)),
                    "semantic_candidate_count": int(diagnostics.get("semantic_candidate_count", 0)),
                    "semantic_attempt_count": int(diagnostics.get("semantic_attempt_count", 0)),
                    "max_lexical_score": round(float(diagnostics.get("max_lexical_score", 0.0)), 3),
                    "max_semantic_score": round(float(diagnostics.get("max_semantic_score", 0.0)), 3),
                    "max_alignment_score": round(float(diagnostics.get("max_alignment_score", 0.0)), 3),
                    "shared_anchor_overlap_count": int(diagnostics.get("shared_anchor_overlap_count", 0)),
                    "embedding_error_count": int(diagnostics.get("embedding_error_count", 0)),
                    "same_obligation_screen_count": int(diagnostics.get("same_obligation_screen_count", 0)),
                    "same_obligation_screen_pass_count": int(diagnostics.get("same_obligation_screen_pass_count", 0)),
                    "same_obligation_screen_reject_count": int(diagnostics.get("same_obligation_screen_reject_count", 0)),
                    "same_obligation_screen_error_count": int(diagnostics.get("same_obligation_screen_error_count", 0)),
                    "same_obligation_screen_fallback_count": int(diagnostics.get("same_obligation_screen_fallback_count", 0)),
                    "same_obligation_screen_override_count": int(diagnostics.get("same_obligation_screen_override_count", 0)),
                    "same_obligation_screen_latency_seconds": round(
                        float(diagnostics.get("same_obligation_screen_latency_seconds", 0.0)),
                        3,
                    ),
                    "same_obligation_screen_decisions": list(diagnostics.get("same_obligation_screen_decisions", [])),
                    "same_obligation_screen_errors": list(diagnostics.get("same_obligation_screen_errors", [])),
                    "adjudication_count": int(diagnostics.get("adjudication_count", 0)),
                    "fallback_decision_count": int(diagnostics.get("fallback_decision_count", 0)),
                    "fallback_decision_reasons": list(diagnostics.get("fallback_decision_reasons", [])),
                    "non_accepted_decision_count": int(diagnostics.get("non_accepted_decision_count", 0)),
                    "no_candidate_obligation_count": int(diagnostics.get("no_candidate_obligation_count", 0)),
                    "no_candidate_not_related_count": int(diagnostics.get("no_candidate_not_related_count", 0)),
                    "missing_obligation_fallback_count": int(diagnostics.get("missing_obligation_fallback_count", 0)),
                    "rejected_candidate_finding_count": int(diagnostics.get("rejected_candidate_finding_count", 0)),
                    "no_candidate_resolution": str(diagnostics.get("no_candidate_resolution", "")),
                    "no_candidate_resolutions": list(diagnostics.get("no_candidate_resolutions", [])),
                    "gate_demotion_reason": str(diagnostics.get("gate_demotion_reason", "")),
                    "gate_demotion_reasons": list(diagnostics.get("gate_demotion_reasons", [])),
                    "model_decision_classifications": list(diagnostics.get("model_decision_classifications", [])),
                    "final_decision_classifications": list(diagnostics.get("final_decision_classifications", [])),
                    "accepted_decision_classifications": list(diagnostics.get("accepted_decision_classifications", [])),
                    "rejected_decision_classifications": list(diagnostics.get("rejected_decision_classifications", [])),
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
        disable_safety_gates=disable_safety_gates,
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
        f"Safety gates disabled: {summary['disable_safety_gates']}",
        f"Semantic candidate threshold: {summary['semantic_candidate_threshold']:.2f}",
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

    lines.extend(
        [
            "",
            "## Split Metrics",
            "",
            "| Split | Passed | Accuracy | LLM Coverage | not_related Recall | Contradiction Precision |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for split, metrics in report["split_metrics"].items():
        split_total = int(metrics["total"])
        split_passed = int(metrics["passed"])
        split_accuracy = float(metrics["accuracy"])
        split_observability = metrics["observability"]
        split_per_class = metrics["per_class"]
        not_related_recall = float(split_per_class.get("not_related", {}).get("recall", 0.0))
        contradiction_precision = float(split_per_class.get("contradiction", {}).get("precision", 0.0))
        lines.append(
            f"| {split} | {split_passed}/{split_total} | {split_accuracy:.0%} | "
            f"{float(split_observability['adjudicator_coverage']):.0%} | {not_related_recall:.0%} | "
            f"{contradiction_precision:.0%} |"
        )

    ablation = report["ablation"]
    lines.extend(
        [
            "",
            "## Guard Ablation",
            "",
            f"Model-only accuracy: {ablation['model_only_passed']}/{ablation['total']} ({ablation['model_only_accuracy']:.0%})",
            f"With-guards accuracy: {ablation['with_guards_passed']}/{ablation['total']} ({ablation['with_guards_accuracy']:.0%})",
            f"Guard-changed classifications: {ablation['guard_changed_count']}/{ablation['total']}",
            f"Guard helped: {ablation['guard_helped_count']}",
            f"Guard hurt: {ablation['guard_hurt_count']}",
            "",
            "| Split | Model-only | With guards | Changed | Helped | Hurt |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for split, metrics in ablation["by_split"].items():
        lines.append(
            f"| {split} | {metrics['model_only_passed']}/{metrics['total']} ({metrics['model_only_accuracy']:.0%}) | "
            f"{metrics['with_guards_passed']}/{metrics['total']} ({metrics['with_guards_accuracy']:.0%}) | "
            f"{metrics['guard_changed_count']} | {metrics['guard_helped_count']} | {metrics['guard_hurt_count']} |"
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
            f"Candidate comparisons: {observability['candidate_comparison_count_total']}",
            f"Total candidate count: {observability['candidate_count_total']}",
            f"Lexical candidates: {observability['lexical_candidate_count_total']}",
            f"Anchor-rescued candidates: {observability['anchor_candidate_count_total']}",
            f"Semantic-rescued candidates: {observability['semantic_candidate_count_total']}",
            f"Semantic attempts: {observability['semantic_attempt_count_total']}",
            (
                "Semantic score distribution: "
                f"n={observability['semantic_score_summary']['count']}, "
                f"min={observability['semantic_score_summary']['min']:.2f}, "
                f"median={observability['semantic_score_summary']['median']:.2f}, "
                f"p90={observability['semantic_score_summary']['p90']:.2f}, "
                f"max={observability['semantic_score_summary']['max']:.2f}"
            ),
            f"Embedding errors: {observability['embedding_error_count_total']}",
            f"Same-obligation screen calls: {observability['same_obligation_screen_count_total']}",
            f"Same-obligation screen passes: {observability['same_obligation_screen_pass_count_total']}",
            f"Same-obligation screen rejects: {observability['same_obligation_screen_reject_count_total']}",
            f"Same-obligation screen errors: {observability['same_obligation_screen_error_count_total']}",
            f"Same-obligation screen fallback-to-primary calls: {observability['same_obligation_screen_fallback_count_total']}",
            f"Same-obligation screen polarity overrides: {observability['same_obligation_screen_override_count_total']}",
            f"Same-obligation screen latency: {observability['same_obligation_screen_latency_seconds_total']:.1f}s",
            f"Total adjudication calls: {observability['adjudication_count_total']}",
            f"No-candidate not-related resolutions: {observability['no_candidate_not_related_count_total']}",
            f"Rejected candidate findings retained: {observability['rejected_candidate_finding_count_total']}",
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

    lines.extend(["", "### Same-Obligation Screen Errors", "", "| Error | Count |", "|---|---:|"])
    if observability["same_obligation_screen_errors"]:
        for error, count in observability["same_obligation_screen_errors"].items():
            lines.append(f"| {error} | {count} |")
    else:
        lines.append("| none | 0 |")

    lines.extend(["", "### No-Candidate Resolutions", "", "| Resolution | Count |", "|---|---:|"])
    if observability["no_candidate_resolutions"]:
        for resolution, count in observability["no_candidate_resolutions"].items():
            lines.append(f"| {resolution} | {count} |")
    else:
        lines.append("| none | 0 |")

    lines.extend(["", "### Decision Classes", "", "| Decision class | Model | Final | Accepted | Rejected |", "|---|---:|---:|---:|---:|"])
    decision_counts = observability["decision_class_counts"]
    class_names = sorted(
        set(decision_counts["model"])
        | set(decision_counts["final"])
        | set(decision_counts["accepted"])
        | set(decision_counts["rejected"])
    )
    if class_names:
        for class_name in class_names:
            lines.append(
                f"| {class_name} | {decision_counts['model'].get(class_name, 0)} | "
                f"{decision_counts['final'].get(class_name, 0)} | "
                f"{decision_counts['accepted'].get(class_name, 0)} | "
                f"{decision_counts['rejected'].get(class_name, 0)} |"
            )
    else:
        lines.append("| none | 0 | 0 | 0 | 0 |")

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
            (
                "| Run | ID | Split | Domain | Expected | Model-only | Actual | Pass | Guard | LLM | Candidates | Screen | "
                "Candidate sources | Max semantic | Resolution/Gate | Latency |"
            ),
            "|---:|---|---|---|---|---|---|:--:|:--:|:--:|---:|---:|---|---:|---|---:|",
        ]
    )
    for row in report["rows"]:
        mark = "PASS" if row["passed"] else "FAIL"
        guard_mark = "yes" if row["guard_changed_classification"] else "no"
        llm_mark = "yes" if row["llm_called"] else "no"
        gate_reason = row["gate_demotion_reason"] or row["no_candidate_resolution"] or row["no_alignment_reason"] or ""
        sources = f"L{row['lexical_candidate_count']}/A{row['anchor_candidate_count']}/S{row['semantic_candidate_count']}"
        lines.append(
            f"| {row['run']} | {row['id']} | {row['split']} | {row['domain']} | {row['expected']} | "
            f"{row['model_only_actual']} | {row['actual']} | {mark} | {guard_mark} | {llm_mark} | {row['candidate_count']} | "
            f"{row['same_obligation_screen_count']} | {sources} | {row['max_semantic_score']:.2f} | "
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
    depth_generators = {depth: generator}
    depth_model_names = {depth: model_name}
    if depth == "deep":
        balanced_model = os.environ.get("KP_COMPLIANCE_BALANCED_LLM_MODEL", "deepseek-r1:8b")
        balanced_generator = OllamaComplianceGenerator(
            base_url=os.environ.get("KP_OLLAMA_URL", "http://127.0.0.1:11434"),
            model=balanced_model,
            num_ctx=int(os.environ.get("KP_COMPLIANCE_BALANCED_LLM_NUM_CTX", "4096")),
            timeout=float(os.environ.get("KP_COMPLIANCE_BALANCED_LLM_TIMEOUT", os.environ.get("KP_COMPLIANCE_LLM_TIMEOUT", "120"))),
        )
        depth_generators["balanced"] = balanced_generator
        depth_model_names["balanced"] = balanced_model
    embedder = _embedder_from_env()
    return AgenticComplianceEngine(
        generator=generator,
        model_name=model_name,
        depth_generators=depth_generators,
        depth_model_names=depth_model_names,
        embedder=embedder,
        min_semantic_candidate_score=_semantic_candidate_threshold(),
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
        depth_generators={depth: generator, "balanced": generator},
        depth_model_names={depth: "scripted-fake", "balanced": "scripted-fake"},
    )


def _embedder_from_env() -> OllamaComplianceEmbedder | None:
    enabled = os.environ.get("KP_COMPLIANCE_EMBEDDINGS_ENABLED", "1").strip().lower() in {"1", "true", "yes", "on"}
    if not enabled:
        return None
    return OllamaComplianceEmbedder(
        base_url=os.environ.get("KP_OLLAMA_URL", "http://127.0.0.1:11434"),
        model=os.environ.get("KP_COMPLIANCE_EMBED_MODEL", os.environ.get("KP_EMBED_MODEL", "nomic-embed-text")),
        timeout=float(os.environ.get("KP_COMPLIANCE_EMBED_TIMEOUT", "30")),
    )


def _semantic_candidate_threshold() -> float:
    return float(os.environ.get("KP_COMPLIANCE_SEMANTIC_CANDIDATE_SCORE", "0.58"))


def _request_for_label(
    label: ComplianceReasoningLabel,
    *,
    depth: ReviewDepth,
    throttle_deep: bool,
    disable_safety_gates: bool,
) -> ComplianceReviewRequest:
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
            disable_safety_gates=disable_safety_gates,
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


def _model_only_classification(diagnostics: dict[str, Any], *, fallback_actual: str) -> str:
    model_decisions = [str(item) for item in diagnostics.get("model_decision_classifications", []) if str(item).strip()]
    if model_decisions:
        return model_decisions[0]

    resolutions = [str(item) for item in diagnostics.get("no_candidate_resolutions", []) if str(item).strip()]
    resolution = resolutions[0] if resolutions else str(diagnostics.get("no_candidate_resolution", ""))
    if "not_related" in resolution:
        return "not_related"
    if "missing_obligation" in resolution or int(diagnostics.get("missing_obligation_fallback_count", 0)) > 0:
        return "missing_obligation"
    return fallback_actual


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
    disable_safety_gates: bool,
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
            "disable_safety_gates": disable_safety_gates,
            "semantic_candidate_threshold": _semantic_candidate_threshold(),
        },
        "classes": classes,
        "per_class": per_class,
        "split_metrics": _split_metrics(rows, classes),
        "ablation": _ablation_summary(rows, classes),
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


def _split_metrics(rows: list[dict[str, Any]], classes: list[str]) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for split in _ordered_splits(rows):
        split_rows = [row for row in rows if row.get("split", "training") == split]
        passed = sum(1 for row in split_rows if row.get("passed"))
        matrix = (
            _confusion_matrix(split_rows, classes)
            if split_rows
            else {class_name: {actual: 0 for actual in classes} for class_name in classes}
        )
        metrics[split] = {
            "total": len(split_rows),
            "passed": passed,
            "accuracy": round(passed / len(split_rows), 3) if split_rows else 0.0,
            "per_class": _per_class_metrics(matrix, classes),
            "observability": _observability_summary(split_rows, classes) if split_rows else _empty_observability(classes),
        }
    return metrics


def _ablation_summary(rows: list[dict[str, Any]], classes: list[str]) -> dict[str, Any]:
    overall = _ablation_counts(rows)
    model_only_rows = [
        {
            **row,
            "actual": row.get("model_only_actual", row.get("actual")),
            "passed": row.get("model_only_passed", row.get("passed")),
        }
        for row in rows
    ]
    overall["model_only_confusion_matrix"] = _confusion_matrix(model_only_rows, classes)
    overall["model_only_per_class"] = _per_class_metrics(overall["model_only_confusion_matrix"], classes)
    overall["by_split"] = {
        split: _ablation_counts([row for row in rows if row.get("split", "training") == split])
        for split in _ordered_splits(rows)
    }
    return overall


def _ablation_counts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    model_only_passed = sum(1 for row in rows if row.get("model_only_passed"))
    with_guards_passed = sum(1 for row in rows if row.get("passed"))
    changed_rows = [row for row in rows if row.get("guard_changed_classification")]
    helped = sum(1 for row in changed_rows if not row.get("model_only_passed") and row.get("passed"))
    hurt = sum(1 for row in changed_rows if row.get("model_only_passed") and not row.get("passed"))
    neutral = len(changed_rows) - helped - hurt
    return {
        "total": total,
        "model_only_passed": model_only_passed,
        "model_only_accuracy": round(model_only_passed / total, 3) if total else 0.0,
        "with_guards_passed": with_guards_passed,
        "with_guards_accuracy": round(with_guards_passed / total, 3) if total else 0.0,
        "guard_changed_count": len(changed_rows),
        "guard_changed_rate": round(len(changed_rows) / total, 3) if total else 0.0,
        "guard_helped_count": helped,
        "guard_hurt_count": hurt,
        "guard_neutral_count": neutral,
    }


def _ordered_splits(rows: list[dict[str, Any]]) -> list[str]:
    seen = {str(row.get("split", "training")) for row in rows if str(row.get("split", "training")).strip()}
    priority = ["training", "in_domain", "holdout"]
    return [split for split in priority if split in seen] + sorted(seen.difference(priority))


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
    no_candidate_resolution_counts = Counter(
        resolution
        for row in rows
        for resolution in row.get("no_candidate_resolutions", [])
        if str(resolution).strip()
    )
    screen_error_counts = Counter(
        error
        for row in rows
        for error in row.get("same_obligation_screen_errors", [])
        if str(error).strip()
    )
    semantic_scores = [float(row.get("max_semantic_score", 0.0)) for row in rows if int(row.get("semantic_attempt_count", 0)) > 0]
    return {
        "total_rows": total_rows,
        "llm_called_rows": llm_called_rows,
        "never_adjudicated_rows": total_rows - llm_called_rows,
        "adjudicator_coverage": round(llm_called_rows / total_rows, 3) if total_rows else 0.0,
        "candidate_count_total": sum(int(row.get("candidate_count", 0)) for row in rows),
        "candidate_comparison_count_total": sum(int(row.get("candidate_comparison_count", 0)) for row in rows),
        "lexical_candidate_count_total": sum(int(row.get("lexical_candidate_count", 0)) for row in rows),
        "anchor_candidate_count_total": sum(int(row.get("anchor_candidate_count", 0)) for row in rows),
        "semantic_candidate_count_total": sum(int(row.get("semantic_candidate_count", 0)) for row in rows),
        "semantic_attempt_count_total": sum(int(row.get("semantic_attempt_count", 0)) for row in rows),
        "semantic_score_summary": _score_summary(semantic_scores),
        "max_semantic_score": round(max(semantic_scores), 3) if semantic_scores else 0.0,
        "max_alignment_score": round(max((float(row.get("max_alignment_score", 0.0)) for row in rows), default=0.0), 3),
        "embedding_error_count_total": sum(int(row.get("embedding_error_count", 0)) for row in rows),
        "same_obligation_screen_count_total": sum(int(row.get("same_obligation_screen_count", 0)) for row in rows),
        "same_obligation_screen_pass_count_total": sum(int(row.get("same_obligation_screen_pass_count", 0)) for row in rows),
        "same_obligation_screen_reject_count_total": sum(int(row.get("same_obligation_screen_reject_count", 0)) for row in rows),
        "same_obligation_screen_error_count_total": sum(int(row.get("same_obligation_screen_error_count", 0)) for row in rows),
        "same_obligation_screen_fallback_count_total": sum(
            int(row.get("same_obligation_screen_fallback_count", 0)) for row in rows
        ),
        "same_obligation_screen_override_count_total": sum(
            int(row.get("same_obligation_screen_override_count", 0)) for row in rows
        ),
        "same_obligation_screen_latency_seconds_total": round(
            sum(float(row.get("same_obligation_screen_latency_seconds", 0.0)) for row in rows),
            3,
        ),
        "same_obligation_screen_errors": dict(screen_error_counts),
        "adjudication_count_total": sum(int(row.get("adjudication_count", 0)) for row in rows),
        "fallback_decision_count_total": sum(int(row.get("fallback_decision_count", 0)) for row in rows),
        "missing_obligation_fallback_count_total": sum(int(row.get("missing_obligation_fallback_count", 0)) for row in rows),
        "no_candidate_not_related_count_total": sum(int(row.get("no_candidate_not_related_count", 0)) for row in rows),
        "rejected_candidate_finding_count_total": sum(int(row.get("rejected_candidate_finding_count", 0)) for row in rows),
        "never_adjudicated_by_expected": never_adjudicated_by_expected,
        "no_candidate_resolutions": dict(no_candidate_resolution_counts),
        "gate_demotion_reasons": dict(gate_reason_counts),
        "decision_class_counts": {
            "model": _classification_counter(rows, "model_decision_classifications"),
            "final": _classification_counter(rows, "final_decision_classifications"),
            "accepted": _classification_counter(rows, "accepted_decision_classifications"),
            "rejected": _classification_counter(rows, "rejected_decision_classifications"),
        },
    }


def _empty_observability(classes: list[str]) -> dict[str, Any]:
    return {
        "total_rows": 0,
        "llm_called_rows": 0,
        "never_adjudicated_rows": 0,
        "adjudicator_coverage": 0.0,
        "candidate_count_total": 0,
        "candidate_comparison_count_total": 0,
        "lexical_candidate_count_total": 0,
        "anchor_candidate_count_total": 0,
        "semantic_candidate_count_total": 0,
        "semantic_attempt_count_total": 0,
        "semantic_score_summary": {"count": 0, "min": 0.0, "median": 0.0, "p90": 0.0, "max": 0.0},
        "max_semantic_score": 0.0,
        "max_alignment_score": 0.0,
        "embedding_error_count_total": 0,
        "same_obligation_screen_count_total": 0,
        "same_obligation_screen_pass_count_total": 0,
        "same_obligation_screen_reject_count_total": 0,
        "same_obligation_screen_error_count_total": 0,
        "same_obligation_screen_fallback_count_total": 0,
        "same_obligation_screen_override_count_total": 0,
        "same_obligation_screen_latency_seconds_total": 0.0,
        "same_obligation_screen_errors": {},
        "adjudication_count_total": 0,
        "fallback_decision_count_total": 0,
        "missing_obligation_fallback_count_total": 0,
        "no_candidate_not_related_count_total": 0,
        "rejected_candidate_finding_count_total": 0,
        "never_adjudicated_by_expected": {class_name: 0 for class_name in classes},
        "no_candidate_resolutions": {},
        "gate_demotion_reasons": {},
        "decision_class_counts": {"model": {}, "final": {}, "accepted": {}, "rejected": {}},
    }


def _score_summary(values: list[float]) -> dict[str, float | int]:
    if not values:
        return {"count": 0, "min": 0.0, "median": 0.0, "p90": 0.0, "max": 0.0}
    sorted_values = sorted(values)
    return {
        "count": len(sorted_values),
        "min": round(sorted_values[0], 3),
        "median": round(statistics.median(sorted_values), 3),
        "p90": round(_percentile(sorted_values, 0.9), 3),
        "max": round(sorted_values[-1], 3),
    }


def _classification_counter(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(Counter(str(item) for row in rows for item in row.get(key, []) if str(item).strip()))


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
    seen.update(str(row.get("model_only_actual", "")) for row in rows if str(row.get("model_only_actual", "")).strip())
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
