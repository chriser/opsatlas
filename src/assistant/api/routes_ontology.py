"""Ontology API routes."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from fastapi import APIRouter, HTTPException

from ..ontology.store import OntologyStore


def build_ontology_router(
    store: OntologyStore,
    *,
    rebuild: Callable[[], dict[str, Any]] | None = None,
    dependencies: Sequence | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/ontology", tags=["ontology"], dependencies=list(dependencies or []))

    @router.post("/rebuild")
    def rebuild_endpoint() -> dict[str, Any]:
        if rebuild is None:
            raise HTTPException(status_code=500, detail="Ontology rebuild is not available.")
        return rebuild()

    return router
