"""Tibi, the voice companion, as a service.

This process owns Tibi's conversations: the voice loop (speech recognition, the local model and the
Higgs voice), chat, product interviews and governance interviews, and what those interviews capture.
It has no pages. People use Tibi in the OpsAtlas control panel, which reaches this service only through
its gateway (/services/tibi on the control panel's origin). Tibi reads OpsAtlas knowledge, and proposes
additions to it, only through the OpsAtlas knowledge API.

API, local only:
    GET  /api/health                    service identity and readiness
    GET  /api/bootstrap                 token required on every change
    /api/interviews...                  conversation sessions (create, open, pause, resume, timings)
    WS   /api/conversation/{id}         the live voice loop
    GET  /api/contributions             product-interview contributions awaiting a proposal
    POST /api/contributions/propose     propose a contribution to OpsAtlas as a pending claim
    POST /api/spoken/draft              draft spoken wording for enabled records (stored pending in OpsAtlas)
"""
import os

import httpx
from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse

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

    home = base_url.rstrip('/')

    @app.middleware('http')
    async def no_pages(request, call_next):
        # Tibi is used in the OpsAtlas control panel: anything that is not the API goes there.
        path = request.url.path
        if not path.startswith('/api/'):
            return RedirectResponse(home + ('/#tibi-knowledge' if path == '/knowledge' else '/#tibi'))
        return await call_next(request)

    @app.get('/api/health')
    async def health():
        return {'service': 'tibi', 'status': 'ok', 'workspace': 'opsatlas-sales', 'api_version': 1,
                'modes': ['chat', 'product_interview', 'governance_interview']}

    @app.get('/api/contributions')
    async def contributions():
        store = app.state.interviews.store
        sessions = [store.get(s['id']) for s in store.list()]
        return {'turns': [{**turn, 'session_id': s['id']} for s in sessions for turn in s.get('product_turns', [])]}

    @app.post('/api/contributions/propose')
    async def propose(request: Request):
        data = await request.json()
        try:
            session = app.state.interviews.store.get(data['session_id'])
            turn = next(t for t in session.get('product_turns', []) if t['id'] == data['turn_id'])
            # Attribution and the original transcript come from the saved interview, never the browser.
            payload = {k: turn[k] for k in ('contributor', 'topic', 'question', 'raw_text', 'issue')}
            payload.update({k: data[k] for k in ('session_id', 'turn_id', 'text', 'status', 'expected_hash', 'wording_confirmed')})
        except (KeyError, StopIteration, TypeError) as exc:
            raise HTTPException(400, 'Select a saved contribution') from exc
        return await backend('/api/sales/proposals', payload)

    @app.post('/api/spoken/draft')
    async def draft_spoken():
        # Drafts are checked against their record by OpsAtlas and stay pending until reviewed there.
        return await Tibi([], credential, base_url).draft_spoken()
    return app


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(sales_app(), host='127.0.0.1', port=8773, ws_max_size=8_000_000)
