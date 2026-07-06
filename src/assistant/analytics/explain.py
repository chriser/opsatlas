"""Per-metric computation traces for analytics headline numbers."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..value.ledger import build_value_report
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
    events = context.event_store.events() if context.event_store is not None else []
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
        _value_dcf_trace(build_value_report(events).model_dump()),
        _value_forecast_trace(build_value_report(events).model_dump()),
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


def _value_dcf_trace(value: dict) -> ComputationTrace:
    active_metric = _active_value_metric(value)
    active_scenario = active_metric.get("scenario_id", value.get("active_scenario_id", "base"))
    assumptions = _scenario_assumptions(value, active_scenario)
    discount_rate = float(assumptions.get("discount_rate", 0))
    capex = float(active_metric.get("one_off_capex_gbp", 0))
    annual_net = float(active_metric.get("net_annual_benefit_gbp", 0))
    horizon_years = int(active_metric.get("horizon_years", 0))
    npv = float(active_metric.get("npv_gbp", 0))
    irr = active_metric.get("irr")
    cashflows = [-capex, *([annual_net] * horizon_years)]
    return ComputationTrace(
        metric_id="value_dcf",
        label="Value model NPV, IRR and payback",
        method_id="value_dcf",
        formula="npv = -capex + sum(annual_net / (1 + discount_rate)^year)",
        substituted_formula=f"npv = -{capex} + sum({annual_net} / (1 + {discount_rate})^year) for {horizon_years} years",
        inputs={
            "scenario_id": active_scenario,
            "capex": capex,
            "annual_net": annual_net,
            "discount_rate": discount_rate,
            "horizon_years": horizon_years,
            "cashflows": cashflows,
        },
        intermediate_steps=[
            f"Gross annual benefit = {active_metric.get('gross_annual_benefit_gbp', 0)}.",
            f"Net annual benefit = {annual_net}.",
            f"Simple payback = {active_metric.get('simple_payback_years')}.",
            f"NPV = {npv}.",
            f"IRR = {irr}.",
        ],
        output={"npv_gbp": npv, "irr": irr, "simple_payback_years": active_metric.get("simple_payback_years")},
        boundary="Value outputs are assumptions-led until validated with live enterprise telemetry.",
    )


def _value_forecast_trace(value: dict) -> ComputationTrace:
    telemetry = value.get("telemetry", {})
    projection = telemetry.get("projection", {})
    monthly_trend = telemetry.get("monthly_trend", [])
    dated_months = [row for row in monthly_trend if row.get("month") != "unknown"]
    combined_total = round(sum(float(row.get("total_gbp", 0)) for row in dated_months), 2)
    month_count = len(dated_months)
    output = float(projection.get("combined_ytd_projection_gbp", 0))
    return ComputationTrace(
        metric_id="value_forecast_projection",
        label="Combined annualised value projection",
        method_id="value_dcf",
        formula="combined_ytd_projection = (dated_month_value_total / dated_month_count) * 12",
        substituted_formula=f"combined_ytd_projection = ({combined_total} / {month_count}) * 12",
        inputs={"dated_month_value_total": combined_total, "dated_month_count": month_count},
        intermediate_steps=[
            f"Dated months with value events = {month_count}.",
            f"Combined dated month value = {combined_total}.",
            f"Annualised projection = {output}.",
        ],
        output={"combined_ytd_projection_gbp": output},
        boundary="Projection annualises observed/synthetic event months and is not a guaranteed forecast.",
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


def _active_value_metric(value: dict) -> dict:
    active = value.get("active_scenario_id", "base")
    for metric in value.get("metrics", []):
        if metric.get("scenario_id") == active:
            return metric
    return value.get("metrics", [{}])[0] if value.get("metrics") else {}


def _scenario_assumptions(value: dict, scenario_id: str) -> dict[str, float]:
    return {
        assumption.get("metric", ""): float(assumption.get("value", 0))
        for assumption in value.get("assumptions", [])
        if assumption.get("scenario_id") == scenario_id
    }
