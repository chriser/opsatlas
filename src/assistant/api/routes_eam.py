"""Enterprise Activity Model read routes."""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, HTTPException, Query, Response

from ..eam import TaxonomyConfig, build_eam_model
from ..eam.render_accountability import render_accountability_svg
from ..eam.render_activity import render_activity_svg
from ..eam.render_relationship import render_relationship_svg
from ..eam.render_risk_heat import render_risk_heat_svg
from ..eam.render_system_landscape import render_system_landscape_svg
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
    def svg(
        view: str = Query(default="activity"),
        expanded: str = Query(default=""),
        selected: str = Query(default=""),
    ) -> Response:
        eam = build_eam_model(ontology_store, TaxonomyConfig.load())
        if view == "activity":
            expanded_node_ids = {item.strip() for item in expanded.split(",") if item.strip()}
            return Response(render_activity_svg(eam, expanded_node_ids=expanded_node_ids), media_type="image/svg+xml")
        if view == "accountability":
            return Response(render_accountability_svg(eam), media_type="image/svg+xml")
        if view == "risk":
            return Response(render_risk_heat_svg(eam), media_type="image/svg+xml")
        if view == "relationship":
            return Response(render_relationship_svg(eam), media_type="image/svg+xml")
        if view == "system-landscape":
            return Response(render_system_landscape_svg(eam, selected_node_id=selected or None), media_type="image/svg+xml")
        raise HTTPException(
            status_code=400,
            detail="Supported EAM SVG views: activity, accountability, risk, relationship, system-landscape.",
        )

    return router
