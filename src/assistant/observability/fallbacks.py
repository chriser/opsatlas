"""Fallbacks made visible (ARCH F5).

When a step of the question path fails, the service carries on with less: the question as asked instead of a
rewrite, the search order instead of a rerank, lexical search instead of hybrid, a refusal from the facts map
instead of a document search. Until now each of these was a silent ``except``, so a degraded answer looked like
any other (the external architecture review of 27 September 2026, problem 5). A fallback is now logged as a
warning, which the service log shows, and kept with the answer it happened in, which the audit trace records.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar

logger = logging.getLogger("assistant.fallbacks")
_answer: ContextVar[list[dict] | None] = ContextVar("fallbacks_of_the_answer", default=None)


def begin() -> None:
    """Start collecting the fallbacks of one answer (the context is per request)."""
    _answer.set([])


def collect() -> list[dict]:
    """The fallbacks collected since ``begin``, which ends the collection: a fallback after this is only logged."""
    found = list(_answer.get() or [])
    _answer.set(None)
    return found


def note(step: str, cause: BaseException | str, *, kept: str) -> None:
    """Record that ``step`` fell back, why, and what was kept instead."""
    reason = cause if isinstance(cause, str) else f"{type(cause).__name__}: {cause}"
    detail = {"step": step, "cause": reason[:200], "kept": kept}
    logger.warning("Fallback in %s (%s); kept %s.", step, detail["cause"], kept)
    found = _answer.get()
    if found is not None:
        found.append(detail)
