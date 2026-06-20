"""Retrieval query route."""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter
from pydantic import BaseModel

from ..retrieval.service import RetrievalService


class QueryRequest(BaseModel):
    q: str
    top_k: int = 5


def build_query_router(retrieval: RetrievalService, dependencies: Sequence | None = None) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["retrieval"], dependencies=list(dependencies or []))

    @router.post("/query")
    def query(body: QueryRequest) -> dict:
        results, mode = retrieval.search(body.q, max(1, min(body.top_k, 20)))
        return {"mode": mode, "results": [r.model_dump() for r in results]}

    return router
