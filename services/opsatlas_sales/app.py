"""Separate loopback Atlas instance plus a read-only product-evidence contract."""
import hashlib
import os
import secrets
import subprocess
import time

from fastapi import Depends, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from . import foundation
from .workspace import REPO, workspace


class Decision(BaseModel):
    expected_hash: str
    approve: bool


class Search(BaseModel):
    q: str


class SpokenDraft(BaseModel):
    record_id: str
    text: str


class Restart(BaseModel):
    which: str = 'tibi'


class BrowserEvents(BaseModel):
    events: list[dict]


class TurnReview(BaseModel):
    verdict: str | None = None
    note: str = ''


def create_sales_app(root=None):
    root = workspace() if root is None else workspace(root)
    credential = (root / 'local-access.key').read_text().strip()
    # Do not inherit a shared data directory or optional external workers.
    os.environ['KP_DATA_DIR'] = str(root / 'core')
    os.environ['KP_OPERATOR_PASSWORD'] = credential
    os.environ['KP_COMPLIANCE_REASONING_URL'] = ''
    os.environ['KP_GOVERNANCE_LLM_ENABLED'] = '0'
    os.environ['KP_OLLAMA_URL'] = 'http://127.0.0.1:11434'
    os.environ['KP_LLM_MODEL'] = 'qwen3.5:4b'
    os.environ['KP_QUERY_REWRITE'] = '0'
    # The one person who signs in here: the author of edits, comments and versions (CM S26).
    os.environ.setdefault('KP_OPERATOR_NAME', 'Kris Pochopien')
    os.environ.setdefault('KP_OPERATOR_ROLE', 'Platform operator')
    os.environ['KP_RERANK'] = '0'
    from assistant.api.app import create_app

    from .knowledge import Knowledge
    from .ontology import ProductOntology
    app = create_app()
    # The activity log (OBS F1): every request, what the page did and Tibi's socket, for diagnosing what happened.
    from .activity import ActivityLog
    activity = ActivityLog(root, 'core', secrets=(credential,))
    browser_log = ActivityLog(root, 'browser', secrets=(credential,))
    app.state.activity = activity
    activity.write('service', event='OpsAtlas started', pid=os.getpid(), workspace=str(root))
    knowledge = Knowledge(app.state.register, app.state.actions)
    corpus, papers = foundation.active()
    knowledge.seed(corpus, papers)
    knowledge.seed_conversation(foundation.CORPUS / 'conversation.json')
    app.state.sales = knowledge
    # The product ontology has its own schema and database: rebuilding it never touches the core ontology.
    ontology = ProductOntology(app.state.register.base_dir / 'product-ontology.db')
    ontology.ensure(knowledge.catalog())
    app.state.product_ontology = ontology
    from .governance import GovernanceDesk
    desk = GovernanceDesk(app.state.register, app.state.section_store, app.state.retrieval, app.state.actions, knowledge)
    app.state.governance_desk = desk
    # Content management keeps records consistent when their documents are edited (CM S12).
    from .content import attach as attach_content
    attach_content(app.state.content, knowledge, desk)
    # Tibi inside the control panel: the same workflows behind the OpsAtlas operator sign-in.
    from .tibi_api import build_router, voice_url
    from .tibi_proxy import attach as attach_tibi
    voice = voice_url()
    app.include_router(build_router(app, knowledge, ontology, desk, voice))
    attach_tibi(app, voice, activity)  # the gateway to the Tibi service, behind the OpsAtlas sign-in

    from assistant.api.routes_auth import make_require_auth

    @app.post('/api/services/restart', dependencies=[Depends(make_require_auth(app.state.auth))])
    def restart_services(data: Restart):
        """Restart services from the control panel: Tibi alone (the operator stays signed in), or Tibi and then
        this core as well (sign-ins are held in memory, so the operator signs in again)."""
        from . import manage
        if data.which not in ('tibi', 'all'):
            raise HTTPException(400, 'Restart "tibi" or "all"')
        activity.write('service', event='restart requested', which=data.which)
        try:
            manage.restart('voice')
            if data.which == 'all':
                manage.restart_later('core')
        except (RuntimeError, subprocess.CalledProcessError) as exc:
            activity.write('service', event='restart refused', which=data.which, error=str(exc))
            raise HTTPException(409, str(exc) if isinstance(exc, RuntimeError) else 'launchd could not restart the service') from exc
        return {'restarting': ['tibi', 'core'] if data.which == 'all' else ['tibi'], 'sign_in_again': data.which == 'all'}

    @app.middleware('http')
    async def boundary(request: Request, call_next):
        host = request.headers.get('host', '')
        if host.split(':')[0] not in ('127.0.0.1', 'localhost', 'testserver'):
            return HTMLResponse('Local workspace only', status_code=403)
        origin = request.headers.get('origin')
        if origin and origin != f'{request.url.scheme}://{host}':
            return HTMLResponse('Use the sales workspace', status_code=403)
        response = await call_next(request)
        response.headers['X-OpsAtlas-Workspace'] = 'opsatlas-sales'
        response.headers['Cache-Control'] = 'no-store'
        return response

    from .activity import POLLS

    @app.middleware('http')
    async def record(request: Request, call_next):
        """Every request in the activity log, with the page it came from; sign-ins as their own events."""
        started = time.perf_counter()
        path = request.url.path
        fields = {'method': request.method, 'path': path, 'view': request.headers.get('x-opsatlas-view') or None,
                  'poll': path in POLLS or None}
        if request.url.query:
            fields['query'] = dict(request.query_params)
        try:
            response = await call_next(request)
        except Exception as exc:
            activity.write('http', **fields, status=500, ms=round((time.perf_counter() - started) * 1000, 1),
                           error=type(exc).__name__)
            raise
        ms = round((time.perf_counter() - started) * 1000, 1)
        if path.startswith(('/api/', '/services/')):
            activity.write('http', **fields, status=response.status_code, ms=ms)
        elif not path.startswith('/assets/'):
            activity.write('http', method=request.method, path=path, status=response.status_code, ms=ms, page=True)
        if path == '/api/auth/login' and request.method == 'POST':
            activity.write('auth', event='signed in' if response.status_code == 200 else 'sign-in refused',
                           status=response.status_code)
        elif path == '/api/auth/logout':
            activity.write('auth', event='signed out')
        return response

    # The conversation log (OBS F2): Tibi writes each turn; the Human reviews sessions and marks turns here.
    from . import conversations
    signed_in = [Depends(make_require_auth(app.state.auth))]

    @app.get('/api/conversations', dependencies=signed_in)
    def conversation_sessions(days: int = 30):
        return {'sessions': conversations.sessions(root, min(max(days, 1), 365))}

    @app.get('/api/conversations/flagged', dependencies=signed_in)
    def conversation_flags():
        return {'turns': conversations.flagged(root)}

    @app.get('/api/conversations/{identifier}', dependencies=signed_in)
    def conversation(identifier: str):
        try:
            return conversations.session(root, identifier)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.put('/api/conversations/{identifier}/turns/{turn}/review', dependencies=signed_in)
    def review_turn(identifier: str, turn: int, data: TurnReview):
        try:
            row = conversations.review(root, identifier, turn, data.verdict, data.note,
                                       os.environ.get('KP_OPERATOR_NAME', 'operator'))
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        activity.write('review', event='marked a turn', session=identifier, turn=turn, verdict=data.verdict)
        return row

    @app.post('/api/activity', dependencies=[Depends(make_require_auth(app.state.auth))])
    def browser_activity(data: BrowserEvents):
        """What the control panel page did, in small batches: pages, buttons, Tibi's microphone and socket, errors."""
        for event in data.events[:100]:
            if isinstance(event, dict):
                kind = str(event.pop('kind', 'action'))[:40]
                browser_log.write(kind, **{str(k)[:40]: v for k, v in list(event.items())[:20]})
        return {'recorded': min(len(data.events), 100)}

    def check(request):
        if not secrets.compare_digest(request.headers.get('x-sales-token', ''), credential):
            raise HTTPException(403, 'Sales workspace access required')

    def answer_digest(rows=None):
        """What Tibi may say, in one hash: enabled records with the evidence versions they were enabled against, usable
        spoken answers, and which product facts hold (audit F01, F04). Tibi checks it again before it speaks."""
        rows = knowledge.catalog() if rows is None else rows
        ontology.ensure(rows)
        return hashlib.sha256(f'{knowledge.digest(rows)}:{ontology.digest()}'.encode()).hexdigest()
    app.state.answer_digest = answer_digest

    @app.get('/api/sales/knowledge')
    def catalog(request: Request):
        check(request)
        rows = knowledge.catalog()
        return {'workspace': 'opsatlas-sales', 'records': rows, 'customer_approved': False,
                'digest': answer_digest(rows)}

    @app.get('/api/sales/digest')
    def digest(request: Request):
        # Cheap revalidation before speech: changes whenever enabled records or usable spoken answers change.
        check(request)
        return {'workspace': 'opsatlas-sales', 'digest': answer_digest()}

    @app.post('/api/sales/search')
    def search(data: Search, request: Request):
        check(request)
        if not 1 <= len(data.q.strip()) <= 1200:
            raise HTTPException(400, 'Use a shorter question')
        rows = knowledge.catalog()
        return {'workspace': 'opsatlas-sales', 'digest': answer_digest(rows),
                **knowledge.rank(data.q, app.state.retrieval, rows), 'ontology': ontology.match(data.q),
                'conversation': knowledge.conversation_guidance(data.q, rows)}

    @app.get('/api/sales/governance/agenda')
    def governance_agenda(request: Request):
        check(request)
        return {'workspace': 'opsatlas-sales', **desk.agenda()}

    @app.post('/api/sales/governance/verify')
    async def governance_verify(request: Request):
        check(request)
        data = await request.json()
        item = desk.item(str(data.get('issue_key', '')))
        if item is None or not isinstance(data.get('resolution'), dict) or not isinstance(data.get('answer'), str):
            raise HTTPException(409, 'That issue is no longer open; refresh the agenda')
        return {'workspace': 'opsatlas-sales', 'verification': desk.verify(item, data['resolution'], data['answer'][:1200])}

    @app.get('/api/sales/governance/answers')
    def governance_answers(request: Request):
        check(request)
        return {'workspace': 'opsatlas-sales', 'answers': desk.answers()}

    @app.post('/api/sales/governance/answers')
    async def governance_propose(request: Request):
        check(request)
        try:
            return desk.propose(await request.json())
        except (ValueError, TypeError, KeyError) as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post('/api/sales/governance/answers/{identifier}/review')
    def governance_review(identifier: str, data: Decision, request: Request):
        check(request)
        try:
            return desk.review(identifier, data.expected_hash, data.approve)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get('/api/sales/ontology')
    def product_ontology(request: Request):
        check(request)
        rows = knowledge.catalog()
        return {'workspace': 'opsatlas-sales', 'digest': answer_digest(rows), **ontology.export()}

    @app.get('/api/sales/spoken')
    def spoken(request: Request):
        check(request)
        rows = knowledge.catalog()
        return {'workspace': 'opsatlas-sales', 'variants': knowledge.spoken_catalog(rows), 'digest': answer_digest(rows)}

    @app.post('/api/sales/spoken')
    def spoken_draft(data: SpokenDraft, request: Request):
        check(request)
        try:
            return knowledge.add_spoken(data.record_id, data.text, 'local model draft')
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post('/api/sales/spoken/{identifier}/review')
    def spoken_review(identifier: str, data: Decision, request: Request):
        check(request)
        try:
            return knowledge.review_spoken(identifier, data.expected_hash, data.approve)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post('/api/sales/knowledge/{identifier}/review')
    def review(identifier: str, data: Decision, request: Request):
        check(request)
        try:
            result = knowledge.decide(identifier, data.expected_hash, data.approve)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        return result

    @app.get('/api/sales/source/{identifier}')
    def source(identifier: str, request: Request):
        check(request)
        record = app.state.register.get(identifier)
        if not record:
            raise HTTPException(404)
        return {'title': record.title, 'text': app.state.register.read_content(identifier).decode('utf-8')}

    @app.post('/api/sales/proposals')
    async def propose(request: Request):
        check(request)
        try:
            row = knowledge.propose(await request.json())
        except (ValueError, TypeError, KeyError) as exc:
            raise HTTPException(409, str(exc)) from exc
        if os.environ.get('SALES_GOVERNANCE_AUTO_REVIEW', '1') != '0':
            # A new claim is checked against the records before the Human enables it: only its own pairs are judged.
            desk.statements.start()
        return row

    @app.post('/api/sales/knowledge/{identifier}/resolve')
    async def resolve(identifier: str, request: Request):
        check(request)
        try:
            data = await request.json()
            return knowledge.adjudicate(identifier, data['expected_hash'], data['decision'], data['related'], data['reason'])
        except (ValueError, TypeError, KeyError) as exc:
            raise HTTPException(409, str(exc)) from exc

    # Existing built Control Panel uses same-origin /api, never the old 8010 backend.
    dist = REPO / 'frontend/dist'

    @app.get('/{path:path}')
    def frontend(path: str):
        if path.startswith('api/'):
            raise HTTPException(404)
        file = (dist / path).resolve()
        if not file.is_relative_to(dist.resolve()):
            raise HTTPException(404)
        if file.is_file() and file.name != 'index.html':
            return FileResponse(file)
        html = (dist / 'index.html').read_text()
        return HTMLResponse(html.replace('<title>', '<title>OpsAtlas Sales · '))
    return app


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(create_sales_app(), host='127.0.0.1', port=8780)
