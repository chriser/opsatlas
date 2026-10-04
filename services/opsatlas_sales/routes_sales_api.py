"""The sidecars' API: Tibi's product contract and governance interviewer (AUDIT F13, from create_sales_app). Each
route needs one service permission, held by the service principal whose credential is presented (REF S12)."""
import hashlib

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from assistant import settings
from assistant.api.access import service
from assistant.evidence.contract import EvidenceBundle, EvidenceItem, EvidenceRequest
from assistant.evidence.receipts import digest as text_digest
from assistant.iam.policy import AuthorizationContext
from assistant.iam.visibility import Visibility

from .spaces import FAMILY, PRODUCT, WORKSPACE_STATEMENTS, apply_family_layout


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


def open_to_anyone(restricted, folders_of, source_id) -> bool:
    """Whether a document, and every folder it sits in, is open to anyone who may read its space (REF S13): what a
    conversation OpsAtlas does not know may use (red team, REF F10)."""
    return not any(link in restricted for link in [("document", source_id), *(("folder", f) for f in folders_of(source_id))])


def build_sales_api_router(app, *, principals, knowledge, ontology, desk, register, sections, spaces) -> APIRouter:
    router = APIRouter()

    def as_service(permission):
        """A route for the service principals holding ``permission``: any other credential, or none, is refused."""
        def check(request):
            principal = principals.identify(request.headers.get('x-sales-token', ''))
            if principal is None:
                raise HTTPException(403, 'Sales workspace access required')
            if permission not in principal.permissions:
                raise HTTPException(403, f'{principal.name} may not call this route')
            request.state.service = principal.id  # the activity log names the service (and whom it acts for)
        dependency = service(check, f'service principal with `{permission}` (REF S12)')
        dependency.dependency.service_permission = permission
        return dependency
    reads, proposes_spoken, proposes_record, interviews = (
        as_service(k) for k in ('sales.read', 'sales.spoken.propose', 'sales.proposals.create', 'sales.governance.interview'))

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
            # A conversation OpsAtlas does not know: the Product Guide, without the documents restricted in it to named
            # people (they were open to anyone here before; red team, REF F10).
            restricted = {(r['resource_type'], r['resource_id']) for r in app.state.auth.iam.restrictions(PRODUCT)}
            folders_of = app.state.content.store.folders_of if getattr(app.state, 'content', None) is not None else (lambda s: [])
            return lambda row: row.get('kind') == 'conversation' or (family.space_of(row['source_id']) == PRODUCT
                                                                     and open_to_anyone(restricted, folders_of, row['source_id']))
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

    def asking(request):
        """Whom Tibi is answering, from which spaces, on which channel (REF S19): the conversation's owner and the family
        spaces they may read; the Product Guide for a conversation OpsAtlas does not know; the family for Tibi itself."""
        conversation = request.headers.get('x-tibi-conversation')
        if not conversation:
            return None, list(FAMILY), 'service'
        owners = app.state.tibi_owners
        owner = owners.owner(conversation)
        channel = 'digital_sme' if owners.kind(conversation) == 'text' else 'voice'
        if owner is None:
            return None, [PRODUCT], channel
        ctx = AuthorizationContext(principal_id=owner)
        return owner, [s for s in FAMILY if app.state.auth.iam.policy.evaluate(ctx, 'documents.read', space_id=s)], channel

    def contract(request, question, ranked, rows):
        """The evidence contract both answer paths share (REF S19): the request, every ranked record with its source,
        space, hash and relevance, the decision, and the guide's refusal and referral sentences."""
        owner, spaces, channel = asking(request)
        by_id, family, config = {r['id']: r for r in rows}, app.state.family_register, app.state.answer.space_config
        bundle = EvidenceBundle(
            request=EvidenceRequest(person=owner, spaces=spaces, question_sha256=text_digest(question), channel=channel),
            items=[EvidenceItem(kind='record', source_id=by_id[r['id']]['source_id'], space=family.space_of(by_id[r['id']]['source_id']),
                                title=by_id[r['id']]['title'], locator=r['id'], sha256=by_id[r['id']].get('sha256'),
                                relevant=r['relevant']) for r in ranked['results'] if r['id'] in by_id],
            refusal=config.refusal, referral=config.referral.sentence or None, referral_topics=list(config.referral.topics),
            statements={k: c for k in ('refusal', 'referral') if (c := app.state.space_statements.cite(k))})
        return {**bundle.summary(), 'request': bundle.request.model_dump(), 'items': [i.model_dump() for i in bundle.items]}

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

    @router.get('/api/sales/knowledge', dependencies=[reads])
    def catalog(request: Request):
        rows, digest_value = caller_digest(request, knowledge.catalog())
        # Tibi's fixed directions, in the workspace's approved words (REF S22): it says them and logs their version.
        statements = {k: s for k in WORKSPACE_STATEMENTS if (s := app.state.space_statements.approved(k))}
        return {'workspace': 'opsatlas-sales', 'records': rows, 'customer_approved': False, 'digest': digest_value,
                'statements': statements}

    @router.get('/api/sales/digest', dependencies=[reads])
    def digest(request: Request):
        # Cheap revalidation before speech: changes whenever enabled records or usable spoken answers change.
        return {'workspace': 'opsatlas-sales', 'digest': caller_digest(request, knowledge.catalog())[1]}

    @router.post('/api/sales/search', dependencies=[reads])
    def search(data: Search, request: Request):
        if not 1 <= len(data.q.strip()) <= 1200:
            raise HTTPException(400, 'Use a shorter question')
        full = knowledge.catalog()
        keep = readable(request)
        rows = full if keep is None else [r for r in full if keep(r)]
        ranked = knowledge.rank(data.q, app.state.retrieval, rows)
        return {'workspace': 'opsatlas-sales', 'digest': answer_digest(rows, full), **ranked,
                'ontology': project_facts(ontology.match(data.q), full, None if keep is None else rows),
                'conversation': knowledge.conversation_guidance(data.q, rows),
                'contract': contract(request, data.q, ranked, rows)}

    @router.get('/api/sales/governance/agenda', dependencies=[interviews])
    def governance_agenda(request: Request):
        agenda = desk.agenda()
        keep = readable(request)
        if keep is not None:  # nothing about a document the conversation's owner may not read (REF S11)
            family = app.state.family_register

            def visible_source(sid):
                return keep({'source_id': sid}) if family.space_of(sid) else True
            agenda = {**agenda, 'items': [i for i in agenda.get('items', []) if all(visible_source(s) for s in _sources_in(i))]}
            agenda['total'] = len(agenda['items'])
        return {'workspace': 'opsatlas-sales', **agenda}

    @router.post('/api/sales/governance/verify', dependencies=[interviews])
    async def governance_verify(request: Request):
        data = await request.json()
        item = desk.item(str(data.get('issue_key', '')))
        if item is None or not isinstance(data.get('resolution'), dict) or not isinstance(data.get('answer'), str):
            raise HTTPException(409, 'That issue is no longer open; refresh the agenda')
        return {'workspace': 'opsatlas-sales', 'verification': desk.verify(item, data['resolution'], data['answer'][:1200])}

    @router.get('/api/sales/governance/answers', dependencies=[interviews])
    def governance_answers(request: Request):
        return {'workspace': 'opsatlas-sales', 'answers': desk.answers()}

    @router.post('/api/sales/governance/answers', dependencies=[interviews])
    async def governance_propose(request: Request):
        try:
            return desk.propose(await request.json())
        except (ValueError, TypeError, KeyError) as exc:
            raise HTTPException(409, str(exc)) from exc

    @router.get('/api/sales/ontology', dependencies=[reads])
    def product_ontology(request: Request):
        rows = knowledge.catalog()
        return {'workspace': 'opsatlas-sales', 'digest': answer_digest(rows), **ontology.export()}

    @router.get('/api/sales/spoken', dependencies=[reads])
    def spoken(request: Request):
        rows, digest_value = caller_digest(request, knowledge.catalog())
        return {'workspace': 'opsatlas-sales', 'variants': knowledge.spoken_catalog(rows), 'digest': digest_value}

    @router.post('/api/sales/spoken', dependencies=[proposes_spoken])
    def spoken_draft(data: SpokenDraft, request: Request):
        try:
            return knowledge.add_spoken(data.record_id, data.text, 'local model draft')
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @router.post('/api/sales/proposals', dependencies=[proposes_record])
    async def propose(request: Request):
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
