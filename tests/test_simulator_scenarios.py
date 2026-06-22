"""Validation for the synthetic persona simulator scenario catalogue."""

from __future__ import annotations

import json
import re
from pathlib import Path

SCENARIOS = Path("docs/benchmark/simulator-scenarios.json")
REQUIRED_PERSONA_TYPES = {
    "new starter",
    "vendor/partner",
    "process owner",
    "site operator",
    "compliance reviewer",
    "project/product manager",
}
VALID_BEHAVIOURS = {"answer", "decline", "refuse", "guardrail"}
VALID_DIFFICULTIES = {"basic", "intermediate", "advanced"}


def _catalogue() -> dict:
    return json.loads(SCENARIOS.read_text())


def test_simulator_catalogue_covers_required_personas_and_process_areas():
    catalogue = _catalogue()
    personas = catalogue["personas"]
    scenarios = catalogue["scenarios"]

    assert catalogue["schema_version"] == "1.0"
    assert catalogue["safety"]["data_classification"] == "synthetic"
    assert len(personas) >= 6
    assert {persona["persona_type"] for persona in personas} >= REQUIRED_PERSONA_TYPES
    assert len({scenario["process_area"] for scenario in scenarios}) >= 4


def test_each_simulator_scenario_has_reusable_metadata_and_questions():
    catalogue = _catalogue()
    persona_ids = {persona["persona_id"] for persona in catalogue["personas"]}

    question_ids: set[str] = set()
    for scenario in catalogue["scenarios"]:
        assert scenario["persona_id"] in persona_ids
        assert scenario["scenario_id"].startswith("sim-")
        assert scenario["journey"]
        assert scenario["intent"]
        assert scenario["process_area"]
        assert scenario["value_driver"]
        assert scenario["difficulty"] in VALID_DIFFICULTIES
        assert scenario["expected_outcome"]
        assert scenario["expected_evidence"]
        assert len(scenario["success_criteria"]) >= 2
        assert len(scenario["questions"]) >= 3

        for question in scenario["questions"]:
            assert question["question_id"].startswith("sim-q")
            assert question["question_id"] not in question_ids
            question_ids.add(question["question_id"])
            assert question["text"].endswith("?")
            assert question["expected_behavior"] in VALID_BEHAVIOURS
            assert question["expected_signal"]


def test_simulator_catalogue_exercises_boundaries_as_well_as_answer_paths():
    behaviours = {
        question["expected_behavior"]
        for scenario in _catalogue()["scenarios"]
        for question in scenario["questions"]
    }

    assert {"answer", "decline", "refuse", "guardrail"} <= behaviours


def test_simulator_catalogue_avoids_obvious_confidential_red_flags():
    text = SCENARIOS.read_text()

    assert not re.search(r"@|password|secret|token|api[_-]?key", text, re.I)
    assert not re.search(r"\b\d{6,}\b", text)
