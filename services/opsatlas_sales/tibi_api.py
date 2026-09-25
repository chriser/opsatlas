"""Tibi inside OpsAtlas: the control panel's API for Tibi's knowledge and governance-interview answers.

The same operations the separate review page used, behind the OpsAtlas operator sign-in instead of the
workspace key, so the control panel can offer them as its own pages: Tibi knowledge (records, conversation
style, spoken answers, interview contributions, product ontology) and, on the Governance page, the answers
the Human gave Tibi in governance interviews. Every decision still goes through the same Knowledge and
GovernanceDesk methods; nothing here approves on its own.
"""
import json
import os
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

# The local voice service; a disposable copy (the latency replay) runs its own on another port.
VOICE = os.environ.get('SME_TIBI_VOICE_URL', 'http://127.0.0.1:8773')


class Review(BaseModel):
    expected_hash: str
    approve: bool


class Resolution(BaseModel):
    expected_hash: str
    decision: str
    related: dict
    reason: str


class Proposal(BaseModel):
    session_id: str
    turn_id: str
    text: str
    status: str
    expected_hash: str | None = None
    wording_confirmed: bool


def interview_turns(voice_db):
    """Product-interview contributions saved by the voice service, read without writing to its ledger."""
    if not voice_db.exists():
        return []
    with sqlite3.connect(f'file:{voice_db}?mode=ro', uri=True) as connection:
        rows = connection.execute('select id, data from sessions').fetchall()
    return [{**turn, 'session_id': identifier} for identifier, data in rows
            for turn in json.loads(data).get('product_turns', [])]


def build_router(app, knowledge, ontology, desk, root, credential, voice=VOICE):
    from assistant.api.routes_auth import make_require_auth

    router = APIRouter(prefix='/api/tibi', dependencies=[Depends(make_require_auth(app.state.auth))])
    voice_db = root / 'voice' / 'interviews.sqlite'

    def conflict(fn):
        try:
            return fn()
        except (ValueError, TypeError, KeyError) as exc:
            raise HTTPException(409, str(exc)) from exc

    @router.get('/status')
    def status():
        # The voice client is embedded in the control panel; it runs in its own local service.
        return {'available': True, 'voice_url': voice + '/conversation?social=1&sales=1&embed=1'}

    @router.get('/knowledge')
    def records():
        rows = knowledge.catalog()
        return {'records': rows, 'digest': knowledge.digest(rows)}

    @router.post('/knowledge/{identifier}/review')
    def review(identifier: str, data: Review):
        return conflict(lambda: knowledge.decide(identifier, data.expected_hash, data.approve))

    @router.post('/knowledge/{identifier}/resolve')
    def resolve(identifier: str, data: Resolution):
        return conflict(lambda: knowledge.adjudicate(identifier, data.expected_hash, data.decision, data.related, data.reason))

    @router.get('/sources/{identifier}')
    def source(identifier: str):
        record = app.state.register.get(identifier)
        if not record:
            raise HTTPException(404)
        return {'title': record.title, 'text': app.state.register.read_content(identifier).decode('utf-8', 'replace')}

    @router.get('/spoken')
    def spoken():
        return {'variants': knowledge.spoken_catalog()}

    @router.post('/spoken/{identifier}/review')
    def review_spoken(identifier: str, data: Review):
        return conflict(lambda: knowledge.review_spoken(identifier, data.expected_hash, data.approve))

    @router.post('/spoken/draft')
    async def draft_spoken(request: Request):
        # Drafts are written by the local model and stored pending, through the workspace's own API.
        from services.sme_interviewer.tibi import Tibi
        return await Tibi([], credential, str(request.base_url).rstrip('/')).draft_spoken()

    @router.get('/contributions')
    def contributions():
        return {'turns': interview_turns(voice_db)}

    @router.post('/proposals')
    def propose(data: Proposal):
        turn = next((t for t in interview_turns(voice_db)
                     if t['session_id'] == data.session_id and t['id'] == data.turn_id), None)
        if turn is None:
            raise HTTPException(400, 'Select a saved contribution')
        # Attribution and the original transcript come from the saved interview, never the browser.
        payload = {k: turn[k] for k in ('contributor', 'topic', 'question', 'raw_text', 'issue')}
        payload.update(session_id=data.session_id, turn_id=data.turn_id, text=data.text, status=data.status,
                       expected_hash=data.expected_hash, wording_confirmed=data.wording_confirmed)
        return conflict(lambda: knowledge.propose(payload))

    @router.get('/ontology')
    def product_ontology():
        ontology.ensure(knowledge.catalog())
        return ontology.export()

    @router.get('/governance/answers')
    def governance_answers():
        return {'answers': desk.answers()}

    @router.get('/governance/agenda')
    def governance_agenda():
        agenda = desk.agenda()
        return {'issues': agenda['issues'], 'total': agenda['total'],
                'answered': sum(1 for i in agenda['items'] if i.get('answer')),
                'open': sum(1 for i in agenda['items'] if not i.get('answer'))}

    @router.post('/governance/answers/{identifier}/review')
    def governance_review(identifier: str, data: Review):
        return conflict(lambda: desk.review(identifier, data.expected_hash, data.approve))

    return router
