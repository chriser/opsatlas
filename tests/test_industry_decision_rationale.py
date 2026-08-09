"""Checks for the product-facing industry decision rationale."""

from __future__ import annotations

from pathlib import Path

RATIONALE = Path("docs/architecture/industry-context-and-decisions.md")


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


def test_industry_decisions_are_reflected_in_build_implications():
    text = RATIONALE.read_text()

    for phrase in [
        "Governance analytics should keep showing sources",
        "structured process entities",
        "approved-source, citation and audit path",
        "canonical answer service",
        "ingestion quality, retrieval quality and faithfulness",
    ]:
        assert phrase in text
