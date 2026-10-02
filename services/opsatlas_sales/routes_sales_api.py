"""The sidecars' API behind the workspace credential: Tibi's product contract and governance interviewer (AUDIT F13,
from create_sales_app)."""
import hashlib
import secrets

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from assistant import settings
from assistant.api.access import service
from assistant.iam.policy import AuthorizationContext
from assistant.iam.visibility import Visibility

from .spaces import FAMILY, PRODUCT, apply_family_layout


class Search(BaseModel):
    q: str


class SpokenDraft(BaseModel):
    record_id: str
    text: str


def _sources_in(value) -> set[str]:
    """Every source id named anywhere in an agenda item."""
    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key in ('source_id', 'source_b_id') and isinstance(item, str):
                found.add(item)
            else:
                found |= _sources_in(item)
    elif isinstance(value, list):
        for item in value:
            found |= _sources_in(item)
    return found


def build_sales_api_router(app, *, credential, knowledge, ontology, desk, register, sections, spaces) -> APIRouter:
    router = APIRouter()

    def check(request):
        if not secrets.compare_digest(request.headers.get('x-sales-token', ''), credential):
            raise HTTPException(403, 'Sales workspace access required')
    sales_service = service(check, "the workspace credential: Tibi's governance interviewer and the read-only product contract")

    def answer_digest(rows=None, full=None):
        """What Tibi may say, in one hash: enabled records with the evidence versions they were enabled against, usable
        spoken answers, and which product facts hold (audit F01, F04). Tibi checks it again before it speaks. The product
        facts are built from every record (one shared graph); the hash covers the records this caller may use."""
        full = full if full is not None else (knowledge.catalog() if rows is None else None)
        ontology.ensure(full if full is not None else rows)
        rows = full if rows is None else rows
        return hashlib.sha256(f'{knowledge.digest(rows)}:{ontology.digest()}'.encode()).hexdigest()
    app.state.answer_digest = answer_digest

    def readable(request):
        """Which records the conversation Tibi names may use (REF S10, S11): its owner's, from the OpsAtlas family spaces
        that person may read, without the documents restricted from them. A conversation OpsAtlas does not know gets the
        Product Guide only. No conversation named (Tibi itself: drafting spoken answers, warming up) keeps the whole
        family, as before. Conversation-style records guide how Tibi talks, never what it claims, and always apply."""
        conversation = request.headers.get('x-tibi-conversation')
        if not conversation:
            return None
        owners = getattr(app.state, 'tibi_owners', None)
        owner = owners.owner(conversation) if owners is not None else None
        family = app.state.family_register
        if owner is None:
            return lambda row: row.get('kind') == 'conversation' or family.space_of(row['source_id']) == PRODUCT
        iam = app.state.auth.iam
        ctx = AuthorizationContext(principal_id=owner)
        spaces = {s for s in FAMILY if iam.policy.evaluate(ctx, 'documents.read', space_id=s)}
        seen = {s: Visibility(iam, owner, s, app.state.cores[s].state.content.store.folders_of if s in app.state.cores else None)
                for s in spaces}

        def keep(row):
            if row.get('kind') == 'conversation':
                return True
            space = family.space_of(row['source_id'])
            return space in spaces and seen[space].can_read(row['source_id'])
        return keep

    def project(request, rows):
        keep = readable(request)
        return rows if keep is None else [r for r in rows if keep(r)]

    def caller_digest(request, full):
        """The digest of what this caller may use, reading the catalogue once (it is the slow part of every call)."""
        rows = project(request, full)
        return rows, answer_digest(rows, full)

    def project_facts(match, rows, allowed):
        """Product facts resting on a record the caller may not use are dropped, and so are those records."""
        if allowed is None:
            return match
        hidden = {r['id'] for r in rows} - {r['id'] for r in allowed}
        used = set(match.get('records', [])) | {i for a in match.get('aspects', []) for i in a.get('records', [])}
        if not hidden & used:
            return match
        return {**match, 'facts': [], 'fact_status': [], 'records': [r for r in match.get('records', []) if r not in hidden],
                'aspects': [a for a in match.get('aspects', []) if not hidden & set(a.get('records', []))]}

    @router.get('/api/sales/knowledge', dependencies=[sales_service])
    def catalog(request: Request):
        check(request)
        rows, digest_value = caller_digest(request, knowledge.catalog())
        return {'workspace': 'opsatlas-sales', 'records': rows, 'customer_approved': False, 'digest': digest_value}

    @router.get('/api/sales/digest', dependencies=[sales_service])
    def digest(request: Request):
        # Cheap revalidation before speech: changes whenever enabled records or usable spoken answers change.
        check(request)
        return {'workspace': 'opsatlas-sales', 'digest': caller_digest(request, knowledge.catalog())[1]}

    @router.post('/api/sales/search', dependencies=[sales_service])
    def search(data: Search, request: Request):
        check(request)
        if not 1 <= len(data.q.strip()) <= 1200:
            raise HTTPException(400, 'Use a shorter question')
        full = knowledge.catalog()
        keep = readable(request)
        rows = full if keep is None else [r for r in full if keep(r)]
        return {'workspace': 'opsatlas-sales', 'digest': answer_digest(rows, full),
                **knowledge.rank(data.q, app.state.retrieval, rows),
                'ontology': project_facts(ontology.match(data.q), full, None if keep is None else rows),
                'conversation': knowledge.conversation_guidance(data.q, rows)}

    @router.get('/api/sales/governance/agenda', dependencies=[sales_service])
    def governance_agenda(request: Request):
        check(request)
        agenda = desk.agenda()
        keep = readable(request)
        if keep is not None:  # nothing about a document the conversation's owner may not read (REF S11)
            family = app.state.family_register

            def visible_source(sid):
                return keep({'source_id': sid}) if family.space_of(sid) else True
            agenda = {**agenda, 'items': [i for i in agenda.get('items', []) if all(visible_source(s) for s in _sources_in(i))]}
            agenda['total'] = len(agenda['items'])
        return {'workspace': 'opsatlas-sales', **agenda}

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

    @router.get('/api/sales/ontology', dependencies=[sales_service])
    def product_ontology(request: Request):
        check(request)
        rows = knowledge.catalog()
        return {'workspace': 'opsatlas-sales', 'digest': answer_digest(rows), **ontology.export()}

    @router.get('/api/sales/spoken', dependencies=[sales_service])
    def spoken(request: Request):
        check(request)
        rows, digest_value = caller_digest(request, knowledge.catalog())
        return {'workspace': 'opsatlas-sales', 'variants': knowledge.spoken_catalog(rows), 'digest': digest_value}

    @router.post('/api/sales/spoken', dependencies=[sales_service])
    def spoken_draft(data: SpokenDraft, request: Request):
        check(request)
        try:
            return knowledge.add_spoken(data.record_id, data.text, 'local model draft')
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

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

    return router
