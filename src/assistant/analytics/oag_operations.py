"""Live OAG operations analytics from real usage telemetry."""

from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from datetime import datetime
from hashlib import sha1
from typing import Any

from .classify import classify_topic
from .forecast import forecast_series
from .log import UsageEntry


def build_oag_operations_report(usage_entries: list[UsageEntry], traces: list[dict[str, Any]]) -> dict[str, Any]:
    answered = [entry for entry in usage_entries if not entry.refused]
    path_counts = Counter(entry.answer_path or "unknown" for entry in usage_entries)
    answer_count = len(answered)
    deterministic_values = [entry.deterministic_evidence_ratio for entry in answered if entry.citation_count > 0]
    generative_values = [entry.generative_evidence_ratio for entry in answered if entry.citation_count > 0]
    ontology_cited = sum(1 for entry in answered if entry.citation_type_counts.get("ontology_object", 0) > 0)
    daily_path = _daily_path_rows(usage_entries)
    oag_points = [{"date": row["date"], "value": row["oag"] + row["rag_ontology"]} for row in daily_path]
    oag_forecast = forecast_series(oag_points, horizon=7)
    return {
        "summary": {
            "total_queries": len(usage_entries),
            "answered_queries": answer_count,
            "path_counts": dict(path_counts),
            "oag_assisted_count": path_counts.get("oag", 0) + path_counts.get("rag+ontology", 0),
            "rag_fallback_count": path_counts.get("rag", 0),
            "deterministic_evidence_ratio": round(statistics.mean(deterministic_values), 3) if deterministic_values else 0.0,
            "generative_evidence_ratio": round(statistics.mean(generative_values), 3) if generative_values else 0.0,
            "ontology_object_citation_rate": round(ontology_cited / answer_count, 3) if answer_count else 0.0,
        },
        "daily_path_split": daily_path,
        "oag_adoption_forecast": {
            "series_id": "oag_adoption",
            "label": "OAG-assisted answers",
            "bucket": "day",
            "actuals": oag_points,
            "statistics": {"point_count": len(oag_points)},
            "method_id": "forecasting",
            **oag_forecast,
        },
        "path_grounding_matrix": _path_grounding_matrix(usage_entries),
        "latency_by_path": _latency_by_path(traces),
        "coverage_gaps": _coverage_gaps(usage_entries),
        "boundary": (
            "Live OAG operations are based on local usage/audit telemetry. RAG fallback is a coverage signal "
            "for review, not proof that ontology content is wrong or incomplete."
        ),
    }


def _daily_path_rows(entries: list[UsageEntry]) -> list[dict[str, Any]]:
    rows: dict[str, Counter[str]] = defaultdict(Counter)
    for entry in entries:
        day = _day(entry.timestamp)
        path = entry.answer_path if entry.answer_path in {"oag", "rag", "rag+ontology"} else "other"
        rows[day][path] += 1
    return [
        {
            "date": day,
            "oag": counts.get("oag", 0),
            "rag": counts.get("rag", 0),
            "rag_ontology": counts.get("rag+ontology", 0),
            "other": counts.get("other", 0),
            "total": sum(counts.values()),
        }
        for day, counts in sorted(rows.items())
    ]


def _path_grounding_matrix(entries: list[UsageEntry]) -> list[dict[str, Any]]:
    matrix: dict[str, Counter[str]] = defaultdict(Counter)
    for entry in entries:
        path = entry.answer_path if entry.answer_path in {"oag", "rag", "rag+ontology"} else "other"
        if entry.refused:
            bucket = "refused"
        elif entry.confidence == "grounded":
            bucket = "grounded"
        elif entry.confidence == "unverified":
            bucket = "unverified"
        else:
            bucket = "none"
        matrix[path][bucket] += 1
    return [
        {
            "answer_path": path,
            "grounded": counts.get("grounded", 0),
            "unverified": counts.get("unverified", 0),
            "refused": counts.get("refused", 0),
            "none": counts.get("none", 0),
            "total": sum(counts.values()),
        }
        for path, counts in sorted(matrix.items())
    ]


def _latency_by_path(traces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values: dict[str, list[float]] = defaultdict(list)
    for trace in traces:
        path = str(trace.get("answer_path") or "unknown")
        latency = trace.get("latency_ms")
        if isinstance(latency, (int, float)):
            values[path].append(float(latency))
    return [
        {
            "answer_path": path,
            "count": len(latencies),
            "mean_ms": round(statistics.mean(latencies), 1),
            "p95_ms": round(_percentile(latencies, 0.95), 1),
        }
        for path, latencies in sorted(values.items())
        if latencies
    ]


def _coverage_gaps(entries: list[UsageEntry]) -> list[dict[str, Any]]:
    gaps = []
    seen: set[str] = set()
    for entry in reversed(entries):
        key = entry.question.strip().lower()
        if not key or key in seen:
            continue
        if entry.answer_path != "rag" or entry.refused:
            continue
        seen.add(key)
        topic = classify_topic(entry.question)
        gaps.append(
            {
                "gap_id": f"oag-coverage-{len(gaps) + 1}",
                "question": entry.question.strip(),
                "timestamp": entry.timestamp,
                "topic": topic,
                "reason": "Answered by RAG with no OAG or hybrid path; review whether an ontology object/link should cover it.",
                "trigger_ref": f"oag-coverage:{topic}:{sha1(key.encode()).hexdigest()[:10]}",
                "suggested_owner_role": "knowledge steward",
                "eam_gap_ref": f"eam-gap:{topic}",
            }
        )
    return gaps[:20]


def _day(timestamp: str) -> str:
    try:
        return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return timestamp[:10] or "unknown"


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * percentile))))
    return float(ordered[index])
