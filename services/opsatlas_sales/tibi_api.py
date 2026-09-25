"""OpsAtlas's side of Tibi: the control panel's API for the knowledge Tibi uses and the answers it collects.

Behind the OpsAtlas operator sign-in: records, conversation style, spoken answers, the product ontology,
and the governance-interview answers approved on the Governance page. These are OpsAtlas data; every
decision goes through the Knowledge and GovernanceDesk methods, and nothing here approves on its own.

Tibi itself is a separate service. OpsAtlas never imports its code or reads its storage: it checks the
service's health over HTTP, and the control panel reaches its API through the gateway (tibi_proxy).
"""
import os

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel


def voice_url():
    """The Tibi service's address; a disposable copy (the latency replay, a UI check) runs its own on another port."""
    return os.environ.get('SME_TIBI_VOICE_URL') or 'http://127.0.0.1:8773'


class Review(BaseModel):
    expected_hash: str
    approve: bool


class Resolution(BaseModel):
    expected_hash: str
    decision: str
    related: dict
    reason: str


def build_router(app, knowledge, ontology, desk, voice):
    from assistant.api.routes_auth import make_require_auth

    router = APIRouter(prefix='/api/tibi', dependencies=[Depends(make_require_auth(app.state.auth))])

    def conflict(fn):
        try:
            return fn()
        except (ValueError, TypeError, KeyError) as exc:
            raise HTTPException(409, str(exc)) from exc

    @router.get('/status')
    async def status():
        """Whether the Tibi service is running; the control panel shows Tibi either way."""
        try:
            async with httpx.AsyncClient(timeout=1.5, trust_env=False) as client:
                health = (await client.get(voice.rstrip('/') + '/api/health')).json()
            tibi = isinstance(health, dict) and health.get('service') == 'tibi'
            return {'available': tibi, 'service': health if tibi else None, 'gateway': '/services/tibi'}
        except (httpx.HTTPError, ValueError):
            return {'available': False, 'service': None, 'gateway': '/services/tibi'}

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
