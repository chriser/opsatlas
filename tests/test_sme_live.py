"""Duplex transport shares revision guards and lets controls overtake slow work."""
import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from services.sme_interviewer.answer_check import AnswerCheck
from services.sme_interviewer.app import create_app


@pytest.fixture
def setup(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app, base_url='http://127.0.0.1') as client:
        token = client.get('/api/bootstrap').json()['token']
        client.headers['x-sme-token'] = token
        session = client.post('/api/interviews', json={'accept_synthetic_storage': True,
                              'request_id': str(uuid.uuid4()), 'scope': {'region': 'unknown', 'variant': 'unknown', 'date': ''}}).json()
        yield client, app, token, session


def connect(client, session):
    return client.websocket_connect('ws://127.0.0.1/api/live/' + session['id'], headers={'origin': 'http://127.0.0.1'})


def command(ws, session, suffix, body, rid='1'):
    ws.send_json({'id': rid, 'path': '/api/interviews/' + session['id'] + suffix, 'method': 'POST',
                  'session_id': session['id'], 'turn_id': 'turn-1', 'generation_id': 'gen-1',
                  'revision': session['revision'], 'body': body})


def reply(ws, rid='1'):
    for _ in range(20):
        event = ws.receive_json()
        if event['type'] == 'reply' and event['id'] == rid:
            return event
    raise AssertionError('Missing reply')


def test_auth_origin_and_single_owner(setup):
    client, app, token, session = setup
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect('ws://127.0.0.1/api/live/' + session['id'], headers={'origin': 'https://attacker.example'}):
            pass
    with connect(client, session) as ws:
        ws.send_json({'token': 'wrong'})
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()
    with connect(client, session) as ws:
        ws.send_json({'token': token})
        assert ws.receive_json()['type'] == 'hello'
        with connect(client, session) as other:
            other.send_json({'token': token})
            with pytest.raises(WebSocketDisconnect):
                other.receive_json()
        assert app.state.interviews.store.get(session['id'])['status'] == 'active'
    assert app.state.interviews.store.get(session['id'])['status'] == 'paused'


def test_revision_idempotency_and_reconnect_snapshot(setup):
    client, app, token, session = setup
    with connect(client, session) as ws:
        ws.send_json({'token': token})
        ws.receive_json()
        body = {'expected_revision': session['revision'], 'request_id': str(uuid.uuid4()),
                'segment': {'text': 'The approver checked the record.', 'kind': 'reported_practice', 'state': 'confirmed'}}
        command(ws, session, '/segments', body)
        first = reply(ws)
        assert first['status'] == 200 and len(first['data']['segments']) == 1
        command(ws, session, '/segments', body, '2')
        assert len(reply(ws, '2')['data']['segments']) == 1
        body['request_id'] = str(uuid.uuid4())
        command(ws, session, '/segments', body, '3')
        assert reply(ws, '3')['status'] == 409
    with connect(client, session) as ws:
        ws.send_json({'token': token})
        snapshot = ws.receive_json()['data']
        assert snapshot['status'] == 'paused'
        assert len(snapshot['segments']) == 1


def test_pause_overtakes_inflight_answer_check(setup):
    client, app, token, session = setup
    class SlowCheck:
        async def check(self, *args):
            await asyncio.sleep(30)
            return AnswerCheck.result('responsive')
    app.state.interviews.answer_check = SlowCheck()
    with connect(client, session) as ws:
        ws.send_json({'token': token})
        ws.receive_json()
        command(ws, session, '/assess', {'expected_revision': session['revision'], 'text': 'A response'}, 'slow')
        command(ws, session, '/pause', {}, 'pause')
        assert reply(ws, 'pause')['data']['status'] == 'paused'
    assert app.state.interviews.store.get(session['id'])['segments'] == []


def test_cross_session_command_rejected(setup):
    client, app, token, session = setup
    with connect(client, session) as ws:
        ws.send_json({'token': token})
        ws.receive_json()
        command(ws, session, '/../another/pause', {})
        assert reply(ws)['status'] == 400


def test_fast_audio_completion_has_turn_identity_and_disconnect_cancels_it(setup):
    client, app, token, session = setup
    class Worker:
        async def synthesize(self, candidate, text, output):
            output.write_bytes(b'synthetic audio')
            return {'total_ms': 1}
    app.state.manager.workers = {key: Worker() for key in app.state.manager.workers}
    # Restore closable workers before app shutdown.
    async def close():
        pass
    for worker in app.state.manager.workers.values():
        worker.close = close
    with connect(client, session) as ws:
        ws.send_json({'token': token})
        ws.receive_json()
        ws.send_json({'id': 'audio', 'path': '/api/turns', 'method': 'POST', 'session_id': session['id'],
                      'turn_id': 'turn-audio', 'generation_id': 'generation-audio', 'revision': 7,
                      'body': {'candidate': 'B', 'text': 'What happened next?'}})
        created = reply(ws, 'audio')
        assert created['revision'] == 7
        while True:
            event = ws.receive_json()
            if event['type'] == 'audio':
                break
        assert event['data']['state'] == 'ready'
        assert event['turn_id'] == 'turn-audio' and event['revision'] == 7
        assert 'path' not in event['data'] and 'task' not in event['data']
        job = created['data']['id']
    assert app.state.manager.jobs[job]['state'] == 'cancelled'


def test_assessment_of_a_correction_uses_its_original_question(setup):
    client, app, token, session = setup
    store = app.state.interviews.store
    pending = store.mutate(session['id'], session['revision'], str(uuid.uuid4()), 'plan_requested', {})
    store.apply_plan(session['id'], pending['revision'], {'question': 'story', 'observations': [], 'mode': 'guided'})
    current = store.get(session['id'])
    original = current['current_question']['text']
    current = store.mutate(session['id'], current['revision'], str(uuid.uuid4()), 'segment_saved',
                           {'text': 'An older answer.', 'kind': 'reported_practice', 'state': 'confirmed'})
    target = current['segments'][0]
    calls = []
    class Check:
        async def check(self, *args):
            calls.append(args)
            return AnswerCheck.result('responsive')
    app.state.interviews.answer_check = Check()
    result = client.post('/api/interviews/' + session['id'] + '/assess', json={
        'expected_revision': current['revision'], 'segment_id': target['id'], 'text': 'Corrected wording.'})
    assert result.status_code == 200
    assert calls[0][:3] == (original, 'Corrected wording.', '')
    assert store.get(session['id'])['segments'][0]['text'] == 'An older answer.'
