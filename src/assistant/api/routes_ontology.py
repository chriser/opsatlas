"""Ontology API routes."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ..analytics.event_store import AnalyticsEventStore
from ..ontology.actions import ActionActor, ActionsEngine
from ..ontology.agent import OntologyAgent
from ..ontology.proposals import PendingActionProposal, PendingActionStore
from ..ontology.query import OntologyQueryService
from ..ontology.store import OntologyStore


class ActionExecuteRequest(BaseModel):
    params: dict[str, Any] = Field(default_factory=dict)


class AgentRunRequest(BaseModel):
    question: str


class DeclineProposalRequest(BaseModel):
    reason: str = ""


def build_ontology_router(
    store: OntologyStore,
    *,
    rebuild: Callable[[], dict[str, Any]] | None = None,
    actions: ActionsEngine | None = None,
    agent: OntologyAgent | None = None,
    proposals: PendingActionStore | None = None,
    event_store: AnalyticsEventStore | None = None,
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

    @router.post("/agent/runs")
    def run_agent(body: AgentRunRequest) -> dict[str, Any]:
        if agent is None or proposals is None:
            raise HTTPException(status_code=503, detail="Ontology agent is not configured.")
        trace = agent.run(body.question.strip())
        created = proposals.add_from_trace(trace)
        _record_event(
            event_store,
            "agent_run_completed",
            actor_type="operator",
            entity_type="agent_run",
            entity_id=trace.run_id,
            outcome=trace.stopped_reason,
            metadata={"step_count": len(trace.steps), "proposal_count": len(created)},
        )
        for proposal in created:
            _record_event(
                event_store,
                "action_proposed",
                actor_type="agent",
                actor_id=trace.run_id,
                entity_type="action_proposal",
                entity_id=proposal.proposal_id,
                outcome="pending",
                metadata={"action": proposal.action},
            )
        payload = trace.model_dump()
        payload["persisted_proposals"] = [item.model_dump() for item in created]
        return payload

    @router.get("/proposals")
    def list_proposals() -> dict[str, Any]:
        if proposals is None:
            raise HTTPException(status_code=503, detail="Ontology proposals are not configured.")
        rows = proposals.list()
        return {"proposals": [item.model_dump() for item in rows], "count": len(rows)}

    @router.post("/proposals/{proposal_id}/approve")
    def approve_proposal(proposal_id: str) -> dict[str, Any]:
        if proposals is None or actions is None:
            raise HTTPException(status_code=503, detail="Ontology proposals are not configured.")
        proposal = _require_proposal(proposals, proposal_id)
        if proposal.status == "approved":
            return {"proposal": proposal.model_dump(), "already_approved": True}
        if proposal.status == "declined":
            raise HTTPException(status_code=409, detail="Declined proposals cannot be approved.")
        try:
            execution = actions.execute(
                proposal.action,
                proposal.params,
                ActionActor(type="agent", id=proposal.agent_run_id, approved_by="operator"),
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if execution.outcome == "rejected":
            raise HTTPException(status_code=400, detail=execution.message)
        if execution.outcome == "error":
            raise HTTPException(status_code=500, detail=execution.message)
        approved = proposals.mark_approved(proposal_id, execution.execution_id)
        _record_event(
            event_store,
            "action_approved",
            actor_type="operator",
            entity_type="action_proposal",
            entity_id=proposal_id,
            outcome="approved",
            metadata={"action": approved.action, "execution_id": execution.execution_id},
        )
        return {"proposal": approved.model_dump(), "execution": execution.model_dump(), "already_approved": False}

    @router.post("/proposals/{proposal_id}/decline")
    def decline_proposal(proposal_id: str, body: DeclineProposalRequest | None = None) -> dict[str, Any]:
        if proposals is None:
            raise HTTPException(status_code=503, detail="Ontology proposals are not configured.")
        proposal = _require_proposal(proposals, proposal_id)
        if proposal.status == "approved":
            raise HTTPException(status_code=409, detail="Approved proposals cannot be declined.")
        if proposal.status == "declined":
            return {"proposal": proposal.model_dump(), "already_declined": True}
        declined = proposals.decline(proposal_id, (body or DeclineProposalRequest()).reason)
        _record_event(
            event_store,
            "action_declined",
            actor_type="operator",
            entity_type="action_proposal",
            entity_id=proposal_id,
            outcome="declined",
            metadata={"action": declined.action},
        )
        return {"proposal": declined.model_dump(), "already_declined": False}

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


def _require_proposal(store: PendingActionStore, proposal_id: str) -> PendingActionProposal:
    proposal = store.get(proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail="Pending action proposal not found.")
    return proposal


def _record_event(event_store: AnalyticsEventStore | None, event_type: str, **kwargs) -> None:
    if event_store is not None:
        event_store.record(event_type, **kwargs)


def _property_filters(request: Request) -> dict[str, str]:
    filters: dict[str, str] = {}
    for key, value in request.query_params.multi_items():
        if key.startswith("property."):
            property_name = key.removeprefix("property.")
            if property_name:
                filters[property_name] = value
    return filters
