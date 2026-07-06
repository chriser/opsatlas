"""Enterprise Activity Model read routes."""

from __future__ import annotations

from collections.abc import Sequence
from html import escape

from fastapi import APIRouter, HTTPException, Query, Response

from ..eam import TaxonomyConfig, build_eam_model
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
        return Response(_activity_svg_placeholder(eam.model_dump()), media_type="image/svg+xml")

    return router


def _activity_svg_placeholder(model: dict) -> str:
    """Small route-level placeholder until EAM-2.2 adds the full renderer."""

    width = 980
    height = 220
    coverage = model.get("coverage", {})
    score = coverage.get("score", 0)
    process_count = model.get("process_count", 0)
    source_count = model.get("source_count", 0)
    finding_count = model.get("meta", {}).get("finding_count", 0)
    title = f"Enterprise Activity Model - {process_count} processes from {source_count} sources"
    subtitle = f"Coverage {score}% · {finding_count} triage findings · full activity renderer follows in EAM-2.2"
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">
  <rect x="0" y="0" width="{width}" height="{height}" rx="18" fill="#111827"/>
  <rect x="24" y="24" width="{width - 48}" height="{height - 48}" rx="14" fill="#172033" stroke="#334155"/>
  <text x="48" y="76" fill="#f8fafc" font-family="Inter, Arial, sans-serif" font-size="28" font-weight="700">{escape(title)}</text>
  <text x="48" y="116" fill="#cbd5e1" font-family="Inter, Arial, sans-serif" font-size="18">{escape(subtitle)}</text>
  <text x="48" y="164" fill="#ec4899" font-family="Inter, Arial, sans-serif" font-size="16"
        font-weight="700">Activity canvas route ready</text>
  <text x="280" y="164" fill="#94a3b8" font-family="Inter, Arial, sans-serif" font-size="16">
    The deterministic grid renderer will replace this placeholder in the next slice.
  </text>
</svg>"""
