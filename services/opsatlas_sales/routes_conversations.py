"""The conversation log's review routes (OBS F2; AUDIT F13, from create_sales_app)."""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from assistant.api.access import current_actor, need


class TurnReview(BaseModel):
    verdict: str | None = None
    note: str = ''


def build_conversations_router(root, activity) -> APIRouter:
    router = APIRouter()

    # The conversation log (OBS F2): Tibi writes each turn; the Human reviews sessions and marks turns here.
    from . import conversations

    @router.get('/api/conversations', dependencies=[need('conversations.read_all')])
    def conversation_sessions(days: int = 30):
        return {'sessions': conversations.sessions(root, min(max(days, 1), 365))}

    @router.get('/api/conversations/flagged', dependencies=[need('conversations.read_all')])
    def conversation_flags():
        return {'turns': conversations.flagged(root)}

    @router.get('/api/conversations/{identifier}', dependencies=[need('conversations.read_all')])
    def conversation(identifier: str):
        try:
            return conversations.session(root, identifier)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc

    @router.put('/api/conversations/{identifier}/turns/{turn}/review', dependencies=[need('conversations.review')])
    def review_turn(identifier: str, turn: int, data: TurnReview, request: Request):
        try:
            row = conversations.review(root, identifier, turn, data.verdict, data.note, current_actor(request).display_name)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        activity.write('review', event='marked a turn', session=identifier, turn=turn, verdict=data.verdict)
        return row
    return router
