"""Turn diagnostics must be honest about eligibility and independent of claim state."""

import copy
import uuid

import pytest
from fastapi.testclient import TestClient

from services.sme_interviewer.app import create_app
from services.sme_interviewer.timing import MARKS, TimingStore, report, validate


def record(**changes):
    return dict(version=1, id='turn-1', page_id='page-1', generation_id='generation-1', revision=1,
                sequence=1, source='microphone', runtime='unknown', endpoint_kind='manual_stop', status='open',
                marks=dict.fromkeys(MARKS), **changes)


def completed(identifier='turn-1', delay=2000):
    data = record()
    data.update(id=identifier, status='complete')
    data['marks'].update(endpoint=100, final_transcript=200, confirmation_start=200, confirmed=500,
                         plan_requested=500, question_ready=1000, tts_requested=1000,
                         audio_ready=1500, first_audio=1600, playback_start=100+delay)
    return data


def test_manual_timing_never_becomes_acoustic_or_warm_evidence():
    a, b = completed(), completed('turn-2', 4000)
    failed = record()
    failed.update(id='failed', status='failed')
    output = report([a, b, failed])
    group = output['groups'][0]
    assert group['runtime'] == 'unknown'
    assert group['attempts'] == 3
    assert group['outcomes'] == {'complete': 2, 'failed': 1}
    assert group['metrics']['manual_stop_to_playback'] == {'n': 2, 'p50_ms': 2000, 'p95_ms': 4000}
    assert group['metrics']['speech_end_to_playback']['n'] == 0
    assert group['metrics']['confirmation_wait']['p50_ms'] == 300


def test_no_success_percentiles_from_text_cancellations_or_replays():
    values = []
    for state in ('open', 'text_only', 'failed', 'interrupted', 'abandoned'):
        data = completed(state)
        data['status'] = state
        values.append(data)
    replay = completed('replay')
    replay['source'] = 'replay'
    values.append(replay)
    for group in report(values)['groups']:
        assert group['metrics']['manual_stop_to_playback']['n'] == 0
        assert group['metrics']['speech_end_to_playback']['n'] == 0


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -1, True, '10', 86400001])
def test_invalid_clock_values_rejected(value):
    data = record()
    data['marks']['endpoint'] = value
    with pytest.raises(ValueError):
        validate(data)


def test_milestone_order_and_no_unmeasured_completion():
    data = completed()
    data['marks']['first_audio'] = 90
    with pytest.raises(ValueError):
        validate(data)
    data = record()
    data['status'] = 'complete'
    with pytest.raises(ValueError):
        validate(data)


def test_no_text_or_arbitrary_payload_in_diagnostics():
    data = record()
    data['transcript'] = 'Private wording'
    with pytest.raises(ValueError):
        validate(data)


def test_delayed_snapshots_cannot_undo_completed_record(tmp_path):
    store = TimingStore(tmp_path / 'timings.sqlite')
    initial = record()
    initial['marks']['endpoint'] = 100
    store.save('session', initial)
    final = completed()
    final['sequence'] = 5
    store.save('session', final)
    assert store.save('session', initial) == {'saved': False}
    assert store.export('session')['records'] == [final]
    mutated = copy.deepcopy(final)
    mutated['sequence'] = 6
    mutated['marks']['endpoint'] = 0
    with pytest.raises(ValueError):
        store.save('session', mutated)
    assert TimingStore(store.path).export('session')['records'] == [final]


def test_timing_api_preserves_ledger_and_requires_local_token(tmp_path):
    with TestClient(create_app(tmp_path), base_url='http://127.0.0.1') as client:
        token = client.get('/api/bootstrap').json()['token']
        headers = {'x-sme-token': token}
        session = client.post('/api/interviews', headers=headers, json={
            'request_id': str(uuid.uuid4()), 'accept_synthetic_storage': True,
            'scope': {'region': 'unknown', 'variant': 'unknown', 'date': ''},
        }).json()
        path = f"/api/interviews/{session['id']}"
        before = client.get(path + '/events').json()
        assert client.post(path + '/timings', json=completed()).status_code == 403
        assert client.post(path + '/timings', json=completed(), headers=headers).status_code == 200
        assert client.get(path).json() == session
        assert client.get(path + '/events').json() == before
        exported = client.get(path + '/timings')
        assert exported.json()['attempts'] == 1
        assert 'attachment' in exported.headers['content-disposition']
        assert client.post('/api/interviews/missing/timings', headers=headers, json=record()).status_code == 404
