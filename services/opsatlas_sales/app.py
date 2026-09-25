"""Separate loopback Atlas instance plus a read-only product-evidence contract."""
import os
import secrets

from fastapi import HTTPException, Request
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
    os.environ['KP_RERANK'] = '0'
    from assistant.api.app import create_app

    from .knowledge import Knowledge
    from .ontology import ProductOntology
    app = create_app()
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
    # Tibi inside the control panel: the same workflows behind the OpsAtlas operator sign-in.
    from .tibi_api import build_router, voice_url
    from .tibi_proxy import attach as attach_tibi
    voice = voice_url()
    app.include_router(build_router(app, knowledge, ontology, desk, voice))
    attach_tibi(app, voice)  # the gateway to the Tibi service, behind the OpsAtlas sign-in

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

    def check(request):
        if not secrets.compare_digest(request.headers.get('x-sales-token', ''), credential):
            raise HTTPException(403, 'Sales workspace access required')

    @app.get('/api/sales/knowledge')
    def catalog(request: Request):
        check(request)
        rows = knowledge.catalog()
        return {'workspace': 'opsatlas-sales', 'records': rows, 'customer_approved': False,
                'digest': knowledge.digest(rows)}

    @app.get('/api/sales/digest')
    def digest(request: Request):
        # Cheap revalidation before speech: changes whenever enabled records or usable spoken answers change.
        check(request)
        return {'workspace': 'opsatlas-sales', 'digest': knowledge.digest()}

    @app.post('/api/sales/search')
    def search(data: Search, request: Request):
        check(request)
        if not 1 <= len(data.q.strip()) <= 1200:
            raise HTTPException(400, 'Use a shorter question')
        rows = knowledge.catalog()
        ontology.ensure(rows)
        return {'workspace': 'opsatlas-sales', 'digest': knowledge.digest(rows),
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
        ontology.ensure(rows)
        return {'workspace': 'opsatlas-sales', 'digest': knowledge.digest(rows), **ontology.export()}

    @app.get('/api/sales/spoken')
    def spoken(request: Request):
        check(request)
        rows = knowledge.catalog()
        return {'workspace': 'opsatlas-sales', 'variants': knowledge.spoken_catalog(rows), 'digest': knowledge.digest(rows)}

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
            return knowledge.propose(await request.json())
        except (ValueError, TypeError, KeyError) as exc:
            raise HTTPException(409, str(exc)) from exc

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
        banner = ('<aside style="position:fixed;bottom:0;left:0;right:0;z-index:99999;background:#173e36;'
                  'color:white;padding:10px;text-align:center">OpsAtlas Sales · isolated internal rehearsal workspace '
                  '· <a style="color:white" href="/#tibi">Talk with Tibi</a></aside>')
        return HTMLResponse(html.replace('<title>', '<title>OpsAtlas Sales · ').replace('</body>', banner + '</body>'))
    return app


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(create_sales_app(), host='127.0.0.1', port=8780)
