"""A space's governed fixed sentences (REF S22): read them, and approve a pending version."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..space_config import SpaceConfig
from .access import current_actor, need


class Approval(BaseModel):
    version: int


def build_statements_router(app, base_dir) -> APIRouter:
    router = APIRouter(prefix="/api/space-statements", tags=["governance"])

    @router.get("", dependencies=[need("documents.read")])
    def listing() -> dict:
        """Each sentence: the version in use, and any pending one written in the space's configuration since."""
        return {"statements": app.state.space_statements.listing()}

    @router.post("/{key}/approve", dependencies=[need("documents.approve")])
    def approve(key: str, body: Approval, request: Request) -> dict:
        """Approve a version: from now on the space says it, and answers that use it record this version."""
        statements = app.state.space_statements
        try:
            row = statements.approve(key, body.version, current_actor(request).display_name)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="No such statement version") from exc
        config = statements.governed(SpaceConfig.load(base_dir))
        app.state.space_config = config
        app.state.answer.use_config(config)
        events = getattr(app.state, "analytics_events", None)
        if events is not None:
            events.record("action_approved", actor_type="operator", entity_type="space_statement", entity_id=key,
                          outcome="approved", metadata={"version": body.version})
        return row

    return router
