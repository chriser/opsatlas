"""OpsAtlas's side of Tibi: the control panel's API for the knowledge Tibi uses and the answers it collects.

Behind the OpsAtlas operator sign-in: records, conversation style, spoken answers, the product ontology,
and the governance-interview answers approved on the Governance page. These are OpsAtlas data; every
decision goes through the Knowledge and GovernanceDesk methods, and nothing here approves on its own.

Tibi itself is a separate service. OpsAtlas never imports its code or reads its storage: it checks the
service's health over HTTP, and the control panel reaches its API through the gateway (tibi_proxy).
"""
import json
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from assistant import settings
from assistant.api.access import need
from assistant.iam.context import acting_id, acting_name


def voice_url():
    """The Tibi service's address; a disposable copy (the latency replay, a UI check) runs its own on another port."""
    return settings.get('SME_TIBI_VOICE_URL') or f'http://127.0.0.1:{settings.TIBI_PORT}'


class Review(BaseModel):
    expected_hash: str
    approve: bool


class FactConfirmation(BaseModel):
    records: dict[str, str]


class Resolution(BaseModel):
    expected_hash: str
    decision: str
    related: dict
    reason: str


ISSUE_LABELS = {'undefined_acronym': 'Acronym not spelled out', 'readability': 'Hard to read',
                'localisation': 'Mixed UK and US spelling', 'content_style': 'House style', 'broken_link': 'Broken link',
                'duplicate': 'Repeated section', 'metadata_title': 'No descriptive title', 'not_ingested': 'Not usable yet',
                'conflict': 'Possible contradiction'}


def open_issue(item: dict) -> dict:
    """An agenda item in plain words: what it is, where it is, and what the sources already say about it."""
    hint = None
    if item['kind'] == 'acronym':
        text = f"{item['acronym']} is used without being spelled out."
        where = item.get('sources') or [item['source_title']]
        known = item.get('known') or []
        if known:
            hint = f"{known[0]['source_title']} spells it out as {known[0]['expansion']}."
    elif item['kind'] == 'standard':
        names = item.get('acronyms') or []
        text = f"Common acronym{'s' if len(names) > 1 else ''} used without being spelled out: {', '.join(names)}."
        where = sorted({ref['source_title'] for ref in item.get('issues', [])}) or [item['source_title']]
    else:
        text = item.get('detail') or ''
        where = [t for t in (item.get('source_title'), item.get('source_b_title')) if t]
        hint = item.get('recommended_action')
    return {'key': item['key'], 'kind': item['kind'], 'check': item['check'],
            'label': ISSUE_LABELS.get(item['check'], item['check'].replace('_', ' ').capitalize()),
            'severity': item.get('severity'), 'text': text, 'where': where, 'hint': hint,
            'answer': (item.get('answer') or {}).get('status')}


def build_router(app, knowledge, ontology, desk, voice):
    from assistant.api.access import by_method, current_actor

    router = APIRouter(prefix='/api/tibi', dependencies=by_method(GET='tibi.use'))

    class Ticket(BaseModel):
        conversation_id: str

    @router.post('/ws-ticket', dependencies=[need('tibi.voice.use')])
    def ws_ticket(data: Ticket, request: Request):
        """A one-use, 30-second ticket for the voice socket's hello: the browser cannot prove its session there
        otherwise, and a ticket is bound to this session and this conversation (IAM F6)."""
        actor = current_actor(request)
        owners = getattr(app.state, 'tibi_owners', None)
        if owners is not None and not owners.may(actor, data.conversation_id, app.state.space_id):
            raise HTTPException(404, 'Not found')  # a ticket only for one's own conversation (REF S14)
        return {'ticket': app.state.auth.iam.issue_ticket(actor.session, data.conversation_id, app.state.space_id)}

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
            return {'available': tibi, 'service': health if tibi else None, 'gateway': '/services/tibi', 'busy': busy()}
        except (httpx.HTTPError, ValueError):
            return {'available': False, 'service': None, 'gateway': '/services/tibi', 'busy': busy()}

    def busy():
        """Why Tibi may be slow to start: the governance review judges on the same local model server, and Tibi's
        warm-up waits behind it (26 September 2026: three starts timed out while a review ran)."""
        if desk.statements.state.get('status') == 'running':
            return 'The governance review is using the local model; Tibi can be slow to start until it finishes.'
        return None

    from .machine import Machine
    machine = Machine(getattr(app.state, 'activity', None))

    @router.get('/machine')
    def machine_reading():
        """How busy this Mac is: the graphics processor and who is using it, memory, the processors, and the models
        OpsAtlas has loaded, with what to do when Tibi's voice is at risk. The Talk with Tibi page asks every few seconds."""
        return machine.read()

    @router.get('/knowledge', dependencies=[need("tibi.knowledge.read")])
    def records():
        rows = knowledge.catalog()
        return {'records': rows, 'digest': app.state.answer_digest(rows)}

    @router.post('/knowledge/{identifier}/review', dependencies=[need("tibi.knowledge.approve")])
    def review(identifier: str, data: Review):
        return conflict(lambda: knowledge.decide(identifier, data.expected_hash, data.approve))

    @router.post('/knowledge/{identifier}/resolve', dependencies=[need("tibi.knowledge.approve")])
    def resolve(identifier: str, data: Resolution):
        return conflict(lambda: knowledge.adjudicate(identifier, data.expected_hash, data.decision, data.related, data.reason))

    @router.get('/sources/{identifier}', dependencies=[need("tibi.knowledge.read")])
    def source(identifier: str):
        record = app.state.family_register.get(identifier)
        if not record:
            raise HTTPException(404)
        return {'title': record.title, 'text': app.state.family_register.read_content(identifier).decode('utf-8', 'replace')}

    @router.get('/spoken', dependencies=[need("tibi.knowledge.read")])
    def spoken():
        return {'variants': knowledge.spoken_catalog()}

    @router.post('/spoken/{identifier}/review', dependencies=[need("tibi.spoken.approve")])
    def review_spoken(identifier: str, data: Review):
        return conflict(lambda: knowledge.review_spoken(identifier, data.expected_hash, data.approve))

    @router.get('/ontology', dependencies=[need("tibi.knowledge.read")])
    def product_ontology():
        ontology.ensure(knowledge.catalog())
        return ontology.export()

    @router.post('/ontology/{identifier}/confirm', dependencies=[need("tibi.knowledge.approve")])
    def confirm_fact(identifier: str, data: FactConfirmation):
        """The Human confirms a product fact still holds against its records' current wording (audit F04)."""
        item = conflict(lambda: ontology.confirm(identifier, data.records, knowledge.catalog()))
        with (app.state.register.base_dir / 'sales-review-history.jsonl').open('a') as log:
            log.write(json.dumps({'ontology_fact': identifier, 'decision': 'confirmed against current records',
                                  'records': data.records, 'actor': acting_name(), 'actor_id': acting_id(),
                                  'at': datetime.now(timezone.utc).isoformat()}) + '\n')
        ontology.ensure(knowledge.catalog())
        return {'confirmed': item['id'], **ontology.export()}

    @router.get('/governance/answers', dependencies=[need("governance.read")])
    def governance_answers():
        return {'answers': desk.answers()}

    @router.get('/governance/agenda', dependencies=[need("governance.read")])
    def governance_agenda():
        agenda = desk.agenda()
        # Conflicts and duplicates between records are listed with the statement review; the rest are listed here,
        # so every open issue can be read on the Governance page, not only in Tibi's interview.
        return {'issues': agenda['issues'], 'total': agenda['total'],
                'answered': sum(1 for i in agenda['items'] if i.get('answer')),
                'open': sum(1 for i in agenda['items'] if not i.get('answer')),
                'items': [open_issue(i) for i in agenda['items'] if i.get('kind') != 'statement']}

    @router.post('/governance/answers/{identifier}/review', dependencies=[need("governance.findings.resolve")])
    def governance_review(identifier: str, data: Review):
        return conflict(lambda: desk.review(identifier, data.expected_hash, data.approve))

    # Statement-level governance of the records (GOV S9): conflicts and duplicates between records, judged locally
    # by default. A review runs in the background; findings join the agenda when it finishes.
    @router.get('/governance/statements', dependencies=[need("governance.read")])
    def governance_statements():
        open_items = [i for i in desk.agenda()['items'] if i.get('kind') == 'statement']
        return {**desk.statements.status(), 'open': [
            {k: i.get(k) for k in ('key', 'relation', 'statements', 'reason', 'second_opinion', 'same_document', 'answer')}
            for i in open_items]}

    @router.post('/governance/statements/run', dependencies=[need("governance.reviews.run")])
    def governance_statements_run():
        return desk.statements.start()

    return router
