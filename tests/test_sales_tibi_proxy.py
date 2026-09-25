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


class Auth:
    """The OpsAtlas sign-in, reduced to one valid token."""

    @staticmethod
    def validate(token):
        return token == 'signed-in'


def gateway(voice):
    app = FastAPI()
    app.state.auth = Auth()
    tibi_proxy.attach(app, voice)
    return app


def test_the_gateway_needs_the_sign_in_and_keeps_tibis_own_checks(tmp_path, monkeypatch):
    from services.sme_interviewer.sales_preview import sales_app
    monkeypatch.setattr(os, 'environ', os.environ.copy())
    tibi = sales_app(tmp_path / 'sales', 'http://127.0.0.1:8780')
    original = httpx.AsyncClient
    monkeypatch.setattr(tibi_proxy.httpx, 'AsyncClient',
                        lambda **kw: original(**{**kw, 'transport': httpx.ASGITransport(app=tibi)}))
    signed = {'Authorization': 'Bearer signed-in'}
    with TestClient(gateway('http://127.0.0.1:8773'), base_url='http://127.0.0.1:8780') as client:
        assert client.get('/services/tibi/api/health').status_code == 401
        assert client.get('/services/tibi/api/health', headers={'Authorization': 'Bearer nope'}).status_code == 401
        assert client.get('/services/tibi/api/health', headers=signed).json()['service'] == 'tibi'
        token = client.get('/services/tibi/api/bootstrap', headers=signed).json()['token']
        body = {'request_id': str(uuid.uuid4()), 'accept_local_storage': True,
                'scope': {'region': 'unknown', 'variant': 'unknown', 'date': ''}}
        origin = {**signed, 'origin': 'http://127.0.0.1:8780'}
        # Tibi's own session token is still required on every change.
        assert client.post('/services/tibi/api/interviews', json=body, headers=origin).status_code == 403
        created = client.post('/services/tibi/api/interviews', json=body, headers={**origin, 'x-sme-token': token})
        assert created.status_code == 200 and created.json()['id']
        # Only Tibi's API is reachable through the gateway.
        assert client.get('/services/tibi/conversation', headers=signed).status_code == 404


def test_the_gateway_reports_a_stopped_tibi_service():
    with TestClient(gateway('http://127.0.0.1:9'), base_url='http://127.0.0.1:8780') as client:
        response = client.get('/services/tibi/api/health', headers={'Authorization': 'Bearer signed-in'})
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

    client = TestClient(gateway(voice_socket_server))
    origin = {'origin': 'http://127.0.0.1:8780'}
    with client.websocket_connect(SOCKET, headers=origin) as ws:
        ws.send_text(json.dumps({'opsatlas_token': 'signed-in', 'token': 'tibi-token'}))
        # Tibi receives its own hello, without the OpsAtlas sign-in.
        assert json.loads(ws.receive_text().split(':', 1)[1]) == {'token': 'tibi-token'}
        ws.send_text('hello')
        assert ws.receive_text() == 's1:hello'
        ws.send_text('refuse')
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_text()
        assert closed.value.code == 1008
    for hello, headers in (({'opsatlas_token': 'wrong', 'token': 't'}, origin),
                           ({'opsatlas_token': 'signed-in', 'token': 't'}, {'origin': 'http://evil.test'})):
        with pytest.raises(WebSocketDisconnect) as refused:
            with client.websocket_connect(SOCKET, headers=headers) as ws:
                ws.send_text(json.dumps(hello))
                ws.receive_text()
        assert refused.value.code == 1008
