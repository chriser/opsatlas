"""Export-safe markdown analytics report builder."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_analytics_report(
    *,
    scorecard: dict,
    history: dict,
    governance: dict,
    gaps: dict,
    complexity: dict,
    value: dict,
    validation: dict,
    generated_at: str | None = None,
) -> str:
    ts = generated_at or datetime.now(timezone.utc).isoformat()
    active_value = _active_value_metric(value)
    lines = [
        "# AI Knowledge and Analytics Assistant - Analytics Evidence Report",
        "",
        f"Generated: `{ts}`",
        "",
        "## Executive Summary",
        "",
        _table(
            ["Metric", "Value"],
            [
                ["Total questions", scorecard.get("total_queries", 0)],
                ["Answer rate", _pct(scorecard.get("answer_rate", 0))],
                ["Grounded rate", _pct(scorecard.get("grounded_rate", 0))],
                ["Open governance issues", governance.get("open_count", 0)],
                ["Knowledge-gap clusters", gaps.get("cluster_count", 0)],
                ["Average process complexity", complexity.get("average_complexity", 0)],
                ["P50 net annual benefit", _gbp(active_value.get("net_annual_benefit_gbp", 0))],
                ["Observed value events", value.get("telemetry", {}).get("event_count", 0)],
                ["Validation protocols", validation.get("summary", {}).get("validation_protocol_count", 0)],
            ],
        ),
        "",
        "## Analytics Method",
        "",
        "- Descriptive analytics: answer volume, answer quality, citations, outcomes and governance lifecycle events.",
        "- Diagnostic analytics: knowledge-gap clusters, process-complexity indicators and recurring governance signals.",
        "- Simulation analytics: synthetic persona replay and regulatory impact triage over approved sources.",
        "- Value analytics: assumptions-led scenarios separated from observed aggregate value events.",
        "- Validation evidence: KSB-style traceability and model/analytics protocol catalogue.",
        "",
        "## Value Scenario",
        "",
        _table(
            ["Scenario", "Gross/year", "Net/year", "Payback", "NPV", "IRR"],
            [
                [
                    active_value.get("label", "n/a"),
                    _gbp(active_value.get("gross_annual_benefit_gbp", 0)),
                    _gbp(active_value.get("net_annual_benefit_gbp", 0)),
                    _years(active_value.get("simple_payback_years")),
                    _gbp(active_value.get("npv_gbp", 0)),
                    _pct(active_value.get("irr")),
                ]
            ],
        ),
        "",
        "## Governance and Gaps",
        "",
        _table(
            ["Signal", "Value"],
            [
                ["Mean time to resolve governance issues", f"{governance.get('mean_time_to_resolve_hours', 0)}h"],
                ["Resolved governance issues", governance.get("resolved_count", 0)],
                ["Open governance issues", governance.get("open_count", 0)],
                ["Knowledge-gap candidates", gaps.get("total_candidates", 0)],
                ["Knowledge-gap cluster quality (silhouette, -1..1)", _coef(gaps.get("silhouette_score"))],
            ],
        ),
        "",
        "## Top Knowledge-Gap Clusters",
        "",
        _table(
            ["Cluster", "Process area", "Questions", "Friction"],
            [
                [
                    cluster.get("label", ""),
                    cluster.get("process_area", ""),
                    cluster.get("question_count", 0),
                    cluster.get("friction_score", 0),
                ]
                for cluster in gaps.get("clusters", [])[:6]
            ],
        ),
        "",
        "## Process Complexity",
        "",
        _table(
            ["Process", "Complexity", "Key-person risk", "Indicator"],
            [
                [
                    process.get("name", ""),
                    f"{process.get('complexity_score', 0)} ({process.get('complexity_band', 'n/a')})",
                    f"{process.get('key_person_risk_score', 0)} ({process.get('key_person_risk_band', 'n/a')})",
                    "; ".join(process.get("indicators", [])[:2]),
                ]
                for process in complexity.get("processes", [])[:8]
            ],
        ),
        "",
        "## Validation Protocols",
        "",
        _table(
            ["Protocol", "Component", "Status", "Boundary"],
            [
                [
                    protocol.get("protocol_id", ""),
                    protocol.get("component", ""),
                    protocol.get("status", ""),
                    protocol.get("boundary", ""),
                ]
                for protocol in validation.get("validation_protocols", [])
            ],
        ),
        "",
        "## Evidence Caveats",
        "",
        *[f"- {caveat}" for caveat in validation.get("caveats", [])],
        "- Export intentionally avoids raw source text, generated answers and full prompt/answer traces.",
    ]
    return "\n".join(lines).strip() + "\n"


def _active_value_metric(value: dict) -> dict:
    active = value.get("active_scenario_id", "base")
    for metric in value.get("metrics", []):
        if metric.get("scenario_id") == active:
            return metric
    return value.get("metrics", [{}])[0] if value.get("metrics") else {}


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    if not rows:
        rows = [["n/a" for _ in headers]]
    output = [
        "| " + " | ".join(_cell(header) for header in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        padded = [*row, *([""] * max(0, len(headers) - len(row)))]
        output.append("| " + " | ".join(_cell(value) for value in padded[: len(headers)]) + " |")
    return "\n".join(output)


def _cell(value: Any) -> str:
    return str(value).replace("|", "/").replace("\n", " ").strip()


def _pct(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{round(float(value) * 100)}%"


def _coef(value: Any) -> str:
    # A unitless coefficient (e.g. silhouette score) — render as-is, not as a percentage.
    if value is None:
        return "n/a"
    return f"{float(value):.2f}"


def _gbp(value: Any) -> str:
    amount = float(value or 0)
    if abs(amount) >= 1_000_000:
        return f"GBP {amount / 1_000_000:.1f}m"
    if abs(amount) >= 1_000:
        return f"GBP {round(amount / 1_000)}k"
    return f"GBP {round(amount)}"


def _years(value: Any) -> str:
    return "n/a" if value is None else f"{value} years"
