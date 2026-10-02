"""Grounded-answer (Ask the assistant) route."""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, Request
from pydantic import BaseModel

from ..answer.service import AnswerService
from .access import still_allowed


class AskRequest(BaseModel):
    q: str
    top_k: int = 5


def build_ask_router(answer_service: AnswerService, dependencies: Sequence | None = None) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["assistant"], dependencies=list(dependencies or []))

    @router.post("/ask")
    def ask(body: AskRequest, request: Request) -> dict:
        result = answer_service.answer(body.q, max(1, min(body.top_k, 20)))
        if getattr(request.state, "actor", None) is not None:
            still_allowed(request, "knowledge.ask")  # revoked while it was prepared: withheld (REF S16)
        return result.model_dump()

    return router
