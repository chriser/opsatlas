"""Grounded-answer (Ask the assistant) route."""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter
from pydantic import BaseModel

from ..answer.service import AnswerService


class AskRequest(BaseModel):
    q: str
    top_k: int = 5


def build_ask_router(answer_service: AnswerService, dependencies: Sequence | None = None) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["assistant"], dependencies=list(dependencies or []))

    @router.post("/ask")
    def ask(body: AskRequest) -> dict:
        result = answer_service.answer(body.q, max(1, min(body.top_k, 20)))
        return result.model_dump()

    return router
