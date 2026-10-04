"""Governance routes: knowledge-intelligence overview and the approval gate."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..analytics.event_store import AnalyticsEventStore
from ..analytics.governance_history import record_governance_snapshot
from ..external.registry import PublicContentRegistry
from ..governance.accepted import issue_key
from ..governance.intelligence import KnowledgeIntelligence
from ..governance.reanalysis import GovernanceReanalysisStore, build_reanalysis_report, latest_reanalysis_status
from ..governance.remediation import suggest_remediation
from ..governance.review_jobs import (
    InternalReviewCache,
    InternalReviewOptions,
    InternalReviewResult,
    InternalReviewStore,
    start_internal_review_job,
)
from ..iam.visibility import visible
from ..ingestion.store import SectionStore
from ..ontology.actions import ActionContext, ActionExecutionResult, ActionsEngine, ValidationResult, acting_person
from ..regulatory.review import RegulatoryReviewStore
from ..sources.register import SourceRegister, TextNotNamed
from .access import current_actor, need


class Decision(BaseModel):
    """An approval or rejection names the text decided on: the SHA-256 of the version the reviewer read (REF S23, S8)."""

    sha: str


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
    ontology_rebuilder: Callable[[], dict] | None = None,
    actions: ActionsEngine | None = None,
    dependencies: Sequence | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/governance", tags=["governance"], dependencies=list(dependencies or []))
    reanalysis_store = GovernanceReanalysisStore(register.base_dir)
    internal_review_store = InternalReviewStore()
    internal_review_cache = InternalReviewCache(register.base_dir / "governance_internal_review_cache.json")

    def _register_governance_actions() -> None:
        if actions is None:
            return
        actions.register_validation_rule("source_exists", _validate_source_exists)
        actions.register_validation_rule("names_current_text", _validate_names_current_text)
        actions.register_validation_rule("not_already_approved", _validate_not_already_approved)
        actions.register_validation_rule("not_already_rejected", _validate_not_already_rejected)
        actions.register_validation_rule("issue_fields_present", _validate_issue_fields_present)
        actions.register_validation_rule("non_empty_text", _validate_non_empty_text)
        actions.register_handler("approve_source", _approve_source_action)
        actions.register_handler("reject_source", _reject_source_action)
        actions.register_handler("accept_issue", _accept_issue_action)

    def _execute_operator_action(api_name: str, params: dict) -> dict | None:
        if actions is None:
            return None
        result = actions.execute(api_name, params, acting_person())
        if result.outcome == "ok":
            handler_result = result.result.get("handler", {})
            response = handler_result.get("response") if isinstance(handler_result, dict) else None
            return response if isinstance(response, dict) else result.model_dump()
        _raise_action_http_error(api_name, result)

    def _raise_action_http_error(api_name: str, result: ActionExecutionResult) -> None:
        if result.failed_rule == "source_exists":
            raise HTTPException(status_code=404, detail="Source not found.")
        if result.failed_rule in {"not_already_approved", "not_already_rejected", "names_current_text"}:
            raise HTTPException(status_code=409, detail=result.message)
        if result.outcome == "rejected":
            raise HTTPException(status_code=400, detail=result.message)
        raise HTTPException(status_code=500, detail=result.message or "Action failed.")

    def _validate_source_exists(context: ActionContext) -> ValidationResult:
        if register.get(str(context.params.get("source_id", ""))) is not None:
            return ValidationResult(rule="source_exists", passed=True, message="Source exists.")
        return ValidationResult(rule="source_exists", passed=False, message="Source not found.")

    def _validate_names_current_text(context: ActionContext) -> ValidationResult:
        """An early answer from the register's own check (REF S23, S8): the decision is refused here with a reason the
        caller can show; the register's decide checks the same again when it writes, and that is the one that counts."""
        reason = register.names_text(str(context.params.get("source_id", "")), context.params.get("sha"))
        if reason is None:
            return ValidationResult(rule="names_current_text", passed=True, message="The text named is the current one.")
        return ValidationResult(rule="names_current_text", passed=False, message=f"{reason}.")

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
        response = _set_status(register, str(context.params["source_id"]), "approved", sha=context.params.get("sha"))
        return {"response": response, "analytics_event": _source_status_event(response, "approved")}

    def _reject_source_action(context: ActionContext) -> dict:
        response = _set_status(register, str(context.params["source_id"]), "rejected", sha=context.params.get("sha"))
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

    _register_governance_actions()

    @router.get("/intelligence")
    def overview() -> dict:
        report = intelligence.run()
        if event_store is not None:
            record_governance_snapshot(report, event_store)  # the space's snapshot, whole
        return _visible_report(report)

    @router.get("/internal-review/latest")
    def internal_review_latest() -> dict:
        result = internal_review_store.latest()
        return _visible_review(result) if result is not None else {"status": None, "report": {}}

    @router.post("/internal-review/reviews", dependencies=[need("governance.reviews.run")])
    def internal_review(request: Request, options: InternalReviewOptions | None = None) -> dict:
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
            started_by=current_actor(request).id,
        )
        return _visible_review(result)

    @router.get("/internal-review/reviews/{job_id}", dependencies=[need("jobs.read_own")])
    def internal_review_status(request: Request, job_id: str) -> dict:
        """A review job by its id: for the person who started it (REF S14); everyone else gets 404, as for no job.
        Colleagues read the space's latest review instead."""
        result = internal_review_store.get(job_id)
        if result is None or result.status.started_by != current_actor(request).id:
            raise HTTPException(status_code=404, detail="Internal review job not found.")
        return _visible_review(result)

    @router.get("/reanalysis/latest")
    def reanalysis_latest() -> dict:
        if public_registry is None:
            raise HTTPException(status_code=500, detail="External source registry is not available.")
        return latest_reanalysis_status(reanalysis_store, register, public_registry)

    @router.post("/reanalysis", dependencies=[need("governance.scan.run")])
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

    @router.post("/issues/accept", dependencies=[need("governance.exceptions.accept")])
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
        record, text = register.read_record_text(source_id)  # read together (REF S23)
        if record is None:
            raise HTTPException(status_code=404, detail="Source not found.")
        return {"id": record.id, "title": record.title, "text": text.decode("utf-8", "replace")}

    @router.get("/remediation/{a_id}/{b_id}")
    def remediation(a_id: str, b_id: str) -> dict:
        docs = []
        for sid in (a_id, b_id):
            rec, text = register.read_record_text(sid)  # read together (REF S23)
            if rec is None:
                raise HTTPException(status_code=404, detail="Source not found.")
            docs.append({"id": rec.id, "title": rec.title, "text": text.decode("utf-8", "replace")})
        return suggest_remediation(docs[0], docs[1])

    @router.post("/sources/{source_id}/approve", dependencies=[need("documents.approve")])
    def approve(source_id: str, decision: Decision) -> dict:
        action_response = _execute_operator_action("approve_source", {"source_id": source_id, "sha": decision.sha})
        if action_response is not None:
            return action_response
        result = _set_status(register, source_id, "approved", event_store=event_store, sha=decision.sha)
        _refresh_process_registry()
        return result

    @router.post("/sources/{source_id}/reject", dependencies=[need("documents.reject")])
    def reject(source_id: str, decision: Decision) -> dict:
        action_response = _execute_operator_action("reject_source", {"source_id": source_id, "sha": decision.sha})
        if action_response is not None:
            return action_response
        result = _set_status(register, source_id, "rejected", event_store=event_store, sha=decision.sha)
        _refresh_process_registry()
        return result

    def _refresh_process_registry() -> None:
        # Persist the registry when the approved set changes, so read paths (which use
        # the pure derive) and the answer-routing (which reads the persisted file) stay current.
        if process_registry is not None:
            process_registry.build_from_sources(register)
        if ontology_rebuilder is not None:
            ontology_rebuilder()

    return router


def _visible_report(report: dict) -> dict:
    """The overview as the person may see it (REF S13): no issue, count or label about a document they may not read."""
    issues = {kind: [i for i in items if visible(i["source_id"]) and (not i.get("source_b_id") or visible(i["source_b_id"]))]
              for kind, items in report.get("issues", {}).items()}
    if issues == report.get("issues"):
        return report
    return {**report, "issues": issues, "categories": {k: len(v) for k, v in issues.items()},
            "total_issues": sum(len(v) for v in issues.values()),
            "source_summary": {sid: row for sid, row in report.get("source_summary", {}).items() if visible(sid)}}


def _about_visible(item: dict) -> bool:
    ids = [item.get("source_id"), item.get("source_b_id"), item.get("item_id"), *(item.get("source_ids") or [])]
    return all(visible(i) for i in ids if isinstance(i, str) and i)


def _visible_review(result: InternalReviewResult) -> dict:
    """A review as the person may see it (REF S13, S16): its report as the overview is shown, and no progress item,
    finding or count about a document they may not read."""
    data = result.model_dump()
    status, findings = data["status"], [f for f in data.get("findings", []) if _about_visible(f)]
    items = [i for i in status.get("items", []) if _about_visible(i)]
    if data.get("report"):
        data["report"] = _visible_report(data["report"])
    if len(items) == len(status.get("items", [])) and len(findings) == len(data.get("findings", [])):
        return data
    current = status.get("current_item")
    status.update(items=items, item_total=len(items), item_completed=sum(1 for i in items if i["status"] == "completed"),
                  current_item=current if current and _about_visible(current) else None, finding_count=len(findings))
    data["findings"] = findings
    return data


def _set_status(register: SourceRegister, source_id: str, status: str, event_store: AnalyticsEventStore | None = None,
                sha: str | None = None) -> dict:
    """A decision through the register's decide (REF S23, S8): it names the text decided on, under the workspace's lock
    taken at the door (S7)."""
    if register.get(source_id) is None:
        raise HTTPException(status_code=404, detail="Source not found.")
    try:
        record = register.decide(source_id, status, sha)
    except TextNotNamed as refused:
        raise HTTPException(status_code=409, detail=f"{refused}.") from None
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
