"""Execute synthetic persona scenarios through the normal assistant path."""

from __future__ import annotations

import json
import random
import threading
import time
from datetime import date, datetime, timedelta, timezone
from datetime import time as dt_time
from hashlib import sha256
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from ..analytics.event_store import AnalyticsEventStore
from ..analytics.log import now_iso
from ..answer.service import AnswerResult, AnswerService
from .scenarios import (
    ScenarioCatalogue,
    ScenarioQuestion,
    SimulatorScenario,
    select_scenarios,
)


class SimulationRunConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_kind: Literal["single", "period"] = "single"
    scenario_ids: list[str] = Field(default_factory=list)
    persona_ids: list[str] = Field(default_factory=list)
    seed: int | None = None
    max_questions: int | None = Field(default=None, ge=1)
    top_k: int = Field(default=5, ge=1, le=20)
    preset_period: Literal["last_7_days", "last_30_days", "last_90_days", "custom"] = "last_30_days"
    start_date: str = ""
    end_date: str = ""
    usage_density: Literal["light", "moderate", "heavy"] = "moderate"
    usage_pattern: Literal["steady", "weekday_peak", "ramp_up", "month_end"] = "weekday_peak"


class SimulationQuestionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp: str = ""
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


class SimulationRunQa(BaseModel):
    model_config = ConfigDict(extra="forbid")

    synthetic_only: bool = True
    replayable: bool = True
    synthetic_historical: bool = False
    actor_type: str = "persona"
    source: str = "simulator"
    replay_of_run_id: str | None = None
    question_fingerprint: str = ""
    replay_fingerprint: str = ""
    selected_scenario_ids: list[str] = Field(default_factory=list)
    selected_persona_ids: list[str] = Field(default_factory=list)
    selected_question_ids: list[str] = Field(default_factory=list)
    period_start: str = ""
    period_end: str = ""
    period_day_count: int = 0
    usage_density: str = ""
    usage_pattern: str = ""


class SimulationRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    started_at: str
    completed_at: str
    config: SimulationRunConfig
    qa: SimulationRunQa = Field(default_factory=SimulationRunQa)
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

    def get(self, run_id: str) -> SimulationRun | None:
        for run in reversed(self.runs()):
            if run.run_id == run_id:
                return run
        return None


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

    def run(self, config: SimulationRunConfig | None = None, replay_of_run_id: str | None = None) -> SimulationRun:
        cfg = config or SimulationRunConfig()
        scenarios = select_scenarios(self.catalogue, cfg.scenario_ids, cfg.persona_ids, cfg.seed)
        pairs = _question_pairs(scenarios, cfg.seed)
        if cfg.max_questions is not None:
            pairs = pairs[:cfg.max_questions]
        if not pairs:
            raise ValueError("No simulator questions matched the selected configuration.")

        run_id = uuid4().hex
        started_at = now_iso()
        qa = _qa_metadata(cfg, pairs, replay_of_run_id)
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
                "synthetic_only": qa.synthetic_only,
                "replay_of_run_id": qa.replay_of_run_id or "",
                "question_fingerprint": qa.question_fingerprint,
                "replay_fingerprint": qa.replay_fingerprint,
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
            qa=qa,
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
                "synthetic_only": qa.synthetic_only,
                "replayable": qa.replayable,
                "replay_of_run_id": qa.replay_of_run_id or "",
                "question_fingerprint": qa.question_fingerprint,
                "replay_fingerprint": qa.replay_fingerprint,
            },
        )
        if self.run_store is not None:
            self.run_store.append(run)
        return run

    def replay(self, run_id: str) -> SimulationRun:
        if self.run_store is None:
            raise ValueError("Simulation replay is not configured.")
        source_run = self.run_store.get(run_id)
        if source_run is None:
            raise ValueError(f"Simulation run {run_id} was not found.")
        if not source_run.qa.replayable:
            raise ValueError(f"Simulation run {run_id} is not replayable.")
        return self.run(source_run.config, replay_of_run_id=source_run.run_id)

    def run_historical_period(self, config: SimulationRunConfig | None = None) -> SimulationRun:
        cfg = config or SimulationRunConfig(run_kind="period")
        cfg = cfg.model_copy(update={"run_kind": "period"})
        scenarios = select_scenarios(self.catalogue, cfg.scenario_ids, cfg.persona_ids, cfg.seed)
        pairs = _question_pairs(scenarios, cfg.seed)
        if not pairs:
            raise ValueError("No simulator questions matched the selected configuration.")

        days = _period_days(cfg)
        selected = _historical_schedule(pairs, days, cfg)
        if not selected:
            raise ValueError("The historical period configuration produced no synthetic interactions.")

        run_id = uuid4().hex
        started_at = now_iso()
        qa = _qa_metadata(cfg, [(scenario, question) for _, scenario, question in selected], None)
        qa.synthetic_historical = True
        qa.replayable = False
        qa.source = "period_simulator"
        qa.period_start = days[0].isoformat()
        qa.period_end = days[-1].isoformat()
        qa.period_day_count = len(days)
        qa.usage_density = cfg.usage_density
        qa.usage_pattern = cfg.usage_pattern
        self.event_store.record(
            "simulation_run_started",
            timestamp=started_at,
            actor_type="system",
            entity_type="simulation_run",
            entity_id=run_id,
            metadata={
                "run_kind": "period",
                "scenario_count": len({scenario.scenario_id for _, scenario, _ in selected}),
                "question_count": len(selected),
                "seed": cfg.seed,
                "max_questions": cfg.max_questions,
                "selected_scenarios": ",".join(cfg.scenario_ids),
                "selected_personas": ",".join(cfg.persona_ids),
                "synthetic_only": True,
                "synthetic_historical": True,
                "period_start": qa.period_start,
                "period_end": qa.period_end,
                "usage_density": cfg.usage_density,
                "usage_pattern": cfg.usage_pattern,
                "question_fingerprint": qa.question_fingerprint,
                "replay_fingerprint": qa.replay_fingerprint,
            },
        )

        results: list[SimulationQuestionResult] = []
        for index, (ts, scenario, question) in enumerate(selected, start=1):
            observed = _historical_observed_behavior(question.expected_behavior)
            refused = observed in {"refuse", "guardrail", "decline"}
            synthetic_value = _synthetic_value_estimate(scenario.value_driver, scenario.difficulty, observed)
            result = SimulationQuestionResult(
                timestamp=ts,
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
                refused=refused,
                mode="historical-synthetic",
                confidence="none" if refused else "grounded",
                grounding="n/a" if refused else "supported",
                grounding_score=0.0 if refused else 0.86,
                faithfulness="n/a" if refused else "supported",
                citation_count=0 if refused else 2,
                latency_ms=_historical_latency(ts, scenario.scenario_id, question.question_id),
            )
            results.append(result)
            self.event_store.record(
                _event_type_for_observed(observed),
                timestamp=ts,
                actor_type="persona",
                actor_id=scenario.persona_id,
                entity_type="ask",
                process_area=scenario.process_area,
                persona=scenario.persona_id,
                outcome=observed,
                value_driver=scenario.value_driver,
                metadata={
                    "run_id": run_id,
                    "run_kind": "period",
                    "scenario_id": scenario.scenario_id,
                    "question_id": question.question_id,
                    "difficulty": scenario.difficulty,
                    "expected_behavior": question.expected_behavior,
                    "expected_signal": question.expected_signal,
                    "synthetic_only": True,
                    "synthetic_historical": True,
                    "period_start": qa.period_start,
                    "period_end": qa.period_end,
                    "usage_density": cfg.usage_density,
                    "usage_pattern": cfg.usage_pattern,
                    "confidence": result.confidence,
                    "grounding": result.grounding,
                    "grounding_score": result.grounding_score,
                    "faithfulness": result.faithfulness,
                    "citation_count": result.citation_count,
                    "latency_ms": result.latency_ms,
                    "topic": scenario.process_area,
                },
            )
            self.event_store.record(
                "value_event_recorded",
                timestamp=ts,
                actor_type="persona",
                actor_id=scenario.persona_id,
                entity_type="value_event",
                entity_id=f"value-{run_id}-{index}",
                process_area=scenario.process_area,
                persona=scenario.persona_id,
                outcome="synthetic_projected",
                value_driver=scenario.value_driver,
                value_estimate=synthetic_value,
                metadata={
                    "label": "Synthetic simulator value signal",
                    "scenario_id": "base",
                    "unit": "GBP",
                    "confidence": "synthetic",
                    "evidence_type": "synthetic_period_simulator",
                    "run_id": run_id,
                    "run_kind": "period",
                    "simulator_scenario_id": scenario.scenario_id,
                    "question_id": question.question_id,
                    "synthetic_only": True,
                    "synthetic_historical": True,
                    "period_start": qa.period_start,
                    "period_end": qa.period_end,
                    "usage_density": cfg.usage_density,
                    "usage_pattern": cfg.usage_pattern,
                },
            )

        completed_at = now_iso()
        summary = _summary(results)
        run = SimulationRun(
            run_id=run_id,
            started_at=started_at,
            completed_at=completed_at,
            config=cfg,
            qa=qa,
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
                "run_kind": "period",
                "scenario_count": run.scenario_count,
                "question_count": summary.total_questions,
                "answered": summary.answered,
                "refused": summary.refused,
                "guardrail_blocks": summary.guardrail_blocks,
                "declined": summary.declined,
                "expectation_matches": summary.expectation_matches,
                "average_latency_ms": summary.average_latency_ms,
                "synthetic_only": qa.synthetic_only,
                "synthetic_historical": qa.synthetic_historical,
                "replayable": qa.replayable,
                "period_start": qa.period_start,
                "period_end": qa.period_end,
                "period_day_count": qa.period_day_count,
                "usage_density": cfg.usage_density,
                "usage_pattern": cfg.usage_pattern,
                "question_fingerprint": qa.question_fingerprint,
                "replay_fingerprint": qa.replay_fingerprint,
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


def _qa_metadata(
    config: SimulationRunConfig,
    pairs: list[tuple[SimulatorScenario, ScenarioQuestion]],
    replay_of_run_id: str | None,
) -> SimulationRunQa:
    question_manifest = _question_manifest(pairs)
    scenario_ids = sorted({scenario.scenario_id for scenario, _ in pairs})
    persona_ids = sorted({scenario.persona_id for scenario, _ in pairs})
    question_ids = [f"{scenario.scenario_id}:{question.question_id}" for scenario, question in pairs]
    return SimulationRunQa(
        replay_of_run_id=replay_of_run_id,
        question_fingerprint=_stable_hash({"questions": question_manifest}),
        replay_fingerprint=_stable_hash({"config": config.model_dump(), "questions": question_manifest}),
        selected_scenario_ids=scenario_ids,
        selected_persona_ids=persona_ids,
        selected_question_ids=question_ids,
    )


def _question_manifest(pairs: list[tuple[SimulatorScenario, ScenarioQuestion]]) -> list[dict[str, str]]:
    return [
        {
            "scenario_id": scenario.scenario_id,
            "persona_id": scenario.persona_id,
            "process_area": scenario.process_area,
            "value_driver": scenario.value_driver,
            "question_id": question.question_id,
            "question": question.text,
            "expected_behavior": question.expected_behavior,
            "expected_signal": question.expected_signal,
        }
        for scenario, question in pairs
    ]


def _stable_hash(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return sha256(encoded).hexdigest()


def _observed_behavior(answer: AnswerResult, expected_behavior: str) -> str:
    if answer.refused and answer.mode == "guardrail":
        return "guardrail"
    if expected_behavior == "decline" and (answer.refused or _looks_like_decline(answer.answer)):
        return "decline"
    if answer.refused:
        return "refuse"
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


def _period_days(config: SimulationRunConfig) -> list[date]:
    today = datetime.now(timezone.utc).date()
    if config.preset_period == "custom":
        if not config.start_date or not config.end_date:
            raise ValueError("Custom historical period requires start_date and end_date.")
        start = _parse_date(config.start_date)
        end = _parse_date(config.end_date)
    else:
        span = {"last_7_days": 7, "last_30_days": 30, "last_90_days": 90}[config.preset_period]
        end = today - timedelta(days=1)
        start = end - timedelta(days=span - 1)
    if end >= today:
        raise ValueError("Historical period must end before today.")
    if start > end:
        raise ValueError("Historical period start_date must be on or before end_date.")
    if (end - start).days > 180:
        raise ValueError("Historical period cannot exceed 181 days.")
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


def _historical_schedule(
    pairs: list[tuple[SimulatorScenario, ScenarioQuestion]],
    days: list[date],
    config: SimulationRunConfig,
) -> list[tuple[str, SimulatorScenario, ScenarioQuestion]]:
    rng = random.Random(config.seed if config.seed is not None else 0)
    density = {"light": 1.0, "moderate": 3.0, "heavy": 6.0}[config.usage_density]
    cap = config.max_questions if config.max_questions is not None else 250
    rows: list[tuple[str, SimulatorScenario, ScenarioQuestion]] = []
    pool = list(pairs)
    for index, day in enumerate(days):
        planned = _interactions_for_day(day, index, len(days), density, config.usage_pattern, rng)
        for ordinal in range(planned):
            if len(rows) >= cap:
                return rows
            scenario, question = pool[(len(rows) + ordinal + rng.randrange(len(pool))) % len(pool)]
            ts = _historical_timestamp(day, len(rows), rng)
            rows.append((ts, scenario, question))
    return rows


def _interactions_for_day(
    day: date,
    index: int,
    total_days: int,
    density: float,
    pattern: str,
    rng: random.Random,
) -> int:
    multiplier = 1.0
    if pattern == "weekday_peak":
        multiplier = 1.25 if day.weekday() < 5 else 0.35
    elif pattern == "ramp_up":
        multiplier = 0.5 + (index / max(1, total_days - 1))
    elif pattern == "month_end":
        multiplier = 1.7 if day.day >= 25 or day.day <= 3 else 0.65
    raw = density * multiplier
    count = int(raw)
    if rng.random() < raw - count:
        count += 1
    return count


def _historical_timestamp(day: date, ordinal: int, rng: random.Random) -> str:
    minute = 8 * 60 + ((ordinal * 37) + rng.randrange(0, 31)) % (10 * 60)
    hour, mins = divmod(minute, 60)
    second = rng.randrange(0, 60)
    dt = datetime.combine(day, dt_time(hour=hour, minute=mins, second=second), tzinfo=timezone.utc)
    return dt.isoformat()


def _historical_observed_behavior(expected_behavior: str) -> str:
    if expected_behavior in {"answer", "refuse", "guardrail", "decline"}:
        return expected_behavior
    return "answer"


def _event_type_for_observed(observed: str) -> str:
    if observed == "guardrail":
        return "ask_guardrail_blocked"
    if observed in {"refuse", "decline"}:
        return "ask_refused"
    return "ask_answered"


def _historical_latency(timestamp: str, scenario_id: str, question_id: str) -> int:
    digest = _stable_hash({"timestamp": timestamp, "scenario_id": scenario_id, "question_id": question_id})
    return 650 + (int(digest[:6], 16) % 1450)


def _synthetic_value_estimate(value_driver: str, difficulty: str, observed: str) -> float:
    base_by_driver = {
        "time_saved": 35.0,
        "sme_clarification_avoided": 45.0,
        "delivery_delay_reduced": 95.0,
        "rework_avoided": 65.0,
        "risk_reduction": 55.0,
    }
    difficulty_multiplier = {"basic": 1.0, "intermediate": 1.35, "advanced": 1.75}.get(difficulty, 1.0)
    outcome_multiplier = 0.3 if observed in {"refuse", "guardrail", "decline"} else 1.0
    return round(base_by_driver.get(value_driver, 40.0) * difficulty_multiplier * outcome_multiplier, 2)


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Invalid date: {value}") from exc
