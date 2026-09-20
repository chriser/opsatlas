import json

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from services.sme_interviewer.experience.app import create_app


def test_lab_local_boundary_and_rating_validation(tmp_path):
    client = TestClient(create_app(tmp_path), base_url='http://127.0.0.1:8769')
    catalog = client.get('/api/catalog').json()
    headers = {'x-lab-token': catalog['token']}
    value = {'alias': 'A', 'prompt': 'pronunciation', 'naturalness': 4, 'pronunciation': 3, 'accent': 4, 'pace': 5}
    assert client.post('/api/rating', json=value).status_code == 403
    assert client.post('/api/rating', json=value, headers={**headers, 'origin': 'https://example.com'}).status_code == 403
    assert client.get('/api/catalog', headers={'host': 'example.com'}).status_code == 400
    assert client.post('/api/rating', json={**value, 'pace': True}, headers=headers).status_code == 422
    assert client.post('/api/rating', json=value, headers=headers).status_code == 200
    saved = json.loads((tmp_path / 'ratings.jsonl').read_text())
    assert saved['candidate'] and saved['naturalness'] == 4
    assert client.get('/audio/A/unknown').status_code == 404
    assert client.get('/assets/app.py').status_code == 404
    assert client.post('/api/endpoint', content=b'a' * 512004, headers=headers).status_code == 413
    assert client.post('/api/endpoint', content=b'abcd', headers=headers).status_code == 422
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect('ws://127.0.0.1:8769/api/vad', headers={'origin': 'https://example.com'}):
            pass
    with client.websocket_connect('ws://127.0.0.1:8769/api/vad', headers={'origin': 'http://127.0.0.1:8769'}) as socket:
        socket.send_text('wrong token')
        with pytest.raises(WebSocketDisconnect):
            socket.receive_json()
