"""Tiberius voice front end; same-origin review proxy to the isolated Atlas core."""
import os

import httpx
from fastapi import HTTPException
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from services.opsatlas_sales.workspace import workspace

from .app import create_app
from .evidence import digest
from .governance_interviewer import GovernanceInterviewer
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
        return {k: v for k, v in snapshot.items() if k not in ('product_interview', 'governance_interview')} == self.snapshot()


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
                      SME_DEFER_REVIEWS='1', SME_LISTENER_LAB='1',
                      SME_ASR_VOCABULARY='OpsAtlas, Ops Atlas, Tiberius, Tibi, ontology, retrieval, SharePoint, single sign-on.')
    # Voice-rating experiments run from experience.voice_ratings on their own port; the live
    # service no longer mounts them or writes into the shared experiment runtime.
    app = create_app(runtime, evidence=SalesEvidence())
    credential = (root / 'local-access.key').read_text().strip()
    app.state.interviews.companion_factory = lambda history: Tibi(history, credential, base_url)
    app.state.interviews.product_companion_factory = lambda session: ProductInterviewer(session, credential, base_url)
    app.state.interviews.governance_companion_factory = lambda session: GovernanceInterviewer(session, credential, base_url)

    async def backend(path, body=None):
        async with httpx.AsyncClient(base_url=base_url, timeout=5, trust_env=False) as client:
            headers = {'x-sales-token': credential}
            response = await (client.get(path, headers=headers) if body is None else client.post(path, headers=headers, json=body))
            if response.status_code >= 400:
                raise HTTPException(response.status_code, response.json().get('detail', 'Refresh and review the evidence.'))
            return response.json()

    # Tibi lives inside the OpsAtlas control panel. This service serves the embedded conversation only;
    # its former stand-alone pages send people to the matching OpsAtlas page.
    home = base_url.rstrip('/')
    port = home.rsplit(':', 1)[-1]
    ancestors = f'http://127.0.0.1:{port} http://localhost:{port}'

    @app.middleware('http')
    async def entry(request, call_next):
        path = request.url.path
        if path in ('/', '/knowledge', '/interview', '/social-voices') or (
                path == '/conversation' and request.query_params.get('embed') != '1'):
            return RedirectResponse(home + ('/#tibi-knowledge' if path == '/knowledge' else '/#tibi'))
        if path == '/conversation':
            if request.query_params.get('social') != '1' or request.query_params.get('sales') != '1':
                query = dict(request.query_params, social='1', sales='1')
                return RedirectResponse('/conversation?' + '&'.join(f'{k}={v}' for k, v in query.items()))
            html = (ROOT / 'web/conversation.html').read_text()
            start = html.index('<select id="social-voice">')
            end = html.index('</select>', start) + len('</select>')
            html = html[:start] + ('<select id="social-voice"><option value="higgs">Higgs · selected male voice</option>'
                                   '<option value="higgs_female">Higgs · female alternative</option></select>') + html[end:]
            html = html.replace('href="/social-voices"', 'href="http://127.0.0.1:8774/higgs-voices"')
            response = HTMLResponse(html.replace('</head>', '<script src="/sales.js" defer></script></head>'))
            # Only the OpsAtlas control panel may embed the conversation.
            response.headers['Content-Security-Policy'] = f'frame-ancestors {ancestors}'
            return response
        return await call_next(request)

    @app.get('/sales.js')
    async def script():
        return FileResponse(ROOT / 'web/sales.js')

    @app.get('/api/sales/knowledge')
    async def knowledge():
        # The session picker needs the topics and how many records are enabled.
        return await backend('/api/sales/knowledge')
    return app


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(sales_app(), host='127.0.0.1', port=8773, ws_max_size=8_000_000)
