"""Scenario catalogue loading for synthetic pilot simulations."""

from __future__ import annotations

import json
import random
from pathlib import Path

from pydantic import BaseModel, ConfigDict

DEFAULT_CATALOGUE_PATH = Path(__file__).resolve().parents[3] / "docs" / "benchmark" / "simulator-scenarios.json"


class SimulatorPersona(BaseModel):
    model_config = ConfigDict(extra="forbid")

    persona_id: str
    persona_type: str
    display_name: str
    context: str
    primary_needs: list[str]
    constraints: list[str]
    default_value_driver: str


class ScenarioQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str
    text: str
    expected_behavior: str
    expected_signal: str


class SimulatorScenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    persona_id: str
    journey: str
    intent: str
    process_area: str
    value_driver: str
    difficulty: str
    expected_outcome: str
    expected_evidence: list[str]
    success_criteria: list[str]
    questions: list[ScenarioQuestion]


class ScenarioCatalogue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    created_for: str
    purpose: str
    safety: dict
    personas: list[SimulatorPersona]
    scenarios: list[SimulatorScenario]

    def persona_lookup(self) -> dict[str, SimulatorPersona]:
        return {persona.persona_id: persona for persona in self.personas}

    def scenario_lookup(self) -> dict[str, SimulatorScenario]:
        return {scenario.scenario_id: scenario for scenario in self.scenarios}


def load_scenario_catalogue(path: str | Path | None = None) -> ScenarioCatalogue:
    catalogue_path = Path(path) if path is not None else DEFAULT_CATALOGUE_PATH
    return ScenarioCatalogue.model_validate(json.loads(catalogue_path.read_text(encoding="utf-8")))


def select_scenarios(
    catalogue: ScenarioCatalogue,
    scenario_ids: list[str] | None = None,
    persona_ids: list[str] | None = None,
    seed: int | None = None,
) -> list[SimulatorScenario]:
    scenarios = list(catalogue.scenarios)
    if scenario_ids:
        lookup = catalogue.scenario_lookup()
        missing = [scenario_id for scenario_id in scenario_ids if scenario_id not in lookup]
        if missing:
            raise ValueError(f"Unknown scenario id(s): {', '.join(missing)}")
        scenarios = [lookup[scenario_id] for scenario_id in scenario_ids]
    if persona_ids:
        known = set(catalogue.persona_lookup())
        missing = [persona_id for persona_id in persona_ids if persona_id not in known]
        if missing:
            raise ValueError(f"Unknown persona id(s): {', '.join(missing)}")
        allowed = set(persona_ids)
        scenarios = [scenario for scenario in scenarios if scenario.persona_id in allowed]
    if seed is not None:
        scenarios = list(scenarios)
        random.Random(seed).shuffle(scenarios)
    return scenarios
