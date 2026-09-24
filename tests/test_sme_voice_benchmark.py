import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.sme_interviewer.experience.benchmark_web import attach_benchmark


def setup(tmp_path):
    (tmp_path / 'turbo.json').write_text(json.dumps([{'candidate': 'turbo', 'case': 'greeting', 'file': 'turbo-greeting.wav',
        'first_output_ms': 100, 'total_ms': 200, 'audio_seconds': 1, 'rtf': .2, 'clipped_samples': 0, 'sha256': 'abc'}]))
    (tmp_path / 'turbo-greeting.wav').write_bytes(b'RIFF-test')
    app = FastAPI()
    attach_benchmark(app, tmp_path)
    return TestClient(app)


def test_feedback_keeps_provenance_and_cannot_approve_training(tmp_path):
    client = setup(tmp_path)
    catalog = client.get('/api/voice-benchmark').json()
    voice = next(v for v in catalog['voices'] if v['clips'])
    assert voice['name'] == 'Voice ' + voice['alias']
    body = {'alias': voice['alias'], 'case': 'greeting', 'naturalness': 4, 'pace': 3,
            'pronunciation': 5, 'accent': 4, 'notes': 'Too formal', 'preferred_wording': 'Hi, Chris.', 'eligible_for_training': True}
    response = client.post('/api/voice-benchmark/feedback', headers={'x-benchmark-token': catalog['token']}, json=body)
    assert response.status_code == 200 and not response.json()['eligible_for_training']
    saved = client.get('/api/voice-benchmark/export').json()['feedback'][0]
    assert saved['clip_sha256'] == 'abc' and saved['review_status'] == 'unreviewed'
    assert not saved['eligible_for_training']
    assert client.get('/api/voice-benchmark/audio/'+voice['alias']+'/greeting').status_code == 200


def test_feedback_requires_token_origin_valid_score_and_available_clip(tmp_path):
    client = setup(tmp_path)
    catalog = client.get('/api/voice-benchmark').json()
    assert client.post('/api/voice-benchmark/feedback', json={}).status_code == 403
    headers = {'x-benchmark-token': catalog['token'], 'origin': 'https://elsewhere.invalid'}
    assert client.post('/api/voice-benchmark/feedback', headers=headers, json={}).status_code == 403
    headers.pop('origin')
    assert client.post('/api/voice-benchmark/feedback', headers=headers, json={}).status_code == 422
    assert not (tmp_path/'feedback.jsonl').exists()
    assert client.get('/api/voice-benchmark/audio/Z/greeting').status_code == 404
