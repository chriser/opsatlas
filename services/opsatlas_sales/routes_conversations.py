"""The conversation log's review routes (OBS F2; AUDIT F13, from create_sales_app).

Conversations belong to a person (REF S14): those who may read everyone's conversations see them all; everyone else
sees, opens and exports only the ones they started (the gateway records who, in tibi-owners.json). Another person's
conversation answers 404, as one that does not exist."""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from assistant.api.access import current_actor, need


class TurnReview(BaseModel):
    verdict: str | None = None
    note: str = ''


def build_conversations_router(root, activity, owners=None, space_id=None) -> APIRouter:
    router = APIRouter()

    # The conversation log (OBS F2): Tibi writes each turn; the Human reviews sessions and marks turns here.
    from . import conversations

    def everyone(request):
        return current_actor(request).can('conversations.read_all', space_id)

    def own(request, identifier):
        """The conversation, if this person may open it; 404 otherwise."""
        if not everyone(request) and (owners is None or owners.owner(identifier) != current_actor(request).id):
            raise HTTPException(404, 'No such conversation')
        try:
            return conversations.session(root, identifier)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc

    @router.get('/api/conversations', dependencies=[need('conversations.read_own')])
    def conversation_sessions(request: Request, days: int = 30):
        rows = conversations.sessions(root, min(max(days, 1), 365))
        if not everyone(request):
            me = current_actor(request).id
            rows = [s for s in rows if owners is not None and owners.owner(str(s['session'])) == me]
        return {'sessions': rows, 'everyone': everyone(request)}

    @router.get('/api/conversations/flagged', dependencies=[need('conversations.read_all')])
    def conversation_flags():
        return {'turns': conversations.flagged(root)}

    @router.get('/api/conversations/{identifier}', dependencies=[need('conversations.read_own')])
    def conversation(identifier: str, request: Request):
        return own(request, identifier)

    @router.get('/api/conversations/{identifier}/export', dependencies=[need('conversations.export')])
    def conversation_export(identifier: str, request: Request):
        """One conversation as a readable transcript: what was heard and what Tibi replied, turn by turn."""
        text = conversations.transcript(own(request, identifier))
        activity.write('export', event='exported a conversation', session=identifier)
        return PlainTextResponse(text, media_type='text/markdown',
                                 headers={'Content-Disposition': f'attachment; filename="conversation-{identifier[:40]}.md"'})

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
