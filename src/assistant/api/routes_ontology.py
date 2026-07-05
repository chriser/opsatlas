"""Ontology API routes."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ..ontology.actions import ActionActor, ActionsEngine
from ..ontology.query import OntologyQueryService
from ..ontology.store import OntologyStore


class ActionExecuteRequest(BaseModel):
    params: dict[str, Any] = Field(default_factory=dict)


def build_ontology_router(
    store: OntologyStore,
    *,
    rebuild: Callable[[], dict[str, Any]] | None = None,
    actions: ActionsEngine | None = None,
    dependencies: Sequence | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/ontology", tags=["ontology"], dependencies=list(dependencies or []))
    query_service = OntologyQueryService(store)

    @router.get("/schema")
    def schema() -> dict[str, Any]:
        return query_service.schema()

    @router.get("/objects")
    def objects(request: Request, object_type: str = Query(alias="type"), q: str = "") -> dict[str, Any]:
        try:
            results = query_service.find_objects(object_type, query=q, filters=_property_filters(request))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"objects": results, "count": len(results)}

    @router.get("/objects/{object_id}")
    def object_detail(object_id: str) -> dict[str, Any]:
        result = query_service.get_object(object_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Ontology object not found.")
        return result

    @router.get("/traverse")
    def traverse(from_id: str, link: str, direction: str = "out") -> dict[str, Any]:
        if direction not in {"out", "in"}:
            raise HTTPException(status_code=400, detail="direction must be 'out' or 'in'.")
        try:
            results = query_service.traverse(from_id, link, direction=direction)  # type: ignore[arg-type]
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"objects": results, "count": len(results)}

    @router.get("/stats")
    def stats() -> dict[str, Any]:
        return query_service.stats()

    @router.get("/actions")
    def action_definitions() -> dict[str, Any]:
        if actions is None:
            raise HTTPException(status_code=503, detail="Ontology actions are not configured.")
        definitions = actions.action_definitions()
        return {"actions": definitions, "count": len(definitions)}

    @router.get("/actions/log")
    def action_log(limit: int = 50) -> dict[str, Any]:
        if actions is None:
            raise HTTPException(status_code=503, detail="Ontology actions are not configured.")
        executions = actions.action_log.recent(limit)
        return {"executions": [item.model_dump() for item in executions], "count": len(executions)}

    @router.post("/actions/{api_name}")
    def execute_action(api_name: str, body: ActionExecuteRequest | None = None) -> dict[str, Any]:
        if actions is None:
            raise HTTPException(status_code=503, detail="Ontology actions are not configured.")
        try:
            result = actions.execute(api_name, (body or ActionExecuteRequest()).params, ActionActor(type="operator", id="operator"))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return result.model_dump()

    @router.post("/rebuild")
    def rebuild_endpoint() -> dict[str, Any]:
        if rebuild is None:
            raise HTTPException(status_code=500, detail="Ontology rebuild is not available.")
        return rebuild()

    return router


def _property_filters(request: Request) -> dict[str, str]:
    filters: dict[str, str] = {}
    for key, value in request.query_params.multi_items():
        if key.startswith("property."):
            property_name = key.removeprefix("property.")
            if property_name:
                filters[property_name] = value
    return filters
