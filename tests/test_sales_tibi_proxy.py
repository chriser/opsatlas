"""The OpsAtlas gateway to the Tibi service (/services/tibi): sign-in, forwarding and the live voice socket."""
import json
import os
import socket
import threading
import time
import uuid

import httpx
import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient

from services.opsatlas_sales import tibi_proxy

SOCKET = 'ws://127.0.0.1:8780/services/tibi/api/conversation/s1'  # the control panel's own origin


PW = 'operator secret'


def gateway(voice, activity=None):
    """A bare app with the OpsAtlas sign-in (the legacy single operator) and the gateway attached."""
    from assistant.api.auth import AuthService
    app = FastAPI()
    app.state.auth = AuthService(PW)
    app.state.token = app.state.auth.login(PW)
    tibi_proxy.attach(app, voice, activity)
    return app


def signed(app):
    return {'Authorization': f"Bearer {app.state.token}"}


def ticket(app, conversation='s1'):
    """A one-use socket ticket for the signed-in operator (IAM F6)."""
    _, session = app.state.auth.iam.resolve(app.state.token, touch=False)
    return app.state.auth.iam.issue_ticket(session, conversation, 'default')


def test_the_gateway_needs_the_sign_in_and_keeps_tibis_own_checks(tmp_path, monkeypatch):
    from services.sme_interviewer.sales_preview import sales_app
    monkeypatch.setattr(os, 'environ', os.environ.copy())
    tibi = sales_app(tmp_path / 'sales', 'http://127.0.0.1:8780')
    original = httpx.AsyncClient
    monkeypatch.setattr(tibi_proxy.httpx, 'AsyncClient',
                        lambda **kw: original(**{**kw, 'transport': httpx.ASGITransport(app=tibi)}))
    app = gateway('http://127.0.0.1:8773')
    with TestClient(app, base_url='http://127.0.0.1:8780') as client:
        assert client.get('/services/tibi/api/health').status_code == 401
        assert client.get('/services/tibi/api/health', headers={'Authorization': 'Bearer nope'}).status_code == 401
        assert client.get('/services/tibi/api/health', headers=signed(app)).json()['service'] == 'tibi'
        token = client.get('/services/tibi/api/bootstrap', headers=signed(app)).json()['token']
        body = {'request_id': str(uuid.uuid4()), 'accept_local_storage': True,
                'scope': {'region': 'unknown', 'variant': 'unknown', 'date': ''}}
        origin = {**signed(app), 'origin': 'http://127.0.0.1:8780'}
        # Tibi's own session token is still required on every change.
        assert client.post('/services/tibi/api/interviews', json=body, headers=origin).status_code == 403
        created = client.post('/services/tibi/api/interviews', json=body, headers={**origin, 'x-sme-token': token})
        assert created.status_code == 200 and created.json()['id']
        # Only Tibi's API is reachable through the gateway.
        assert client.get('/services/tibi/conversation', headers=signed(app)).status_code == 404


def test_the_gateway_reports_a_stopped_tibi_service():
    app = gateway('http://127.0.0.1:9')
    with TestClient(app, base_url='http://127.0.0.1:8780') as client:
        response = client.get('/services/tibi/api/health', headers=signed(app))
        assert response.status_code == 502 and 'not running' in response.json()['detail']


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


@pytest.fixture
def voice_socket_server():
    """A stand-in Tibi service: checks host and origin like the real one, echoes, and closes with a code."""
    import uvicorn

    upstream = FastAPI()

    @upstream.websocket('/api/conversation/{identifier}')
    async def conversation(ws: WebSocket, identifier: str):
        if ws.headers.get('origin') != 'http://' + ws.headers.get('host', ''):
            await ws.close(code=1008)
            return
        await ws.accept()
        while True:
            text = await ws.receive_text()
            if text == 'refuse':
                await ws.close(code=1008, reason='refused')
                return
            if text == 'status':  # what the real Tibi sends while it works, and a reply with its words
                await ws.send_text(json.dumps({'type': 'state', 'state': 'thinking', 'message': 'Considering what you said…'}))
                await ws.send_text(json.dumps({'type': 'social_reply', 'reply': 'Private words.', 'route': 'conversation'}))
                continue
            await ws.send_text(f'{identifier}:{text}')

    port = free_port()
    server = uvicorn.Server(uvicorn.Config(upstream, host='127.0.0.1', port=port, log_level='warning'))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    yield f'http://127.0.0.1:{port}'
    server.should_exit = True
    thread.join(5)


def test_the_live_voice_socket_needs_the_sign_in_and_passes_tibis_close_code(voice_socket_server):
    from starlette.websockets import WebSocketDisconnect

    app = gateway(voice_socket_server)
    client = TestClient(app)
    origin = {'origin': 'http://127.0.0.1:8780'}
    with client.websocket_connect(SOCKET, headers=origin) as ws:
        ws.send_text(json.dumps({'opsatlas_ticket': ticket(app), 'token': 'tibi-token'}))
        # Tibi receives its own hello, without the OpsAtlas sign-in.
        assert json.loads(ws.receive_text().split(':', 1)[1]) == {'token': 'tibi-token'}
        ws.send_text('hello')
        assert ws.receive_text() == 's1:hello'
        ws.send_text('refuse')
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_text()
        assert closed.value.code == 1008
    used = ticket(app)
    app.state.auth.iam.consume_ticket(used, 's1')  # a ticket works once
    for hello, headers in (({'opsatlas_ticket': 'wrong', 'token': 't'}, origin),
                           ({'opsatlas_ticket': used, 'token': 't'}, origin),
                           ({'opsatlas_ticket': ticket(app, 'other-conversation'), 'token': 't'}, origin),
                           ({'opsatlas_token': app.state.token, 'token': 't'}, origin),
                           ({'opsatlas_ticket': ticket(app), 'token': 't'}, {'origin': 'http://evil.test'})):
        with pytest.raises(WebSocketDisconnect) as refused:
            with client.websocket_connect(SOCKET, headers=headers) as ws:
                ws.send_text(json.dumps(hello))
                ws.receive_text()
        assert refused.value.code == 1008


def test_the_voice_socket_is_recorded_in_the_activity_log_without_the_conversation(voice_socket_server, tmp_path):
    from starlette.websockets import WebSocketDisconnect

    from services.opsatlas_sales.activity import ActivityLog, read
    app = gateway(voice_socket_server, ActivityLog(tmp_path, 'core'))
    client = TestClient(app)
    origin = {'origin': 'http://127.0.0.1:8780'}
    first = ticket(app)
    with client.websocket_connect(SOCKET, headers=origin) as ws:
        ws.send_text(json.dumps({'opsatlas_ticket': first, 'token': 'tibi-token', 'social_voice': 'higgs'}))
        ws.receive_text()
        ws.send_text('status')
        ws.receive_text()
        ws.receive_text()
        ws.send_text('refuse')
        with pytest.raises(WebSocketDisconnect):
            ws.receive_text()
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(SOCKET, headers=origin) as ws:
            ws.send_text(json.dumps({'opsatlas_ticket': 'wrong'}))
            ws.receive_text()
    events = read(tmp_path)
    names = [e['event'] for e in events]
    assert names[:3] == ['opened', 'connected to Tibi', 'tibi: state'] and 'tibi: social_reply' in names
    assert next(e for e in events if e['event'] == 'tibi: state')['message'] == 'Considering what you said…'
    closed = next(e for e in events if e['event'] == 'closed')
    assert closed['code'] == 1008 and closed['reason'] == 'refused' and closed['seconds'] >= 0
    assert 'refused: not signed in' in names
    assert next(e for e in events if e['event'] == 'connected to Tibi')['hello'] == {'social_voice': 'higgs'}
    written = ''.join(
        f.read_text() for f in (tmp_path / 'logs' / 'activity').glob('*.jsonl'))
    assert 'Private words' not in written and 'tibi-token' not in written and first not in written and app.state.token not in written


# ---- REF S2: only the listed paths, and the organisation's space checked ----------------------------------------

def fake_tibi(calls):
    """A stand-in Tibi service that records what reaches it: interview a1 is held in alpha, b1 in beta."""
    held = {'a1': 'alpha', 'b1': 'beta'}
    tibi = FastAPI()

    @tibi.get('/api/process-interviews')
    def listing(space: str):
        calls.append(('list', space))
        return {'interviews': [{'id': i} for i, s in held.items() if s == space]}

    @tibi.get('/api/interviews/{identifier}')
    def one(identifier: str):
        calls.append(('get', identifier))
        return {'id': identifier, 'evidence': {'process_interview': {'space': held[identifier]}}}

    @tibi.delete('/api/process-interviews/{identifier}')
    def delete(identifier: str):
        calls.append(('delete', identifier))
        return {'deleted': identifier}

    @tibi.post('/api/interviews')
    def create():
        calls.append(('create',))
        return {'id': 'new'}

    @tibi.get('/api/models')
    def models():
        calls.append(('models',))
        return {}

    return tibi


@pytest.fixture
def two_organisations(tmp_path, monkeypatch):
    """The sales workspace with organisations alpha and beta, and a person who reads alpha only."""
    from assistant.iam.service import Actor
    from services.opsatlas_sales.app import create_sales_app
    from tests.iam_helpers import sign_in

    monkeypatch.setattr(os, 'environ', os.environ.copy())
    os.environ['SME_TIBI_VOICE_URL'] = 'http://127.0.0.1:8773'
    os.environ['SALES_GOVERNANCE_AUTO_REVIEW'] = '0'
    calls = []
    original = httpx.AsyncClient
    monkeypatch.setattr(tibi_proxy.httpx, 'AsyncClient',
                        lambda **kw: original(**{**kw, 'transport': httpx.ASGITransport(app=fake_tibi(calls))}))
    app = create_sales_app(tmp_path / 'sales')
    with TestClient(app, base_url='http://127.0.0.1:8780') as client:
        admin = {'Authorization': f'Bearer {sign_in(client, app)}'}
        for name in ('Alpha', 'Beta'):
            assert client.post('/api/spaces', json={'name': name}, headers=admin).status_code == 200
        iam = app.state.auth.iam
        admin_id = iam.store.one('SELECT id FROM users WHERE login = ?', ('operator@example.test',))['id']
        invited = iam.invite(Actor(admin_id, fresh=True), email='reader@alpha.test', display_name='Reader',
                             role_id='space_reader', space_id='alpha')
        iam.accept_invitation(invited['token'], 'a long enough password for tests')
        reader = {'Authorization': f"Bearer {sign_in(client, app, 'reader@alpha.test', 'a long enough password for tests')}"}
        yield client, admin, reader, calls


def test_the_gateway_forwards_only_the_listed_tibi_paths(two_organisations):
    client, admin, _, calls = two_organisations
    assert client.get('/services/tibi/api/models', headers=admin).status_code == 404
    assert client.post('/services/tibi/api/turns', headers=admin).status_code == 404
    assert calls == []  # refused before reaching Tibi
    assert client.get('/services/tibi/api/process-interviews?space=beta', headers=admin).status_code == 200


def test_a_reader_of_one_organisation_cannot_reach_anothers_interviews(two_organisations):
    client, _, reader, calls = two_organisations
    own = client.get('/services/tibi/api/process-interviews?space=alpha', headers=reader)
    assert own.status_code == 200 and own.json()['interviews'] == [{'id': 'a1'}]
    # Another organisation's listing, interview and deletion all answer 404, and nothing of beta's is fetched.
    assert client.get('/services/tibi/api/process-interviews?space=beta', headers=reader).status_code == 404
    assert ('list', 'beta') not in calls
    assert client.get('/services/tibi/api/interviews/b1', headers=reader).status_code == 404
    assert client.delete('/services/tibi/api/process-interviews/b1', headers=reader).status_code == 404
    assert ('delete', 'b1') not in calls
    # A reader may see alpha's interview but not change it, and may not start one in beta.
    assert client.get('/services/tibi/api/interviews/a1', headers=reader).status_code == 200
    assert client.delete('/services/tibi/api/process-interviews/a1', headers=reader).status_code == 403
    started = client.post('/services/tibi/api/interviews', headers=reader,
                          json={'process_interview': {'space': 'beta', 'space_name': 'Beta'}})
    assert started.status_code == 404 and ('create',) not in calls
