"""Per-metric computation traces for analytics headline numbers."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .export import AnalyticsExportContext
from .knowledge_gaps import build_gap_clusters
from .log import build_scorecard
from .process_complexity import build_process_complexity


class ComputationTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_id: str
    label: str
    method_id: str
    formula: str
    substituted_formula: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    intermediate_steps: list[str] = Field(default_factory=list)
    output: dict[str, Any] = Field(default_factory=dict)
    boundary: str


class ComputationTraceReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trace_count: int
    traces: list[ComputationTrace]


def build_computation_traces(context: AnalyticsExportContext) -> ComputationTraceReport:
    usage_entries = context.usage_log.entries()
    records = []
    if context.process_registry is not None:
        records = (
            context.process_registry.derive_from_sources(context.register)
            if context.register is not None
            else context.process_registry.list()
        )

    traces = [
        _coverage_trace(build_scorecard(usage_entries)),
        _silhouette_trace(build_gap_clusters(usage_entries)),
        _complexity_trace(build_process_complexity(records)),
    ]
    return ComputationTraceReport(trace_count=len(traces), traces=traces)


def find_computation_trace(context: AnalyticsExportContext, metric_id: str) -> ComputationTrace | None:
    for trace in build_computation_traces(context).traces:
        if trace.metric_id == metric_id:
            return trace
    return None


def _coverage_trace(scorecard: dict) -> ComputationTrace:
    total = int(scorecard.get("total_queries", 0))
    answered = int(scorecard.get("answered", 0))
    grounded = round(float(scorecard.get("grounded_rate", 0)) * total)
    answer_rate = float(scorecard.get("answer_rate", 0))
    grounded_rate = float(scorecard.get("grounded_rate", 0))
    return ComputationTrace(
        metric_id="coverage_score",
        label="Coverage and grounding scorecard",
        method_id="coverage_score",
        formula="answer_rate = answered / total; grounded_rate = grounded_answered / total",
        substituted_formula=f"answer_rate = {answered} / {total}; grounded_rate = {grounded} / {total}",
        inputs={"total_queries": total, "answered": answered, "grounded_answered": grounded},
        intermediate_steps=[
            f"answered = {answered}",
            f"total = {total}",
            f"answer_rate = {answer_rate}",
            f"grounded_rate = {grounded_rate}",
        ],
        output={"answer_rate": answer_rate, "grounded_rate": grounded_rate},
        boundary="Coverage is a usage-quality signal, not proof that every answer was semantically correct.",
    )


def _silhouette_trace(gaps: dict) -> ComputationTrace:
    total_candidates = int(gaps.get("total_candidates", 0))
    cluster_count = int(gaps.get("cluster_count", 0))
    silhouette = float(gaps.get("silhouette_score", 0))
    return ComputationTrace(
        metric_id="knowledge_gap_silhouette",
        label="Knowledge-gap silhouette score",
        method_id="knowledge_gap_clustering",
        formula="silhouette = mean((nearest_other_topic_distance - same_topic_distance) / max(same, nearest_other))",
        substituted_formula=f"silhouette = {silhouette} over {total_candidates} candidates and {cluster_count} clusters",
        inputs={"total_candidates": total_candidates, "cluster_count": cluster_count},
        intermediate_steps=[
            "Build refused/weak-evidence candidates from usage_log.",
            "Tokenise each candidate and calculate deterministic token-set distances.",
            f"Reported silhouette score = {silhouette}.",
        ],
        output={"silhouette_score": silhouette},
        boundary="Silhouette is a clustering-quality indicator; low data volume or similar wording can make it unstable.",
    )


def _complexity_trace(complexity: dict) -> ComputationTrace:
    processes = complexity.get("processes", [])
    top = processes[0] if processes else {}
    output = {
        "average_complexity": complexity.get("average_complexity", 0),
        "process_count": complexity.get("process_count", 0),
        "top_process": top.get("name", ""),
        "top_complexity_score": top.get("complexity_score", 0),
        "top_key_person_risk_score": top.get("key_person_risk_score", 0),
    }
    signals = {key.removeprefix("signals."): value for key, value in top.items() if key.startswith("signals.")}
    if not signals and isinstance(top.get("signals"), dict):
        signals = top["signals"]
    return ComputationTrace(
        metric_id="process_complexity",
        label="Process complexity and key-person-risk trace",
        method_id="process_complexity_index",
        formula="complexity = min(100, roles*7 + systems*9 + dependencies*10 + controls*5 + handoffs*7 + exceptions*8 + rules*3)",
        substituted_formula=(
            "complexity = "
            f"min(100, {signals.get('roles', 0)}*7 + {signals.get('systems', 0)}*9 + "
            f"{signals.get('dependencies', 0)}*10 + {signals.get('controls', 0)}*5 + "
            f"{signals.get('handoffs', 0)}*7 + {signals.get('exception_terms', 0)}*8 + "
            f"{signals.get('rules', 0)}*3)"
        ),
        inputs={"top_process_signals": signals, "process_count": complexity.get("process_count", 0)},
        intermediate_steps=[
            f"Process count = {complexity.get('process_count', 0)}.",
            f"Average complexity = {complexity.get('average_complexity', 0)}.",
            f"Top process = {top.get('name', 'n/a')}.",
        ],
        output=output,
        boundary="Process scores are deterministic triage indicators, not operational risk proof.",
    )
