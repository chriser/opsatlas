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
    assert status == {'available': False, 'service': None, 'gateway': '/services/tibi', 'busy': None}
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
    # Every open issue other than a conflict or duplicate between records is listed in plain words for the page.
    assert agenda['items'] and all(i['kind'] != 'statement' and i['label'] and i['text'] and i['where'] for i in agenda['items'])
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


def test_open_issues_are_described_in_plain_words():
    from services.opsatlas_sales.tibi_api import open_issue
    acronym = open_issue({'key': 'acronym:RAG', 'kind': 'acronym', 'check': 'undefined_acronym', 'severity': 'low',
                          'acronym': 'RAG', 'source_title': 'RAG and OAG evaluation results', 'sources': ['RAG and OAG evaluation results'],
                          'known': [{'expansion': 'Retrieval-Augmented Generation', 'source_title': 'DT603 Part A · Appendix A'}]})
    assert acronym['label'] == 'Acronym not spelled out' and acronym['text'] == 'RAG is used without being spelled out.'
    assert acronym['where'] == ['RAG and OAG evaluation results']
    assert acronym['hint'] == 'DT603 Part A · Appendix A spells it out as Retrieval-Augmented Generation.'
    standard = open_issue({'key': 'standard:AI+ML', 'kind': 'standard', 'check': 'undefined_acronym', 'acronyms': ['AI', 'ML'],
                           'source_title': '2 sources', 'issues': [{'source_title': 'B'}, {'source_title': 'A'}],
                           'answer': {'status': 'pending'}})
    assert standard['text'] == 'Common acronyms used without being spelled out: AI, ML.' and standard['where'] == ['A', 'B']
    assert standard['answer'] == 'pending'
    link = open_issue({'key': 'k', 'kind': 'issue', 'check': 'broken_link', 'source_title': 'Security', 'detail': 'docs/x.md',
                       'recommended_action': 'Fix the link.'})
    assert (link['label'], link['text'], link['where'], link['hint']) == ('Broken link', 'docs/x.md', ['Security'], 'Fix the link.')


def test_services_restart_from_the_control_panel(panel, monkeypatch):
    from services.opsatlas_sales import manage
    client, auth, _ = panel
    calls = []
    monkeypatch.setattr(manage, 'restart', lambda name: calls.append(('now', name)))
    monkeypatch.setattr(manage, 'restart_later', lambda name: calls.append(('later', name)))
    assert client.post('/api/services/restart', json={'which': 'tibi'}).status_code == 401
    # Tibi alone: the operator stays signed in.
    assert client.post('/api/services/restart', headers=auth, json={'which': 'tibi'}).json() == {
        'restarting': ['tibi'], 'sign_in_again': False}
    assert calls == [('now', 'voice')]
    # Everything: Tibi now, then the core from a process of its own, so this request is still answered.
    calls.clear()
    assert client.post('/api/services/restart', headers=auth, json={'which': 'all'}).json()['sign_in_again'] is True
    assert calls == [('now', 'voice'), ('later', 'core')]
    assert client.post('/api/services/restart', headers=auth, json={'which': 'ollama'}).status_code == 400

    def not_managed(name):
        raise RuntimeError('The voice service is not running under launchd')
    monkeypatch.setattr(manage, 'restart', not_managed)
    refused = client.post('/api/services/restart', headers=auth, json={'which': 'tibi'})
    assert refused.status_code == 409 and 'launchd' in refused.json()['detail']


def test_tibi_status_says_when_the_governance_review_is_using_the_model(panel):
    client, auth, _ = panel
    desk = client.app.state.governance_desk
    desk.statements.state['status'] = 'running'
    assert 'governance review' in client.get('/api/tibi/status', headers=auth).json()['busy']
    desk.statements.state['status'] = 'finished'
    assert client.get('/api/tibi/status', headers=auth).json()['busy'] is None


def test_the_activity_log_records_requests_sign_ins_and_the_page_without_secrets(panel):
    from services.opsatlas_sales.activity import describe, read
    client, auth, root = panel
    key = (root / 'local-access.key').read_text().strip()
    assert client.post('/api/auth/login', json={'password': 'wrong'}).status_code == 401
    client.get('/api/tibi/status', headers={**auth, 'x-opsatlas-view': 'tibi'})
    client.get('/api/health')
    recorded = client.post('/api/activity', headers=auth, json={'events': [
        {'kind': 'page', 'name': 'opened Governance', 'view': 'governance'},
        {'kind': 'tibi', 'name': 'microphone refused', 'detail': 'NotAllowedError', 'token': 'abc'}]})
    assert recorded.json() == {'recorded': 2}
    assert client.post('/api/activity', json={'events': []}).status_code == 401
    events = read(root)
    http = [e for e in events if e['kind'] == 'http']
    status = next(e for e in http if e['path'] == '/api/tibi/status')
    assert status['view'] == 'tibi' and status['poll'] is True and status['status'] == 200 and status['ms'] >= 0
    auth_events = [e['event'] for e in events if e['kind'] == 'auth']
    assert auth_events.count('signed in') == 1 and 'sign-in refused' in auth_events
    browser = [e for e in events if e['source'] == 'browser']
    assert [e['name'] for e in browser] == ['opened Governance', 'microphone refused'] and browser[1]['token'] == '[redacted]'
    assert all(describe(e) for e in events)
    written = ''.join(f.read_text() for f in (root / 'logs' / 'activity').glob('*.jsonl'))
    assert key not in written and auth['Authorization'].split()[1] not in written and 'wrong' not in written
    assert read(root, polls=False) and not any(e.get('poll') for e in read(root, polls=False))


def test_conversations_are_listed_opened_and_marked_for_improvement(panel):
    client, auth, root = panel
    log = root / 'logs' / 'conversations'
    log.mkdir(parents=True)
    from datetime import datetime, timezone
    day = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    turns = [{'at': f'{day}T21:11:{10 + n}+00:00', 'session': 's1', 'turn': n, 'mode': 'chat',
              'engine': {'version': '1.1.0', 'fingerprint': 'abc'}, 'heard': heard, 'reply': reply, 'route': route,
              'timings': {'first_segment': ms}} for n, (heard, reply, route, ms) in enumerate([
                  ("All right, Tibi, it's Chris here.", 'Nice to see you, Chris!', 'conversation', 260),
                  ('So, how about you?', "That's me! I'm Tibi...", 'self', 850)])]
    (log / f'{day}.jsonl').write_text('\n'.join(json.dumps(t) for t in turns) + '\n')
    assert client.get('/api/conversations').status_code == 401
    [listed] = client.get('/api/conversations', headers=auth).json()['sessions']
    assert listed['turns'] == 2 and listed['engines'] == ['1.1.0'] and listed['first'].startswith('All right')
    marked = client.put('/api/conversations/s1/turns/1/review', headers=auth,
                        json={'verdict': 'wrong', 'note': 'Answered "how about you" with a product description'})
    assert marked.status_code == 200 and marked.json()['verdict'] == 'wrong'
    assert client.put('/api/conversations/s1/turns/9/review', headers=auth, json={'verdict': 'odd'}).status_code == 404
    assert client.put('/api/conversations/s1/turns/0/review', headers=auth, json={'verdict': 'meh'}).status_code == 400
    opened = client.get('/api/conversations/s1', headers=auth).json()['turns']
    assert opened[1]['review']['verdict'] == 'wrong' and opened[0]['review'] is None
    assert [t['turn'] for t in client.get('/api/conversations/flagged', headers=auth).json()['turns']] == [1]
    assert client.get('/api/conversations', headers=auth).json()['sessions'][0]['marks'] == {'wrong': 1}
    # Clearing a mark takes the turn off the improvement list.
    client.put('/api/conversations/s1/turns/1/review', headers=auth, json={'verdict': None})
    assert client.get('/api/conversations/flagged', headers=auth).json()['turns'] == []
