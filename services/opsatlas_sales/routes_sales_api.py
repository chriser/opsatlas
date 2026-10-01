"""The sidecars' API behind the workspace credential: Tibi's product contract and governance interviewer (AUDIT F13,
from create_sales_app)."""
import hashlib
import secrets

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from assistant import settings
from assistant.api.access import service

from .spaces import apply_family_layout


class Decision(BaseModel):
    expected_hash: str
    approve: bool


class Search(BaseModel):
    q: str


class SpokenDraft(BaseModel):
    record_id: str
    text: str


def build_sales_api_router(app, *, credential, knowledge, ontology, desk, register, sections, spaces) -> APIRouter:
    router = APIRouter()

    def check(request):
        if not secrets.compare_digest(request.headers.get('x-sales-token', ''), credential):
            raise HTTPException(403, 'Sales workspace access required')
    sales_service = service(check, "the workspace credential: Tibi's governance interviewer and the read-only product contract")

    def answer_digest(rows=None):
        """What Tibi may say, in one hash: enabled records with the evidence versions they were enabled against, usable
        spoken answers, and which product facts hold (audit F01, F04). Tibi checks it again before it speaks."""
        rows = knowledge.catalog() if rows is None else rows
        ontology.ensure(rows)
        return hashlib.sha256(f'{knowledge.digest(rows)}:{ontology.digest()}'.encode()).hexdigest()
    app.state.answer_digest = answer_digest

    @router.get('/api/sales/knowledge', dependencies=[sales_service])
    def catalog(request: Request):
        check(request)
        rows = knowledge.catalog()
        return {'workspace': 'opsatlas-sales', 'records': rows, 'customer_approved': False,
                'digest': answer_digest(rows)}

    @router.get('/api/sales/digest', dependencies=[sales_service])
    def digest(request: Request):
        # Cheap revalidation before speech: changes whenever enabled records or usable spoken answers change.
        check(request)
        return {'workspace': 'opsatlas-sales', 'digest': answer_digest()}

    @router.post('/api/sales/search', dependencies=[sales_service])
    def search(data: Search, request: Request):
        check(request)
        if not 1 <= len(data.q.strip()) <= 1200:
            raise HTTPException(400, 'Use a shorter question')
        rows = knowledge.catalog()
        return {'workspace': 'opsatlas-sales', 'digest': answer_digest(rows),
                **knowledge.rank(data.q, app.state.retrieval, rows), 'ontology': ontology.match(data.q),
                'conversation': knowledge.conversation_guidance(data.q, rows)}

    @router.get('/api/sales/governance/agenda', dependencies=[sales_service])
    def governance_agenda(request: Request):
        check(request)
        return {'workspace': 'opsatlas-sales', **desk.agenda()}

    @router.post('/api/sales/governance/verify', dependencies=[sales_service])
    async def governance_verify(request: Request):
        check(request)
        data = await request.json()
        item = desk.item(str(data.get('issue_key', '')))
        if item is None or not isinstance(data.get('resolution'), dict) or not isinstance(data.get('answer'), str):
            raise HTTPException(409, 'That issue is no longer open; refresh the agenda')
        return {'workspace': 'opsatlas-sales', 'verification': desk.verify(item, data['resolution'], data['answer'][:1200])}

    @router.get('/api/sales/governance/answers', dependencies=[sales_service])
    def governance_answers(request: Request):
        check(request)
        return {'workspace': 'opsatlas-sales', 'answers': desk.answers()}

    @router.post('/api/sales/governance/answers', dependencies=[sales_service])
    async def governance_propose(request: Request):
        check(request)
        try:
            return desk.propose(await request.json())
        except (ValueError, TypeError, KeyError) as exc:
            raise HTTPException(409, str(exc)) from exc

    @router.post('/api/sales/governance/answers/{identifier}/review', dependencies=[sales_service])
    def governance_review(identifier: str, data: Decision, request: Request):
        check(request)
        try:
            return desk.review(identifier, data.expected_hash, data.approve)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @router.get('/api/sales/ontology', dependencies=[sales_service])
    def product_ontology(request: Request):
        check(request)
        rows = knowledge.catalog()
        return {'workspace': 'opsatlas-sales', 'digest': answer_digest(rows), **ontology.export()}

    @router.get('/api/sales/spoken', dependencies=[sales_service])
    def spoken(request: Request):
        check(request)
        rows = knowledge.catalog()
        return {'workspace': 'opsatlas-sales', 'variants': knowledge.spoken_catalog(rows), 'digest': answer_digest(rows)}

    @router.post('/api/sales/spoken', dependencies=[sales_service])
    def spoken_draft(data: SpokenDraft, request: Request):
        check(request)
        try:
            return knowledge.add_spoken(data.record_id, data.text, 'local model draft')
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @router.post('/api/sales/spoken/{identifier}/review', dependencies=[sales_service])
    def spoken_review(identifier: str, data: Decision, request: Request):
        check(request)
        try:
            return knowledge.review_spoken(identifier, data.expected_hash, data.approve)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @router.post('/api/sales/knowledge/{identifier}/review', dependencies=[sales_service])
    def review(identifier: str, data: Decision, request: Request):
        check(request)
        try:
            result = knowledge.decide(identifier, data.expected_hash, data.approve)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        return result

    @router.get('/api/sales/source/{identifier}', dependencies=[sales_service])
    def source(identifier: str, request: Request):
        check(request)
        record = app.state.family_register.get(identifier)
        if not record:
            raise HTTPException(404)
        return {'title': record.title, 'text': app.state.family_register.read_content(identifier).decode('utf-8')}

    @router.post('/api/sales/proposals', dependencies=[sales_service])
    async def propose(request: Request):
        check(request)
        try:
            row = knowledge.propose(await request.json())
        except (ValueError, TypeError, KeyError) as exc:
            raise HTTPException(409, str(exc)) from exc
        apply_family_layout(knowledge, register, sections, spaces)  # a contributed claim belongs in the playbook
        if settings.get('SALES_GOVERNANCE_AUTO_REVIEW') != '0':
            # A new claim is checked against the records before the Human enables it: only its own pairs are judged.
            desk.statements.start()
        return row

    @router.post('/api/sales/knowledge/{identifier}/resolve', dependencies=[sales_service])
    async def resolve(identifier: str, request: Request):
        check(request)
        try:
            data = await request.json()
            return knowledge.adjudicate(identifier, data['expected_hash'], data['decision'], data['related'], data['reason'])
        except (ValueError, TypeError, KeyError) as exc:
            raise HTTPException(409, str(exc)) from exc
    return router
