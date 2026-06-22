"""Checks for the industry decision-rationale evidence pack."""

from __future__ import annotations

from pathlib import Path

RATIONALE = Path("docs/evidence/industry-decision-rationale.md")
DECISION_LOG = Path("exports/wiki/pages/Delivery-Management__Decision-Log.md")


def test_industry_decision_rationale_covers_required_sources():
    text = RATIONALE.read_text()

    for source in ["eGain", "Graphwise", "Glean", "LlamaIndex", "Dell"]:
        assert source in text

    for url in [
        "https://www.egain.com/ai-knowledge-hub/",
        "https://graphwise.ai/",
        "https://www.glean.com/",
        "https://developers.llamaindex.ai/python/framework/understanding/rag/loading/",
        "https://developers.llamaindex.ai/python/framework/understanding/evaluating/evaluating/",
        "https://www.itpro.com/technology/artificial-intelligence/dell-technologies-cto-john-roese-ai-agents",
    ]:
        assert url in text


def test_industry_decision_rationale_has_accepted_decision_entries():
    text = RATIONALE.read_text()

    for decision_id in ["DEC-008", "DEC-009", "DEC-010", "DEC-011", "DEC-012"]:
        row = next(line for line in text.splitlines() if line.startswith(f"| {decision_id} |"))
        assert "2026-06-22" in row
        assert row.endswith("| Accepted |")


def test_exported_decision_log_includes_industry_entries():
    text = DECISION_LOG.read_text()

    for phrase in [
        "Treat knowledge hygiene as a product capability",
        "Model process knowledge as structured semantic assets",
        "Require permission-aware, cited retrieval for answers",
        "Measure ingestion and answer quality explicitly",
        "Keep agentic and voice channels behind the canonical validated answer flow",
    ]:
        assert phrase in text
