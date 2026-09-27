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
    POST /api/text/sessions             a typed conversation with Tibi's engine, no audio (the Digital SME's channel)
    POST /api/text/sessions/{id}/turns  one typed turn: the reply, its route and the records it used
    POST /api/text/sessions/{id}/close  end it
"""
import json
import logging
import os

import httpx
from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse

from services.opsatlas_sales.workspace import workspace

from .app import create_app
from .evidence import digest
from .governance_interviewer import GovernanceInterviewer
from .product_interviewer import ProductInterviewer
from .rehearsal import RehearsalCoach
from .speech import ROOT
from .text_channel import TextChannel
from .tibi import Tibi

# Words whisper would otherwise mishear; Tibi's own names first among them (for name activation too).
VOCABULARY = 'OpsAtlas, Ops Atlas, Tiberius, Tibi, ontology, retrieval, SharePoint, single sign-on.'


class SalesEvidence:
    def snapshot(self):
        pack = {'schema': 1, 'id': 'opsatlas-sales', 'mode': 'sales_rehearsal', 'title': 'OpsAtlas product knowledge',
                'scope': {'topic': 'OpsAtlas'}, 'sources': [],
                'notice': 'Internal product rehearsal. Evidence is checked per answer; conversation does not publish knowledge.'}
        return {**pack, 'hash': digest(pack)}

    def current(self, snapshot):
        return {k: v for k, v in snapshot.items()
                if k not in ('product_interview', 'governance_interview', 'sales_rehearsal')} == self.snapshot()


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
                      SME_ASR_VOCABULARY=VOCABULARY)
    # Voice-rating experiments run from experience.voice_ratings on their own port; the live
    # service no longer mounts them or writes into the shared experiment runtime.
    app = create_app(runtime, evidence=SalesEvidence())
    credential = (root / 'local-access.key').read_text().strip()
    # Timestamps on the service log, and Tibi's side of the activity log and the conversation log (OBS S4, S6).
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    from services.opsatlas_sales.activity import ActivityLog

    from .engine import current as engine
    app.state.interviews.activity = ActivityLog(root, 'tibi', secrets=(credential,))
    app.state.interviews.conversation_log = root
    # What this process is, captured once as it starts (audit F10): kept with the logs, served at /api/manifest.
    from .manifest import build as build_manifest
    app.state.manifest = build_manifest(runtime)
    manifests = root / 'logs' / 'manifests'
    manifests.mkdir(parents=True, exist_ok=True)
    (manifests / f"{app.state.manifest['id']}.json").write_text(json.dumps(app.state.manifest, indent=1) + '\n')
    app.state.interviews.activity.write('tibi', event='Tibi service started', pid=os.getpid(), engine=engine(),
                                        manifest=app.state.manifest['id'])
    app.state.interviews.companion_factory = lambda history: Tibi(history, credential, base_url)
    app.state.interviews.product_companion_factory = lambda session: ProductInterviewer(session, credential, base_url)
    app.state.interviews.governance_companion_factory = lambda session: GovernanceInterviewer(session, credential, base_url)
    # Sales rehearsal (TIBI E3): Tibi listens to the pitch and helps only when asked.
    app.state.interviews.rehearsal_companion_factory = lambda session: RehearsalCoach(
        session.get('social_dialogue'), credential, base_url, customer=session['evidence']['sales_rehearsal'].get('customer', ''))

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

    @app.get('/api/manifest')
    async def manifest():
        return app.state.manifest

    @app.get('/api/health')
    async def health():
        from .engine import fingerprint
        running = engine()
        return {'service': 'tibi', 'status': 'ok', 'workspace': 'opsatlas-sales', 'api_version': 1,
                'manifest': app.state.manifest['id'],
                # The code on disk no longer being what this process runs (a merge before a restart) is shown, not hidden.
                'changed_on_disk': fingerprint() != running['fingerprint'],
                'modes': ['chat', 'product_interview', 'governance_interview', 'rehearsal', 'digital_sme'],
                'sessions': app.state.interviews.store.capacity(),
                'engine': {k: engine()[k] for k in ('version', 'released', 'fingerprint', 'models', 'matches_release')}}

    @app.get('/api/contributions')
    async def contributions():
        store = app.state.interviews.store
        # Archived sessions too: archiving frees a working slot, never hides a contribution (audit F11).
        sessions = [store.get(s['id']) for s in store.list(include_archived=True, limit=None)]
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

    # The Digital SME asks the same engine by text and has the avatar speak the reply (DSME S1).
    channel = TextChannel(lambda history: app.state.interviews.companion_factory(history), root, app.state.interviews.activity)
    app.state.text_channel = channel

    @app.post('/api/text/sessions')
    async def open_text(request: Request):
        data = await request.json()
        kind = data.get('channel', 'digital_sme') if isinstance(data, dict) else 'digital_sme'
        if kind not in ('digital_sme', 'typed'):
            raise HTTPException(400, 'Unknown channel')
        try:
            return channel.open(kind)
        except OverflowError as exc:
            raise HTTPException(429, str(exc)) from exc

    @app.post('/api/text/sessions/{identifier}/turns')
    async def text_turn(identifier: str, request: Request):
        data = await request.json()
        text = data.get('text') if isinstance(data, dict) else None
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 1200:
            raise HTTPException(400, 'Ask a question of up to 1,200 characters.')
        try:
            return await channel.turn(identifier, text)
        except KeyError as exc:
            raise HTTPException(404, 'That conversation has ended. Start a new one.') from exc
        except TimeoutError as exc:
            channel.log('turn timed out', session=identifier)
            raise HTTPException(504, 'Tibi took too long to answer. The model server may be busy; try again.') from exc
        except Exception as exc:
            channel.log('turn failed', session=identifier, error=type(exc).__name__)
            logging.getLogger(__name__).warning('Text turn failed: %s', type(exc).__name__)
            raise HTTPException(502, 'Tibi could not prepare a reply just then. Please try again.') from exc

    @app.post('/api/text/sessions/{identifier}/close')
    async def close_text(identifier: str):
        return {'closed': channel.close(identifier)}
    return app


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(sales_app(), host='127.0.0.1', port=8773, ws_max_size=8_000_000)
