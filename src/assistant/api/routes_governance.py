"""Governance routes: knowledge-intelligence overview and the approval gate."""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..analytics.event_store import AnalyticsEventStore
from ..analytics.governance_history import record_governance_snapshot
from ..governance.accepted import issue_key
from ..governance.intelligence import KnowledgeIntelligence
from ..governance.remediation import suggest_remediation
from ..ingestion.service import NotIngestableError, ingest_source
from ..ingestion.store import SectionStore
from ..sources.register import SourceRegister


class DocumentEdit(BaseModel):
    text: str


class IssueRef(BaseModel):
    source_id: str
    check: str
    detail: str


def build_governance_router(
    register: SourceRegister,
    intelligence: KnowledgeIntelligence,
    section_store: SectionStore | None = None,
    accepted=None,
    event_store: AnalyticsEventStore | None = None,
    process_registry=None,
    dependencies: Sequence | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/governance", tags=["governance"], dependencies=list(dependencies or []))

    @router.get("/intelligence")
    def overview() -> dict:
        report = intelligence.run()
        if event_store is not None:
            record_governance_snapshot(report, event_store)
        return report

    @router.post("/issues/accept")
    def accept_issue(ref: IssueRef) -> dict:
        if accepted is None:
            raise HTTPException(status_code=500, detail="Accepting issues is not available.")
        accepted.accept(ref.source_id, ref.check, ref.detail)
        if event_store is not None:
            event_store.record(
                "governance_issue_accepted",
                actor_type="operator",
                entity_type="governance_issue",
                entity_id=issue_key(ref.source_id, ref.check, ref.detail),
                source_id=ref.source_id,
                outcome="accepted",
                metadata={"check": ref.check},
            )
        return {"accepted": True}

    @router.get("/sources/{source_id}/document")
    def get_document(source_id: str) -> dict:
        record = register.get(source_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Source not found.")
        return {"id": record.id, "title": record.title, "text": register.read_content(source_id).decode("utf-8", "replace")}

    @router.get("/remediation/{a_id}/{b_id}")
    def remediation(a_id: str, b_id: str) -> dict:
        docs = []
        for sid in (a_id, b_id):
            rec = register.get(sid)
            if rec is None:
                raise HTTPException(status_code=404, detail="Source not found.")
            docs.append({"id": rec.id, "title": rec.title, "text": register.read_content(sid).decode("utf-8", "replace")})
        return suggest_remediation(docs[0], docs[1])

    @router.put("/sources/{source_id}/document")
    def save_document(source_id: str, edit: DocumentEdit) -> dict:
        record = register.get(source_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Source not found.")
        if section_store is None:
            raise HTTPException(status_code=500, detail="Editing is not available.")
        register.write_content(source_id, edit.text.encode("utf-8"))
        try:
            updated = ingest_source(register, section_store, source_id)  # rebuild sections from edited content
        except NotIngestableError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if event_store is not None:
            event_store.record(
                "source_edited",
                actor_type="operator",
                entity_type="source",
                entity_id=updated.id,
                source_id=updated.id,
                metadata={
                    "title": updated.title,
                    "section_count": updated.section_count,
                    "size_bytes": len(edit.text.encode("utf-8")),
                    "processing_state": updated.processing_state,
                    "approval_status": updated.approval_status,
                },
            )
        return {"id": updated.id, "title": updated.title, "section_count": updated.section_count}

    @router.post("/sources/{source_id}/approve")
    def approve(source_id: str) -> dict:
        result = _set_status(register, source_id, "approved", event_store=event_store)
        _refresh_process_registry()
        return result

    @router.post("/sources/{source_id}/reject")
    def reject(source_id: str) -> dict:
        result = _set_status(register, source_id, "rejected", event_store=event_store)
        _refresh_process_registry()
        return result

    def _refresh_process_registry() -> None:
        # Persist the registry when the approved set changes, so read paths (which use
        # the pure derive) and the answer-routing (which reads the persisted file) stay current.
        if process_registry is not None:
            process_registry.build_from_sources(register)

    return router


def _set_status(register: SourceRegister, source_id: str, status: str, event_store: AnalyticsEventStore | None = None) -> dict:
    record = register.update(source_id, approval_status=status)
    if record is None:
        raise HTTPException(status_code=404, detail="Source not found.")
    if event_store is not None:
        event_store.record(
            "source_approved" if status == "approved" else "source_rejected",
            actor_type="operator",
            entity_type="source",
            entity_id=record.id,
            source_id=record.id,
            outcome=status,
            metadata={
                "title": record.title,
                "section_count": record.section_count,
                "processing_state": record.processing_state,
                "approval_status": record.approval_status,
            },
        )
    return record.model_dump()
