"""Enterprise Activity Model read routes."""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, HTTPException, Query, Response

from ..eam import TaxonomyConfig, build_eam_model
from ..eam.render_activity import render_activity_svg
from ..ontology.store import OntologyStore


def build_eam_router(
    ontology_store: OntologyStore,
    *,
    dependencies: Sequence | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/eam", tags=["eam"], dependencies=list(dependencies or []))

    @router.get("/taxonomy")
    def taxonomy() -> dict:
        return TaxonomyConfig.load().model_dump()

    @router.get("/model")
    def model() -> dict:
        return build_eam_model(ontology_store, TaxonomyConfig.load()).model_dump()

    @router.get("/svg")
    def svg(view: str = Query(default="activity")) -> Response:
        if view != "activity":
            raise HTTPException(status_code=400, detail="Only the activity SVG view is available before EAM-3.")
        eam = build_eam_model(ontology_store, TaxonomyConfig.load())
        return Response(render_activity_svg(eam), media_type="image/svg+xml")

    return router
