"""Validation for the hallucination probe dataset."""

from __future__ import annotations

import json
from pathlib import Path

DATASET = Path("tests/evaluation/hallucination_probes.json")
ALLOWED_EXPECTED = {"answer", "refuse", "decline", "guardrail"}
REQUIRED_CATEGORIES = {
    "missing_specific",
    "disclosure",
    "action_request",
    "contradictory_premise",
    "out_of_scope",
    "currentness",
    "prompt_injection",
}


def test_hallucination_probe_dataset_has_required_coverage():
    probes = json.loads(DATASET.read_text())

    assert len(probes) >= 15
    assert len({probe["id"] for probe in probes}) == len(probes)
    assert REQUIRED_CATEGORIES.issubset({probe["category"] for probe in probes})
    assert any(probe["expected"] == "answer" and probe["category"] == "contradictory_premise" for probe in probes)


def test_hallucination_probe_dataset_documents_expected_behaviour():
    probes = json.loads(DATASET.read_text())

    for probe in probes:
        assert probe["id"].startswith("HAL-")
        assert len(probe["question"].strip()) > 20
        assert probe["expected"] in ALLOWED_EXPECTED
        assert len(probe["expected_behavior"]) > 25
        assert len(probe["hallucination_risk"]) > 25
        assert len(probe["source_expectation"]) > 20
