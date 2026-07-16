"""Governance routes: knowledge-intelligence overview and the approval gate."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..analytics.event_store import AnalyticsEventStore
from ..analytics.governance_history import record_governance_snapshot
from ..compliance.client import ComplianceReasoningClient, ComplianceReasoningUnavailable
from ..compliance.payload import build_internal_source_review_payload
from ..external.registry import PublicContentRegistry
from ..governance.accepted import issue_key
from ..governance.intelligence import KnowledgeIntelligence
from ..governance.reanalysis import GovernanceReanalysisStore, build_reanalysis_report, latest_reanalysis_status
from ..governance.remediation import suggest_remediation
from ..governance.review_jobs import (
    InternalReviewCache,
    InternalReviewOptions,
    InternalReviewStore,
    start_internal_review_job,
)
from ..ingestion.service import NotIngestableError, ingest_source
from ..ingestion.store import SectionStore
from ..ontology.actions import ActionActor, ActionContext, ActionExecutionResult, ActionsEngine, ValidationResult
from ..regulatory.review import RegulatoryReviewStore
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
    regulatory_reviews: RegulatoryReviewStore | None = None,
    public_registry: PublicContentRegistry | None = None,
    event_store: AnalyticsEventStore | None = None,
    process_registry=None,
    compliance_reasoning: ComplianceReasoningClient | None = None,
    ontology_rebuilder: Callable[[], dict] | None = None,
    actions: ActionsEngine | None = None,
    dependencies: Sequence | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/governance", tags=["governance"], dependencies=list(dependencies or []))
    reanalysis_store = GovernanceReanalysisStore(register.base_dir)
    internal_review_store = InternalReviewStore()
    internal_review_cache = InternalReviewCache(register.base_dir / "governance_internal_review_cache.json")
    latest_internal_reasoning_job_id = ""

    def _register_governance_actions() -> None:
        if actions is None:
            return
        actions.register_validation_rule("source_exists", _validate_source_exists)
        actions.register_validation_rule("not_already_approved", _validate_not_already_approved)
        actions.register_validation_rule("not_already_rejected", _validate_not_already_rejected)
        actions.register_validation_rule("issue_fields_present", _validate_issue_fields_present)
        actions.register_validation_rule("non_empty_text", _validate_non_empty_text)
        actions.register_handler("approve_source", _approve_source_action)
        actions.register_handler("reject_source", _reject_source_action)
        actions.register_handler("accept_issue", _accept_issue_action)
        actions.register_handler("save_document", _save_document_action)

    def _execute_operator_action(api_name: str, params: dict) -> dict | None:
        if actions is None:
            return None
        result = actions.execute(api_name, params, ActionActor(type="operator", id="operator"))
        if result.outcome == "ok":
            handler_result = result.result.get("handler", {})
            response = handler_result.get("response") if isinstance(handler_result, dict) else None
            return response if isinstance(response, dict) else result.model_dump()
        _raise_action_http_error(api_name, result)

    def _raise_action_http_error(api_name: str, result: ActionExecutionResult) -> None:
        if result.failed_rule == "source_exists":
            raise HTTPException(status_code=404, detail="Source not found.")
        if result.failed_rule in {"not_already_approved", "not_already_rejected"}:
            raise HTTPException(status_code=409, detail=result.message)
        if result.outcome == "rejected":
            raise HTTPException(status_code=400, detail=result.message)
        status_code = 400 if api_name == "save_document" else 500
        raise HTTPException(status_code=status_code, detail=result.message or "Action failed.")

    def _validate_source_exists(context: ActionContext) -> ValidationResult:
        if register.get(str(context.params.get("source_id", ""))) is not None:
            return ValidationResult(rule="source_exists", passed=True, message="Source exists.")
        return ValidationResult(rule="source_exists", passed=False, message="Source not found.")

    def _validate_not_already_approved(context: ActionContext) -> ValidationResult:
        record = register.get(str(context.params.get("source_id", "")))
        if record is not None and record.approval_status == "approved":
            return ValidationResult(rule="not_already_approved", passed=False, message="Source is already approved.")
        return ValidationResult(rule="not_already_approved", passed=True, message="Source is not already approved.")

    def _validate_not_already_rejected(context: ActionContext) -> ValidationResult:
        record = register.get(str(context.params.get("source_id", "")))
        if record is not None and record.approval_status == "rejected":
            return ValidationResult(rule="not_already_rejected", passed=False, message="Source is already rejected.")
        return ValidationResult(rule="not_already_rejected", passed=True, message="Source is not already rejected.")

    def _validate_issue_fields_present(context: ActionContext) -> ValidationResult:
        missing = [
            key
            for key in ("source_id", "check", "detail")
            if not str(context.params.get(key, "")).strip()
        ]
        if missing:
            return ValidationResult(
                rule="issue_fields_present",
                passed=False,
                message=f"Missing issue field(s): {', '.join(missing)}.",
            )
        return ValidationResult(rule="issue_fields_present", passed=True, message="Issue fields present.")

    def _validate_non_empty_text(context: ActionContext) -> ValidationResult:
        if str(context.params.get("text", "")).strip():
            return ValidationResult(rule="non_empty_text", passed=True, message="Document text present.")
        return ValidationResult(rule="non_empty_text", passed=False, message="Document text cannot be empty.")

    def _approve_source_action(context: ActionContext) -> dict:
        response = _set_status(register, str(context.params["source_id"]), "approved")
        return {"response": response, "analytics_event": _source_status_event(response, "approved")}

    def _reject_source_action(context: ActionContext) -> dict:
        response = _set_status(register, str(context.params["source_id"]), "rejected")
        return {"response": response, "analytics_event": _source_status_event(response, "rejected")}

    def _accept_issue_action(context: ActionContext) -> dict:
        if accepted is None:
            raise RuntimeError("Accepting issues is not available.")
        source_id = str(context.params["source_id"])
        check = str(context.params["check"])
        detail = str(context.params["detail"])
        accepted.accept(source_id, check, detail)
        return {
            "response": {"accepted": True},
            "analytics_event": {
                "event_type": "governance_issue_accepted",
                "actor_type": "operator",
                "entity_type": "governance_issue",
                "entity_id": issue_key(source_id, check, detail),
                "source_id": source_id,
                "outcome": "accepted",
                "metadata": {"check": check},
            },
        }

    def _save_document_action(context: ActionContext) -> dict:
        response = _save_document_now(str(context.params["source_id"]), str(context.params["text"]))
        record = register.get(str(context.params["source_id"]))
        event_record = record.model_dump() if record is not None else response
        return {"response": response, "analytics_event": _source_edited_event(event_record, str(context.params["text"]))}

    _register_governance_actions()

    @router.get("/intelligence")
    def overview() -> dict:
        report = intelligence.run()
        if event_store is not None:
            record_governance_snapshot(report, event_store)
        return report

    @router.get("/internal-review/latest")
    def internal_review_latest() -> dict:
        if compliance_reasoning is not None and compliance_reasoning.enabled and latest_internal_reasoning_job_id:
            return _internal_reasoning_result(compliance_reasoning, latest_internal_reasoning_job_id)
        result = internal_review_store.latest()
        return result.model_dump() if result is not None else {"status": None, "report": {}}

    @router.post("/internal-review/reviews")
    def internal_review(options: InternalReviewOptions | None = None) -> dict:
        nonlocal latest_internal_reasoning_job_id
        if compliance_reasoning is not None and compliance_reasoning.enabled:
            if section_store is None:
                raise HTTPException(status_code=500, detail="Internal source review is not available.")
            review_options = options or InternalReviewOptions()
            payload = build_internal_source_review_payload(
                register,
                section_store,
                options=_internal_reasoning_options(review_options),
            )
            try:
                result = compliance_reasoning.create_review(payload)
            except ComplianceReasoningUnavailable as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            status = result.get("status", {})
            latest_internal_reasoning_job_id = str(status.get("job_id", ""))
            if event_store is not None:
                event_store.record(
                    "compliance_reasoning_review_requested",
                    actor_type="operator",
                    entity_type="compliance_review",
                    entity_id=latest_internal_reasoning_job_id,
                    outcome=status.get("status", "unknown"),
                    metadata={
                        "review_mode": "internal_vs_internal",
                        "internal_documents": len(payload["internal_documents"]),
                        "pair_total": status.get("pair_total", 0),
                    },
                )
            return _internal_reasoning_result_from_status(result.get("status", {}), result.get("findings", []))

        def on_complete(report: dict) -> None:
            if event_store is not None:
                record_governance_snapshot(report, event_store)

        result = start_internal_review_job(
            store=internal_review_store,
            cache=internal_review_cache,
            register=register,
            intelligence=intelligence,
            options=options or InternalReviewOptions(),
            on_complete=on_complete,
        )
        return result.model_dump()

    @router.get("/internal-review/reviews/{job_id}")
    def internal_review_status(job_id: str) -> dict:
        if compliance_reasoning is not None and compliance_reasoning.enabled and job_id.startswith("cr-"):
            return _internal_reasoning_result(compliance_reasoning, job_id)
        result = internal_review_store.get(job_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Internal review job not found.")
        return result.model_dump()

    @router.post("/internal-review/reviews/{job_id}/cancel")
    def internal_review_cancel(job_id: str) -> dict:
        if compliance_reasoning is None or not compliance_reasoning.enabled or not job_id.startswith("cr-"):
            raise HTTPException(status_code=409, detail="This Internal Source Review job cannot be cancelled from the reasoning service.")
        try:
            status = compliance_reasoning.cancel_review(job_id)
        except ComplianceReasoningUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return _internal_reasoning_result_from_status(status, [])

    @router.get("/reanalysis/latest")
    def reanalysis_latest() -> dict:
        if public_registry is None:
            raise HTTPException(status_code=500, detail="External source registry is not available.")
        return latest_reanalysis_status(reanalysis_store, register, public_registry)

    @router.post("/reanalysis")
    def reanalysis() -> dict:
        if section_store is None or regulatory_reviews is None or public_registry is None:
            raise HTTPException(status_code=500, detail="Governance re-analysis is not available.")
        report = build_reanalysis_report(
            register,
            intelligence,
            section_store,
            regulatory_reviews,
            public_registry,
            accepted=accepted,
            previous=reanalysis_store.latest(),
        )
        return reanalysis_store.save(report)

    @router.post("/issues/accept")
    def accept_issue(ref: IssueRef) -> dict:
        action_response = _execute_operator_action("accept_issue", ref.model_dump())
        if action_response is not None:
            return action_response
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
        action_response = _execute_operator_action("save_document", {"source_id": source_id, "text": edit.text})
        if action_response is not None:
            return action_response
        response = _save_document_now(source_id, edit.text)
        _refresh_process_registry()
        if event_store is not None:
            record = register.get(source_id)
            event_store.record(**_source_edited_event(record.model_dump() if record is not None else response, edit.text))
        return response

    @router.post("/sources/{source_id}/approve")
    def approve(source_id: str) -> dict:
        action_response = _execute_operator_action("approve_source", {"source_id": source_id})
        if action_response is not None:
            return action_response
        result = _set_status(register, source_id, "approved", event_store=event_store)
        _refresh_process_registry()
        return result

    @router.post("/sources/{source_id}/reject")
    def reject(source_id: str) -> dict:
        action_response = _execute_operator_action("reject_source", {"source_id": source_id})
        if action_response is not None:
            return action_response
        result = _set_status(register, source_id, "rejected", event_store=event_store)
        _refresh_process_registry()
        return result

    def _refresh_process_registry() -> None:
        # Persist the registry when the approved set changes, so read paths (which use
        # the pure derive) and the answer-routing (which reads the persisted file) stay current.
        if process_registry is not None:
            process_registry.build_from_sources(register)
        if ontology_rebuilder is not None:
            ontology_rebuilder()

    def _save_document_now(source_id: str, text: str) -> dict:
        record = register.get(source_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Source not found.")
        if section_store is None:
            raise RuntimeError("Editing is not available.")
        content = text.encode("utf-8")
        register.write_content(source_id, content)
        register.update(
            source_id,
            size_bytes=len(content),
            content_sha256=hashlib.sha256(content).hexdigest(),
            version=record.version + 1,
        )
        try:
            updated = ingest_source(register, section_store, source_id)  # rebuild sections from edited content
        except NotIngestableError as exc:
            raise ValueError(str(exc)) from exc
        return {"id": updated.id, "title": updated.title, "section_count": updated.section_count}

    return router


def _set_status(register: SourceRegister, source_id: str, status: str, event_store: AnalyticsEventStore | None = None) -> dict:
    record = register.update(source_id, approval_status=status)
    if record is None:
        raise HTTPException(status_code=404, detail="Source not found.")
    if event_store is not None:
        event_store.record(**_source_status_event(record.model_dump(), status))
    return record.model_dump()


def _source_status_event(record: dict, status: str) -> dict:
    return {
        "event_type": "source_approved" if status == "approved" else "source_rejected",
        "actor_type": "operator",
        "entity_type": "source",
        "entity_id": record["id"],
        "source_id": record["id"],
        "outcome": status,
        "metadata": {
            "title": record["title"],
            "section_count": record["section_count"],
            "processing_state": record["processing_state"],
            "approval_status": record["approval_status"],
        },
    }


def _source_edited_event(record: dict, text: str) -> dict:
    return {
        "event_type": "source_edited",
        "actor_type": "operator",
        "entity_type": "source",
        "entity_id": record["id"],
        "source_id": record["id"],
        "metadata": {
            "title": record["title"],
            "section_count": record["section_count"],
            "size_bytes": len(text.encode("utf-8")),
            "processing_state": record.get("processing_state", ""),
            "approval_status": record.get("approval_status", ""),
        },
    }


def _internal_reasoning_options(options: InternalReviewOptions) -> dict:
    depth_profiles = {
        "fast": {
            "min_alignment_score": 0.28,
            "min_pair_relevance_score": 0.18,
            "max_agent_calls_per_pair": 0,
            "max_findings": 50,
        },
        "balanced": {
            "min_alignment_score": 0.32,
            "min_pair_relevance_score": 0.2,
            "max_agent_calls_per_pair": 2,
            "max_findings": 75,
        },
        "deep": {
            "min_alignment_score": 0.18,
            "min_pair_relevance_score": 0.12,
            "max_agent_calls_per_pair": 0,
            "max_findings": 100,
        },
    }
    profile = depth_profiles[options.review_depth]
    return {
        "include_supported_findings": False,
        "include_unsupported_internal_claims": False,
        "include_missing_obligations": False,
        "include_not_related_pairs": False,
        "min_alignment_score": profile["min_alignment_score"],
        "min_pair_relevance_score": profile["min_pair_relevance_score"],
        "min_contradiction_alignment_score": 0.3,
        "max_findings": profile["max_findings"],
        "force_rerun": options.force_rerun,
        "review_depth": options.review_depth,
        "throttle_deep": options.throttle_deep,
        "max_agent_calls_per_pair": profile["max_agent_calls_per_pair"],
    }


def _internal_reasoning_result(client: ComplianceReasoningClient, job_id: str) -> dict:
    try:
        status = client.review_status(job_id)
        findings = client.review_findings(job_id).get("findings", []) if status.get("status") == "completed" else []
    except ComplianceReasoningUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _internal_reasoning_result_from_status(status, findings)


def _internal_reasoning_result_from_status(status: dict, findings: list | None = None) -> dict:
    return {
        "status": _internal_reasoning_status(status),
        "report": {},
        "findings": findings or [],
    }


def _internal_reasoning_status(status: dict) -> dict:
    pairs = status.get("pairs", [])
    pair_items = [_internal_pair_item(pair) for pair in pairs if isinstance(pair, dict)]
    current_pair = status.get("current_pair")
    current_item = _internal_pair_item(current_pair) if isinstance(current_pair, dict) else None
    audit = status.get("audit", {})
    audit = audit if isinstance(audit, dict) else {}
    cache_status = "pending"
    if status.get("cache_bypass_count", 0):
        cache_status = "bypassed"
    elif status.get("cache_hit_count", 0) and status.get("cache_hit_count", 0) == status.get("pair_total", 0):
        cache_status = "hit"
    elif status.get("cache_miss_count", 0):
        cache_status = "miss"
    return {
        "job_id": status.get("job_id", ""),
        "status": status.get("status", "queued"),
        "created_at": status.get("created_at", ""),
        "started_at": status.get("started_at", ""),
        "completed_at": status.get("completed_at", ""),
        "failure_reason": status.get("failure_reason", ""),
        "item_total": status.get("pair_total", len(pair_items)),
        "item_completed": status.get("pair_completed", 0),
        "progress_percent": status.get("progress_percent", 0),
        "elapsed_seconds": status.get("elapsed_seconds", 0.0),
        "cache_status": cache_status,
        "current_item": current_item,
        "items": pair_items,
        "estimated_remaining_seconds": status.get("estimated_remaining_seconds", 0.0),
        "estimated_remaining_label": status.get("estimated_remaining_label", ""),
        "eta_confidence": status.get("eta_confidence", "unknown"),
        "finding_count": status.get("finding_count", 0),
        "generated_finding_count": status.get("generated_finding_count", status.get("finding_count", 0)),
        "consolidated_finding_count": status.get("consolidated_finding_count", status.get("finding_count", 0)),
        "finding_limit": status.get("finding_limit", 0),
        "truncated_finding_count": status.get("truncated_finding_count", 0),
        "findings_truncated": status.get("findings_truncated", False),
        "review_mode": status.get("review_mode", "internal_vs_internal"),
        "review_depth": status.get("review_depth", "fast"),
        "throttle_deep": status.get("throttle_deep", False),
        "engine": audit.get("engine", ""),
        "model_profile": audit.get("model_profile", ""),
        "prompt_version": audit.get("prompt_version", ""),
        "cancel_requested": status.get("cancel_requested", False),
    }


def _internal_pair_item(pair: dict) -> dict:
    left = pair.get("external_title", "Internal source A")
    right = pair.get("internal_title", "Internal source B")
    status = pair.get("status", "queued")
    return {
        "item_id": pair.get("pair_id", ""),
        "title": f"{left} vs {right}",
        "status": "completed" if status == "not_related" else status,
        "issue_count": pair.get("finding_count", 0),
    }
