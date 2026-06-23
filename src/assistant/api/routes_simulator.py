"""Synthetic persona simulator API routes."""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, HTTPException

from ..simulator.runner import SimulationRunConfig, SimulationRunner, SimulationRunStore
from ..simulator.scenarios import ScenarioCatalogue


def build_simulator_router(
    catalogue: ScenarioCatalogue,
    runner: SimulationRunner,
    run_store: SimulationRunStore,
    dependencies: Sequence | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/simulator", tags=["simulator"], dependencies=list(dependencies or []))

    @router.get("/scenarios")
    def scenarios() -> dict:
        return catalogue.model_dump()

    @router.get("/runs")
    def runs(limit: int = 20) -> list[dict]:
        return [run.model_dump() for run in run_store.recent(limit)]

    @router.post("/runs")
    def run_simulation(config: SimulationRunConfig) -> dict:
        try:
            return runner.run(config).model_dump()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/period-runs")
    def run_historical_period(config: SimulationRunConfig) -> dict:
        try:
            return runner.run_historical_period(config).model_dump()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/runs/{run_id}/replay")
    def replay_simulation(run_id: str) -> dict:
        try:
            return runner.replay(run_id).model_dump()
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return router
