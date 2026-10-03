"""Seeded random-scenario tests (the Definition of Done of 3 October 2026, REF F10).

A suite names its promises (what must always be true) and its scenario kinds (the things that can go wrong, each a
step a run may take). Each run draws a seed, builds a random sequence of kinds from it, applies them, and checks every
promise after every step. A failure reports the seed, the steps so far and the promise broken, and
``OPSATLAS_SCENARIO_SEED=<seed> OPSATLAS_SCENARIO_RUNS=1`` replays exactly that run.

A fault a reviewer finds becomes a new kind in its suite (not one more test), so every later run tries it among the
rest. Models are never called: a suite uses the real code with fakes for anything slow, so thousands of runs take
seconds and the suite runs in the gate.

    OPSATLAS_SCENARIO_RUNS   runs per suite (default 2000; CI uses the default)
    OPSATLAS_SCENARIO_SEED   the first seed (default 20261003); run n uses seed + n
"""
from __future__ import annotations

import os
import random
from collections.abc import Callable
from dataclasses import dataclass, field

RUNS = int(os.environ.get("OPSATLAS_SCENARIO_RUNS", "2000"))
SEED = int(os.environ.get("OPSATLAS_SCENARIO_SEED", "20261003"))


class PromiseBroken(AssertionError):
    pass


@dataclass
class Run:
    """One run: its seed, its random source, and the steps taken so far (for the report)."""
    seed: int
    rng: random.Random
    steps: list[str] = field(default_factory=list)

    def step(self, kind: str, detail: str = "") -> None:
        self.steps.append(f"{kind}{': ' + detail if detail else ''}")

    def promise(self, name: str, holds: bool, why: str = "") -> None:
        if not holds:
            raise PromiseBroken(f"promise '{name}' broken{': ' + why if why else ''}")


def explore(suite: str, one_run: Callable[[Run], None], runs: int | None = None) -> int:
    """Run ``one_run`` for each seed; stop at the first broken promise or crash with a report that replays it.
    Returns the number of runs made (so a suite can assert it explored)."""
    count = RUNS if runs is None else runs
    for n in range(count):
        seed = SEED + n
        run = Run(seed, random.Random(seed))
        try:
            one_run(run)
        except Exception as exc:  # a crash is a broken promise too: nothing may crash on any scenario
            steps = "\n  ".join(run.steps[-15:]) or "(before the first step)"
            raise PromiseBroken(f"{suite}: seed {seed} ({type(exc).__name__}: {exc})\n  last steps:\n  {steps}\n"
                                f"replay: OPSATLAS_SCENARIO_SEED={seed} OPSATLAS_SCENARIO_RUNS=1") from exc
    return count
