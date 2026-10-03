"""Good, odd or wrong on a written answer, and an improvement action from a wrong one (REF S20)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from ..analytics.feedback import AnswerFeedbackCreate, AnswerFeedbackStore
from ..analytics.improvement import ImprovementActionCreate, ImprovementActionStore
from ..analytics.log import UsageLog
from ..ontology.actions import ActionsEngine, acting_person
from .access import current_actor, need, require

DEFAULT_ACTION = "Review the approved sources behind this answer, then correct or extend them."


def raise_improvement_action(actions: ActionsEngine | None, base_dir: str | Path, payload: ImprovementActionCreate) -> dict:
    """Through the actions engine when there is one, as the analytics route creates an action: audited, with its
    analytics event. The caller has checked analytics.improvements.create. An action still open for the same answer or
    turn is returned instead of a second one."""
    for existing in ImprovementActionStore(base_dir).list():
        if (existing.trigger_type, existing.trigger_ref) == (payload.trigger_type, payload.trigger_ref) \
                and existing.status not in ("closed", "wont_fix"):
            return existing.model_dump()
    if actions is None:
        return ImprovementActionStore(base_dir).create(payload).model_dump()
    result = actions.execute("create_improvement_action", payload.model_dump(), acting_person())
    if result.outcome != "ok":
        raise HTTPException(status_code=400, detail=result.message or "Improvement action was not created.")
    return result.result["handler"]["action"]


def feedback_action(trigger_ref: str, verdict: str, note: str, question: str) -> ImprovementActionCreate:
    """The improvement action a mark raises: the note says what to change, the question what was asked."""
    note = " ".join(note.split())
    return ImprovementActionCreate(
        trigger_type="answer_feedback",
        trigger_ref=trigger_ref[:200],
        recommended_action=(note if len(note) >= 2 else DEFAULT_ACTION)[:500],
        note=f"Marked {verdict}. Asked: {' '.join(question.split())}"[:500],
    )


def build_feedback_router(usage_log: UsageLog, store: AnswerFeedbackStore, actions: ActionsEngine | None,
                          base_dir: str | Path) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["assistant"])

    @router.post("/answers/{answer_id}/feedback", dependencies=[need("knowledge.ask")])
    def answer_feedback(answer_id: str, body: AnswerFeedbackCreate, request: Request) -> dict:
        """Whoever may ask may rate their own answers; another person's answer is 404, as one that does not exist."""
        actor = current_actor(request)
        entry = usage_log.get(answer_id)
        if entry is None or (entry.actor_id is not None and entry.actor_id != actor.id):
            raise HTTPException(status_code=404, detail="No such answer")
        action = None
        if body.raise_action:
            if body.verdict == "good":
                raise HTTPException(status_code=400, detail="Only an odd or wrong answer raises an improvement action")
            require(request, "analytics.improvements.create")
            action = raise_improvement_action(actions, base_dir, feedback_action(answer_id, body.verdict, body.note, entry.question))
        row = store.record(answer_id, body.verdict, body.note, actor.id, action["id"] if action else None)
        return {"feedback": row, "action_id": action["id"] if action else None}

    return router
