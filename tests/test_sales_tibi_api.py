"""OpsAtlas's side of Tibi (behind the operator sign-in) and the Tibi service's own API."""
import json
import os

import pytest


@pytest.fixture
def panel(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from services.opsatlas_sales.app import create_sales_app
    monkeypatch.setattr(os, 'environ', os.environ.copy())
    os.environ['SME_TIBI_VOICE_URL'] = 'http://127.0.0.1:9'  # no Tibi service in these tests
    root = tmp_path / 'sales'
    app = create_sales_app(root)
    app.state.retrieval.embedder = None  # hermetic: lexical ranking only
    with TestClient(app) as client:
        token = client.post('/api/auth/login', json={'password': (root / 'local-access.key').read_text().strip()}).json()['token']
        yield client, {'Authorization': f'Bearer {token}'}, root


def test_every_tibi_endpoint_needs_the_operator_sign_in(panel):
    client, auth, _ = panel
    for path in ('/api/tibi/status', '/api/tibi/knowledge', '/api/tibi/spoken',
                 '/api/tibi/ontology', '/api/tibi/governance/answers', '/api/tibi/governance/agenda',
                 '/api/tibi/governance/statements'):
        assert client.get(path).status_code == 401, path
        assert client.get(path, headers={'Authorization': 'Bearer wrong'}).status_code == 401, path
        assert client.get(path, headers=auth).status_code == 200, path
    # The workspace key is not an operator sign-in.
    key = client.get('/api/tibi/knowledge', headers={'x-sales-token': 'anything'})
    assert key.status_code == 401


def test_the_control_panel_reviews_records_and_governance_answers(panel):
    client, auth, _ = panel
    status = client.get('/api/tibi/status', headers=auth).json()
    # No Tibi service runs in this test: OpsAtlas reports it unavailable rather than failing.
    assert status == {'available': False, 'service': None, 'gateway': '/services/tibi'}
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


def tibi_service(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from services.sme_interviewer.sales_preview import sales_app
    monkeypatch.setattr(os, 'environ', os.environ.copy())
    app = sales_app(tmp_path / 'sales', 'http://127.0.0.1:8780')
    return app, TestClient(app, base_url='http://127.0.0.1', follow_redirects=False)


def test_the_tibi_service_is_an_api_with_no_pages(tmp_path, monkeypatch):
    _, client = tibi_service(tmp_path, monkeypatch)
    with client:
        health = client.get('/api/health').json()
        assert health['service'] == 'tibi' and set(health['modes']) == {'chat', 'product_interview', 'governance_interview'}
        for path, target in (('/', '/#tibi'), ('/knowledge', '/#tibi-knowledge'), ('/conversation?social=1&sales=1', '/#tibi'),
                             ('/sales.js', '/#tibi'), ('/voice-worklet.js', '/#tibi')):
            response = client.get(path)
            assert response.status_code in (302, 307) and response.headers['location'] == 'http://127.0.0.1:8780' + target, path


def test_proposals_take_attribution_from_the_saved_interview_never_the_browser(tmp_path, monkeypatch):
    import uuid

    import httpx

    from services.sme_interviewer.conversation_store import ConversationStore
    app, client = tibi_service(tmp_path, monkeypatch)
    sent = []
    original = httpx.AsyncClient

    def opsatlas(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={**json.loads(request.content), 'id': 'record'})
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kw: original(**kw, transport=httpx.MockTransport(opsatlas)))
    with client:
        token = client.get('/api/bootstrap').json()['token']
        headers = {'x-sme-token': token}
        session = client.post('/api/interviews', headers=headers, json={
            'request_id': str(uuid.uuid4()), 'accept_local_storage': True,
            'scope': {'region': 'unknown', 'variant': 'unknown', 'date': ''},
            'product_interview': {'contributor': 'Chris', 'topic': 'deployment'}}).json()

        def add(saved):
            saved['product_turns'] = [dict(id='turn1', contributor='Chris', topic='deployment', question='What exists?',
                                          raw_text='Actual captured wording.', issue='none')]
            return {}
        ConversationStore(app.state.interviews.store).update(session['id'], session['revision'], 'test_turn', add)
        turns = client.get('/api/contributions').json()['turns']
        assert turns[0]['session_id'] == session['id'] and turns[0]['raw_text'] == 'Actual captured wording.'
        data = dict(session_id=session['id'], turn_id='turn1', text='Corrected wording.', status='planned',
                    expected_hash=None, wording_confirmed=True, contributor='Dan', raw_text='Forged original.')
        assert client.post('/api/contributions/propose', json=data).status_code == 403  # the service's own token
        saved = client.post('/api/contributions/propose', json=data, headers=headers).json()
        assert saved['contributor'] == 'Chris' and saved['raw_text'] == 'Actual captured wording.'
        assert sent[-1]['contributor'] == 'Chris' and sent[-1]['raw_text'] == 'Actual captured wording.'
        assert client.post('/api/contributions/propose', json={**data, 'turn_id': 'nope'}, headers=headers).status_code == 400
