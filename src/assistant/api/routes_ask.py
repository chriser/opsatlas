"""Grounded-answer (Ask the assistant) route."""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..analytics.log import recording
from ..answer.service import AnswerService
from ..iam.visibility import visible
from .access import current_actor, need, still_allowed


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
        # Delivery rechecks the evidence (REF S19): every cited source still readable and still the version it was.
        version_of = getattr(answer_service, "version_of", None)
        current = (lambda item: (version_of(item.source_id) or {}).get("sha")) if version_of else (lambda item: None)
        bundle = answer_service.bundle(body.q, result, actor_id=None, space=getattr(answer_service, "space_id", None))
        if not bundle.recheck(lambda item: item.kind != "passage" or visible(item.source_id), current):
            raise HTTPException(status_code=409, detail="The evidence changed while the answer was prepared; ask again.")
        # The usage entry's id, by which the asker rates the answer (REF S20).
        return {**result.model_dump(), "usage_id": recorded[-1] if recorded else None}

    @router.get("/answers/receipts/{receipt_id}", dependencies=[need("knowledge.ask")])
    def receipt(receipt_id: str, request: Request) -> dict:
        """An answer's evidence receipt (REF S18): for the person who asked, or for those who may read traces here.
        A source the reader may no longer read is shown as withheld, without its title or place."""
        row = answer_service.receipts.get(receipt_id) if answer_service.receipts is not None else None
        actor = current_actor(request)
        if row is None or (row.get("person") != actor.id
                           and not actor.can("diagnostics.traces.read", getattr(answer_service, "space_id", None))):
            raise HTTPException(status_code=404, detail="No such receipt")
        row["evidence"] = [e if e.get("citation_type") != "document" or visible(e["source_id"]) else {"withheld": True}
                           for e in row.get("evidence", [])]
        return row

    return router
