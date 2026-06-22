"""Execute synthetic persona scenarios through the normal assistant path."""

from __future__ import annotations

import json
import random
import threading
import time
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from ..analytics.event_store import AnalyticsEventStore
from ..analytics.log import now_iso
from ..answer.service import AnswerResult, AnswerService
from .scenarios import ScenarioCatalogue, ScenarioQuestion, SimulatorScenario, select_scenarios


class SimulationRunConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_ids: list[str] = Field(default_factory=list)
    persona_ids: list[str] = Field(default_factory=list)
    seed: int | None = None
    max_questions: int | None = Field(default=None, ge=1)
    top_k: int = Field(default=5, ge=1, le=20)


class SimulationQuestionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    question_id: str
    persona_id: str
    process_area: str
    value_driver: str
    difficulty: str
    question: str
    expected_behavior: str
    expected_signal: str
    observed_behavior: str
    matched_expectation: bool
    refused: bool
    mode: str
    confidence: str
    grounding: str
    grounding_score: float
    faithfulness: str
    citation_count: int
    latency_ms: int


class SimulationRunSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_questions: int
    answered: int
    refused: int
    guardrail_blocks: int
    declined: int
    expected_gap_questions: int
    expectation_matches: int
    average_latency_ms: float


class SimulationRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    started_at: str
    completed_at: str
    config: SimulationRunConfig
    scenario_count: int
    results: list[SimulationQuestionResult]
    summary: SimulationRunSummary


class SimulationRunStore:
    """File-backed store for compact simulation run metadata."""

    def __init__(self, base_dir: str | Path, filename: str = "simulation_runs.json") -> None:
        self.path = Path(base_dir) / filename
        self._lock = threading.Lock()

    def _read(self) -> list[dict]:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text(encoding="utf-8") or "[]")

    def append(self, run: SimulationRun) -> SimulationRun:
        with self._lock:
            rows = self._read()
            rows.append(run.model_dump())
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(rows[-50:], indent=2), encoding="utf-8")
        return run

    def runs(self) -> list[SimulationRun]:
        return [SimulationRun.model_validate(row) for row in self._read()]

    def recent(self, limit: int = 20) -> list[SimulationRun]:
        safe_limit = max(1, min(limit, 50))
        return list(reversed(self.runs()))[:safe_limit]


class SimulationRunner:
    def __init__(
        self,
        catalogue: ScenarioCatalogue,
        answer_service: AnswerService,
        event_store: AnalyticsEventStore,
        run_store: SimulationRunStore | None = None,
    ) -> None:
        self.catalogue = catalogue
        self.answer_service = answer_service
        self.event_store = event_store
        self.run_store = run_store

    def run(self, config: SimulationRunConfig | None = None) -> SimulationRun:
        cfg = config or SimulationRunConfig()
        scenarios = select_scenarios(self.catalogue, cfg.scenario_ids, cfg.persona_ids, cfg.seed)
        pairs = _question_pairs(scenarios, cfg.seed)
        if cfg.max_questions is not None:
            pairs = pairs[:cfg.max_questions]
        if not pairs:
            raise ValueError("No simulator questions matched the selected configuration.")

        run_id = uuid4().hex
        started_at = now_iso()
        self.event_store.record(
            "simulation_run_started",
            timestamp=started_at,
            actor_type="system",
            entity_type="simulation_run",
            entity_id=run_id,
            metadata={
                "scenario_count": len({scenario.scenario_id for scenario, _ in pairs}),
                "question_count": len(pairs),
                "seed": cfg.seed,
                "max_questions": cfg.max_questions,
                "top_k": cfg.top_k,
                "selected_scenarios": ",".join(cfg.scenario_ids),
                "selected_personas": ",".join(cfg.persona_ids),
            },
        )

        results: list[SimulationQuestionResult] = []
        for scenario, question in pairs:
            t0 = time.time()
            answer = self.answer_service.answer(
                question.text,
                cfg.top_k,
                actor_type="persona",
                actor_id=scenario.persona_id,
                persona=scenario.persona_id,
                process_area=scenario.process_area,
                value_driver=scenario.value_driver,
                telemetry_metadata={
                    "run_id": run_id,
                    "scenario_id": scenario.scenario_id,
                    "question_id": question.question_id,
                    "difficulty": scenario.difficulty,
                    "expected_behavior": question.expected_behavior,
                    "expected_signal": question.expected_signal,
                    "expected_outcome": scenario.expected_outcome,
                },
            )
            latency_ms = int((time.time() - t0) * 1000)
            observed = _observed_behavior(answer, question.expected_behavior)
            results.append(
                SimulationQuestionResult(
                    scenario_id=scenario.scenario_id,
                    question_id=question.question_id,
                    persona_id=scenario.persona_id,
                    process_area=scenario.process_area,
                    value_driver=scenario.value_driver,
                    difficulty=scenario.difficulty,
                    question=question.text,
                    expected_behavior=question.expected_behavior,
                    expected_signal=question.expected_signal,
                    observed_behavior=observed,
                    matched_expectation=observed == question.expected_behavior,
                    refused=answer.refused,
                    mode=answer.mode,
                    confidence=answer.confidence,
                    grounding=answer.grounding,
                    grounding_score=answer.grounding_score,
                    faithfulness=answer.faithfulness,
                    citation_count=len(answer.citations),
                    latency_ms=latency_ms,
                )
            )

        completed_at = now_iso()
        summary = _summary(results)
        run = SimulationRun(
            run_id=run_id,
            started_at=started_at,
            completed_at=completed_at,
            config=cfg,
            scenario_count=len({result.scenario_id for result in results}),
            results=results,
            summary=summary,
        )
        self.event_store.record(
            "simulation_run_completed",
            timestamp=completed_at,
            actor_type="system",
            entity_type="simulation_run",
            entity_id=run_id,
            outcome="completed",
            metadata={
                "scenario_count": run.scenario_count,
                "question_count": summary.total_questions,
                "answered": summary.answered,
                "refused": summary.refused,
                "guardrail_blocks": summary.guardrail_blocks,
                "declined": summary.declined,
                "expectation_matches": summary.expectation_matches,
                "average_latency_ms": summary.average_latency_ms,
            },
        )
        if self.run_store is not None:
            self.run_store.append(run)
        return run


def _question_pairs(
    scenarios: list[SimulatorScenario],
    seed: int | None,
) -> list[tuple[SimulatorScenario, ScenarioQuestion]]:
    pairs = [(scenario, question) for scenario in scenarios for question in scenario.questions]
    if seed is not None:
        pairs = list(pairs)
        random.Random(seed).shuffle(pairs)
    return pairs


def _observed_behavior(answer: AnswerResult, expected_behavior: str) -> str:
    if answer.refused and answer.mode == "guardrail":
        return "guardrail"
    if answer.refused:
        return "refuse"
    if expected_behavior == "decline" and _looks_like_decline(answer.answer):
        return "decline"
    return "answer"


def _looks_like_decline(answer: str) -> bool:
    text = answer.lower()
    return any(marker in text for marker in ["cannot", "can't", "not able", "human review", "approval", "approve"])


def _summary(results: list[SimulationQuestionResult]) -> SimulationRunSummary:
    total = len(results)
    return SimulationRunSummary(
        total_questions=total,
        answered=sum(1 for result in results if result.observed_behavior == "answer"),
        refused=sum(1 for result in results if result.observed_behavior == "refuse"),
        guardrail_blocks=sum(1 for result in results if result.observed_behavior == "guardrail"),
        declined=sum(1 for result in results if result.observed_behavior == "decline"),
        expected_gap_questions=sum(1 for result in results if result.expected_behavior == "refuse"),
        expectation_matches=sum(1 for result in results if result.matched_expectation),
        average_latency_ms=round(sum(result.latency_ms for result in results) / total, 2) if total else 0.0,
    )
