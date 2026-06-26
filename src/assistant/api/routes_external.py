"""Public external-source routes."""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..external.govuk import (
    GOVUKContentClient,
    GOVUKContentError,
    GOVUKRateLimitError,
    is_supported_public_source_url,
    public_source_provider,
)
from ..external.registry import PublicContentRegistry


class GOVUKSnapshotRequest(BaseModel):
    url: str
    topics: list[str] = []
    licence: str = "Open Government Licence v3.0"
    update_cadence: str = "manual"


def build_external_sources_router(
    registry: PublicContentRegistry,
    govuk_client: GOVUKContentClient | None = None,
    dependencies: Sequence | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/external-sources", tags=["external-sources"], dependencies=list(dependencies or []))
    client = govuk_client or GOVUKContentClient()

    @router.get("")
    def list_sources() -> list[dict]:
        return [source.model_dump() for source in registry.list_sources()]

    @router.get("/snapshots")
    def list_snapshots(source_id: str | None = None, include_text: bool = False) -> list[dict]:
        snapshots = registry.list_snapshots(source_id=source_id, include_text=include_text)
        return [snapshot.model_dump() if hasattr(snapshot, "model_dump") else snapshot for snapshot in snapshots]

    @router.post("/govuk/snapshot")
    def snapshot_govuk(request: GOVUKSnapshotRequest) -> dict:
        try:
            fetched = client.fetch(request.url)
        except GOVUKRateLimitError as exc:
            registry.record_failure(provider=public_source_provider(request.url), url=request.url, error=str(exc))
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except GOVUKContentError as exc:
            if is_supported_public_source_url(request.url):
                registry.record_failure(provider=public_source_provider(request.url), url=request.url, error=str(exc))
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        source = registry.upsert_source(
            provider=fetched.provider,
            url=fetched.url,
            title=fetched.title,
            public_body=fetched.public_body,
            topics=request.topics,
            licence=request.licence,
            update_cadence=request.update_cadence,
        )
        snapshot = registry.add_snapshot(source.id, fetched)
        return {"source": registry.get_source(source.id).model_dump(), "snapshot": snapshot.model_dump()}

    return router
