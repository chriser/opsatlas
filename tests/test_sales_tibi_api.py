"""Tibi inside OpsAtlas: the control panel's Tibi API behind the operator sign-in, and the embedded voice page."""
import json
import os
import sqlite3

import pytest


@pytest.fixture
def panel(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from services.opsatlas_sales.app import create_sales_app
    monkeypatch.setattr(os, 'environ', os.environ.copy())
    root = tmp_path / 'sales'
    app = create_sales_app(root)
    app.state.retrieval.embedder = None  # hermetic: lexical ranking only
    with TestClient(app) as client:
        token = client.post('/api/auth/login', json={'password': (root / 'local-access.key').read_text().strip()}).json()['token']
        yield client, {'Authorization': f'Bearer {token}'}, root


def test_every_tibi_endpoint_needs_the_operator_sign_in(panel):
    client, auth, _ = panel
    for path in ('/api/tibi/status', '/api/tibi/knowledge', '/api/tibi/spoken', '/api/tibi/contributions',
                 '/api/tibi/ontology', '/api/tibi/governance/answers', '/api/tibi/governance/agenda'):
        assert client.get(path).status_code == 401, path
        assert client.get(path, headers={'Authorization': 'Bearer wrong'}).status_code == 401, path
        assert client.get(path, headers=auth).status_code == 200, path
    # The workspace key is not an operator sign-in.
    key = client.get('/api/tibi/knowledge', headers={'x-sales-token': 'anything'})
    assert key.status_code == 401


def test_the_control_panel_reviews_records_and_governance_answers(panel):
    client, auth, _ = panel
    status = client.get('/api/tibi/status', headers=auth).json()
    assert status['available'] and status['voice_url'].endswith('/conversation?social=1&sales=1&embed=1')
    records = {r['id']: r for r in client.get('/api/tibi/knowledge', headers=auth).json()['records']}
    assert any(r.get('kind') == 'conversation' for r in records.values())
    row = records['limitations']
    enabled = client.post('/api/tibi/knowledge/limitations/review', headers=auth,
                          json={'expected_hash': row['sha256'], 'approve': True}).json()
    assert enabled['eligible']
    stale = client.post('/api/tibi/knowledge/limitations/review', headers=auth, json={'expected_hash': 'x', 'approve': True})
    assert stale.status_code == 409
    source = client.get(f"/api/tibi/sources/{row['source_id']}", headers=auth).json()
    assert source['text'].startswith('# ')
    assert any(o['id'] == 'limitation:no_sso' for o in client.get('/api/tibi/ontology', headers=auth).json()['objects'])
    agenda = client.get('/api/tibi/governance/agenda', headers=auth).json()
    assert agenda['total'] >= 1 and agenda['open'] == agenda['total']
    item = client.get('/api/sales/governance/agenda', headers={'x-sales-token': ''}).status_code
    assert item == 403  # the workspace API still needs the workspace key


def test_proposals_take_attribution_from_the_saved_interview_never_the_browser(panel):
    client, auth, root = panel
    (root / 'voice').mkdir(exist_ok=True)
    with sqlite3.connect(root / 'voice' / 'interviews.sqlite') as db:
        db.execute('CREATE TABLE sessions(id TEXT PRIMARY KEY, revision INTEGER NOT NULL, data TEXT NOT NULL)')
        db.execute('INSERT INTO sessions VALUES (?, 1, ?)', ('s1', json.dumps({'product_turns': [dict(
            id='turn1', contributor='Chris', topic='limitations', question='What is missing?',
            raw_text='Actual captured wording.', quote='', status='planned', issue='none')]})))
    turns = client.get('/api/tibi/contributions', headers=auth).json()['turns']
    assert turns[0]['session_id'] == 's1' and turns[0]['raw_text'] == 'Actual captured wording.'
    data = dict(session_id='s1', turn_id='turn1', text='Single sign-on is planned.', status='planned',
                expected_hash=None, wording_confirmed=True, contributor='Dan', raw_text='Forged original.')
    saved = client.post('/api/tibi/proposals', headers=auth, json=data).json()
    assert saved['provenance']['contributor'] == 'Chris' and saved['provenance']['raw_text'] == 'Actual captured wording.'
    missing = client.post('/api/tibi/proposals', headers=auth, json={**data, 'turn_id': 'nope'})
    assert missing.status_code == 400


def test_the_voice_service_only_serves_the_conversation_embedded_in_opsatlas(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from services.sme_interviewer.sales_preview import sales_app
    monkeypatch.setattr(os, 'environ', os.environ.copy())
    app = sales_app(tmp_path / 'sales', 'http://127.0.0.1:8780')
    with TestClient(app, base_url='http://127.0.0.1', follow_redirects=False) as client:
        for path, target in (('/', '/#tibi'), ('/knowledge', '/#tibi-knowledge'), ('/interview', '/#tibi'),
                             ('/conversation?social=1&sales=1', '/#tibi')):
            response = client.get(path)
            assert response.status_code in (302, 307) and response.headers['location'] == 'http://127.0.0.1:8780' + target, path
        page = client.get('/conversation?social=1&sales=1&embed=1&mode=governance')
        assert page.status_code == 200 and '/sales.js' in page.text
        assert page.headers['content-security-policy'] == 'frame-ancestors http://127.0.0.1:8780 http://localhost:8780'
        # Missing parameters are added, and the embedding and mode are kept.
        location = client.get('/conversation?embed=1&mode=interview').headers['location']
        assert 'embed=1' in location and 'mode=interview' in location and 'social=1' in location
        assert client.get('/sales-knowledge.js').status_code == 404
