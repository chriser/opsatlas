"""Grounded-answer (Ask the assistant) route."""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, Request
from pydantic import BaseModel

from ..analytics.log import recording
from ..answer.service import AnswerService
from .access import still_allowed


class AskRequest(BaseModel):
    q: str
    top_k: int = 5


def build_ask_router(answer_service: AnswerService, dependencies: Sequence | None = None) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["assistant"], dependencies=list(dependencies or []))

    @router.post("/ask")
    def ask(body: AskRequest, request: Request) -> dict:
        with recording() as recorded:
            result = answer_service.answer(body.q, max(1, min(body.top_k, 20)))
        if getattr(request.state, "actor", None) is not None:
            still_allowed(request, "knowledge.ask")  # revoked while it was prepared: withheld (REF S16)
        # The usage entry's id, by which the asker rates the answer (REF S20).
        return {**result.model_dump(), "usage_id": recorded[-1] if recorded else None}

    return router
