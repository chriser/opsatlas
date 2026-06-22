"""Descriptive analytics chart aggregation tests."""

from assistant.analytics.charts import build_charts
from assistant.analytics.log import UsageEntry


def _e(ts, q, refused=False, category=None, confidence="grounded", cites=2):
    return UsageEntry(
        timestamp=ts, question=q, mode="retrieval", refused=refused,
        category=category, confidence=confidence, citation_count=cites,
    )


def test_build_charts_aggregates_demand_outcomes_and_latency():
    entries = [
        _e("2026-06-21T10:00:00", "how to set up a supplier?"),
        _e("2026-06-21T11:00:00", "what systems are involved?"),
        _e("2026-06-22T09:00:00", "capital of France?", refused=True),
        _e("2026-06-22T09:30:00", "tell me a joke", category="manipulation"),
    ]
    traces = [
        {"latency_ms": 800, "evidence": [{"source_title": "Pack 1"}]},
        {"latency_ms": 3200, "evidence": [{"source_title": "Pack 1"}, {"source_title": "Pack 2"}]},
    ]
    out = build_charts(entries, traces)

    assert [v["date"] for v in out["volume_over_time"]] == ["2026-06-21", "2026-06-22"]
    assert out["volume_over_time"][0]["queries"] == 2
    outcomes = {o["name"]: o["value"] for o in out["outcomes"]}
    assert outcomes == {"Answered": 2, "Refused": 1, "Guardrail": 1}
    latency = {b["bucket"]: b["count"] for b in out["latency"]}
    assert latency["<1s"] == 1 and latency["2-4s"] == 1
    top = {s["source"]: s["citations"] for s in out["top_sources"]}
    assert top["Pack 1"] == 2 and top["Pack 2"] == 1
    assert out["by_topic"]  # topic demand present


def test_build_charts_empty_is_safe():
    out = build_charts([], [])
    assert out["volume_over_time"] == [] and out["top_sources"] == []
