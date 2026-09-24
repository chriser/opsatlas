"""Tiberius voice front end; same-origin review proxy to the isolated Atlas core."""
import os

import httpx
from fastapi import HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from services.opsatlas_sales.workspace import workspace

from .app import create_app
from .evidence import digest
from .product_interviewer import ProductInterviewer
from .speech import ROOT
from .tibi import Tibi


class SalesEvidence:
    def snapshot(self):
        pack = {'schema': 1, 'id': 'opsatlas-sales', 'mode': 'sales_rehearsal', 'title': 'OpsAtlas product knowledge',
                'scope': {'topic': 'OpsAtlas'}, 'sources': [],
                'notice': 'Internal product rehearsal. Evidence is checked per answer; conversation does not publish knowledge.'}
        return {**pack, 'hash': digest(pack)}

    def current(self, snapshot):
        return {k: v for k, v in snapshot.items() if k != 'product_interview'} == self.snapshot()


def sales_app(root=None, base_url='http://127.0.0.1:8780'):
    root = workspace() if root is None else workspace(root)
    runtime = root / 'voice'
    for name in ('models', 'experience', 'experience-env'):
        target = runtime / name
        if not target.exists():
            target.symlink_to(ROOT / '.runtime' / name, target_is_directory=True)
    binary = runtime / 'conversation-recognizer'
    if not binary.exists():
        binary.symlink_to(ROOT / '.runtime/recognition-check/conversation-recognizer')
    os.environ.update(SME_SOCIAL_CHAT='1', SME_VOICE_BACKEND='higgs', SME_SALES_VOICE='higgs', SME_SMART_ENDPOINT='1',
                      SME_DEFER_REVIEWS='1', SME_LISTENER_LAB='1')
    # Voice-rating experiments run from experience.voice_ratings on their own port; the live
    # service no longer mounts them or writes into the shared experiment runtime.
    app = create_app(runtime, evidence=SalesEvidence())
    credential = (root / 'local-access.key').read_text().strip()
    app.state.interviews.companion_factory = lambda history: Tibi(history, credential, base_url)
    app.state.interviews.product_companion_factory = lambda session: ProductInterviewer(session, credential, base_url)

    async def backend(path, body=None):
        async with httpx.AsyncClient(base_url=base_url, timeout=5, trust_env=False) as client:
            headers = {'x-sales-token': credential}
            response = await (client.get(path, headers=headers) if body is None else client.post(path, headers=headers, json=body))
            if response.status_code >= 400:
                raise HTTPException(response.status_code, response.json().get('detail', 'Refresh and review the evidence.'))
            return response.json()

    @app.middleware('http')
    async def entry(request, call_next):
        if request.url.path == '/':
            return RedirectResponse('/conversation?social=1&sales=1')
        if request.url.path == '/conversation':
            if request.query_params.get('social') != '1' or request.query_params.get('sales') != '1':
                return RedirectResponse('/conversation?social=1&sales=1')
            html = (ROOT / 'web/conversation.html').read_text()
            start = html.index('<select id="social-voice">')
            end = html.index('</select>', start) + len('</select>')
            html = html[:start] + ('<select id="social-voice"><option value="higgs">Higgs · selected male voice</option>'
                                   '<option value="higgs_female">Higgs · female alternative</option></select>') + html[end:]
            html = html.replace('href="/social-voices"', 'href="http://127.0.0.1:8774/higgs-voices"')
            return HTMLResponse(html.replace('</head>', '<script src="/sales.js" defer></script></head>'))
        # Do not expose the supplier-specific form or publication-like recap in this workspace.
        if request.url.path in ('/interview', '/social-voices'):
            return RedirectResponse('/knowledge')
        return await call_next(request)

    @app.get('/sales.js')
    async def script():
        return FileResponse(ROOT / 'web/sales.js')

    @app.get('/knowledge')
    async def review_page():
        return FileResponse(ROOT / 'web/sales-knowledge.html')

    @app.get('/sales-knowledge.js')
    async def review_script():
        return FileResponse(ROOT / 'web/sales-knowledge.js')

    @app.get('/api/sales/knowledge')
    async def knowledge():
        return await backend('/api/sales/knowledge')

    @app.get('/api/sales/spoken')
    async def spoken():
        return await backend('/api/sales/spoken')

    @app.post('/api/sales/spoken/draft')
    async def draft_spoken(request: Request):
        # Drafts are checked against their record by the core and stay pending until reviewed.
        if request.headers.get('origin') not in (None, str(request.base_url).rstrip('/')):
            raise HTTPException(403)
        return await Tibi([], credential, base_url).draft_spoken()

    @app.post('/api/sales/spoken/{identifier}/review')
    async def review_spoken(identifier: str, request: Request):
        if not identifier.isalnum():
            raise HTTPException(404)
        data = await request.json()
        if set(data) != {'expected_hash', 'approve'} or type(data['approve']) is not bool:
            raise HTTPException(400)
        return await backend('/api/sales/spoken/' + identifier + '/review', data)

    @app.get('/api/sales/contributions')
    async def contributions():
        store = app.state.interviews.store
        sessions = [store.get(s['id']) for s in store.list()]
        return {'turns': [{**turn, 'session_id': s['id']} for s in sessions for turn in s.get('product_turns', [])]}

    @app.post('/api/sales/proposals')
    async def proposal(request: Request):
        data = await request.json()
        try:
            session = app.state.interviews.store.get(data['session_id'])
            turn = next(t for t in session.get('product_turns', []) if t['id'] == data['turn_id'])
            # Attribution and original transcript come from the saved server record, never the browser.
            payload = {k: turn[k] for k in ('contributor', 'topic', 'question', 'raw_text', 'issue')}
            payload.update({k: data[k] for k in ('session_id', 'turn_id', 'text', 'status', 'expected_hash', 'wording_confirmed')})
        except (KeyError, StopIteration, TypeError) as exc:
            raise HTTPException(400, 'Select a saved contribution') from exc
        return await backend('/api/sales/proposals', payload)

    @app.post('/api/sales/knowledge/{identifier}/resolve')
    async def resolution(identifier: str, request: Request):
        if not identifier.isalnum():
            raise HTTPException(404)
        return await backend('/api/sales/knowledge/' + identifier + '/resolve', await request.json())

    @app.get('/api/sales/source/{identifier}')
    async def source(identifier: str):
        if not identifier.isalnum():
            raise HTTPException(404)
        return await backend('/api/sales/source/' + identifier)

    @app.post('/api/sales/knowledge/{identifier}/review')
    async def review(identifier: str, request: Request):
        if not identifier.isalnum():
            raise HTTPException(404)
        data = await request.json()
        if set(data) != {'expected_hash', 'approve'} or type(data['approve']) is not bool:
            raise HTTPException(400)
        return await backend('/api/sales/knowledge/' + identifier + '/review', data)
    return app


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(sales_app(), host='127.0.0.1', port=8773, ws_max_size=8_000_000)
