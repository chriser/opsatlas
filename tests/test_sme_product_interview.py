import json

import httpx
import pytest

from assistant.sources.register import SourceRegister
from services.opsatlas_sales.knowledge import Knowledge
from services.opsatlas_sales.workspace import workspace
from services.sme_interviewer.product_interviewer import ProductInterviewer


@pytest.fixture
def anyio_backend():
    return 'asyncio'


def proposal(**updates):
    return {**dict(session_id='session1', turn_id='turn1', contributor='Chris', topic='deployment',
                   question='What exists today?', raw_text='It runs locally today.', text='It runs locally today.',
                   status='available', issue='none', expected_hash=None, wording_confirmed=True), **updates}


def knowledge(tmp_path):
    k = Knowledge(SourceRegister(workspace(tmp_path / 'sales') / 'core'))
    k.seed()
    return k


def resolve(k, row, decision='distinct_scope'):
    overlaps = {r['id']: r['sha256'] for r in k.overlaps(row, k.records())}
    return k.adjudicate(row['id'], row['sha256'], decision, overlaps, 'This describes the local rehearsal deployment only.')


def test_proposal_correction_retries_and_stale_approval(tmp_path):
    k = knowledge(tmp_path)
    draft = k.propose(proposal())
    assert not draft['eligible'] and draft['provenance']['contributor'] == 'Chris'
    count = len(k.register.list())
    assert k.propose(proposal())['source_id'] == draft['source_id']
    assert len(k.register.list()) == count
    with pytest.raises(ValueError, match='related'):
        k.decide(draft['id'], draft['sha256'], True)
    resolve(k, draft)
    assert k.decide(draft['id'], draft['sha256'], True)['eligible']
    changed = k.propose(proposal(text='It will run locally.', status='planned', expected_hash=draft['sha256']))
    assert not changed['eligible'] and changed['text'].startswith('Planned')
    assert k.register.get(draft['source_id']).approval_status == 'rejected'
    assert k.register.read_content(draft['references'][0]['source_id'])
    with pytest.raises(ValueError):
        k.decide(changed['id'], draft['sha256'], True)
    with pytest.raises(ValueError, match='changed'):
        k.propose(proposal(text='Stale edit.', expected_hash=draft['sha256']))
    reloaded = Knowledge(k.register)
    assert reloaded.catalog()[-1]['sha256'] == changed['sha256']
    assert not reloaded.catalog()[-1]['eligible']


def test_same_claim_changed_provenance_changes_review_hash(tmp_path):
    k = knowledge(tmp_path)
    first = k.propose(proposal())
    second = k.propose(proposal(raw_text='It runs locally today. Different scope.', expected_hash=first['sha256']))
    assert first['sha256'] != second['sha256']


def test_dan_disagreement_preserved_and_blocks_both(tmp_path):
    k = knowledge(tmp_path)
    chris = k.propose(proposal())
    resolve(k, chris)
    k.decide(chris['id'], chris['sha256'], True)
    dan = k.propose(proposal(session_id='session2', contributor='Dan', raw_text='It only runs in the cloud.',
                             text='It only runs in the cloud.', issue='possible_conflict'))
    assert dan['provenance']['contributor'] == 'Dan'
    resolve(k, dan, 'dispute')
    assert not any(r['eligible'] for r in k.catalog() if r['id'] in (chris['id'], dan['id'], 'deployment'))
    for row in (chris, dan, next(r for r in k.catalog() if r['id'] == 'deployment')):
        with pytest.raises(ValueError, match='dispute'):
            k.decide(row['id'], row['sha256'], True)
    assert k.register.read_content(chris['source_id'])
    # Explicit resolution remains possible; it does not auto-approve the new account.
    resolve(k, dan, 'distinct_scope')
    assert k.decide(dan['id'], dan['sha256'], True)['eligible']


def test_uncertainty_and_changed_overlap_fail_closed(tmp_path):
    k = knowledge(tmp_path)
    row = k.propose(proposal(status='uncertain'))
    resolve(k, row)
    with pytest.raises(ValueError, match='uncertainty'):
        k.decide(row['id'], row['sha256'], True)
    with pytest.raises(ValueError, match='changed'):
        k.adjudicate(row['id'], row['sha256'], 'distinct_scope', {}, 'There are related records now.')


def test_supersession_and_invalid_correction_do_not_destroy_sources(tmp_path):
    k = knowledge(tmp_path)
    row = k.propose(proposal())
    resolve(k, row, 'supersede')
    assert k.decide(row['id'], row['sha256'], True)['eligible']
    with pytest.raises(ValueError):
        k.propose(proposal(text='x' * 590, expected_hash=row['sha256']))
    assert k.catalog()[-1]['eligible']
    assert next(r for r in k.catalog() if r['id'] == 'deployment')['approval'] == 'rejected'


class Interview(ProductInterviewer):
    async def catalog(self):
        return []


def interviewer():
    return Interview({'evidence': {'product_interview': {'contributor': 'Chris', 'topic': 'deployment'}}}, 'fake', 'http://core')


def model(value):
    return httpx.AsyncClient(base_url='http://local', transport=httpx.MockTransport(
        lambda r: httpx.Response(200, json={'message': {'content': json.dumps(value)}})))


@pytest.mark.anyio
async def test_local_planner_quotes_only_actual_wording_and_does_not_commit():
    agent = interviewer()
    value = dict(reply='Which installation did you test?', quote='It runs locally.', status='available', issue='none', style='warm')
    async with model(value) as c:
        result = await agent.respond('It runs locally.', c)
    assert result['product_turn']['quote'] == 'It runs locally.'
    assert not agent.history
    async with model({**value, 'quote': 'Invented capability'}) as c:
        invalid = await agent.respond('It runs locally.', c)
    assert invalid['product_turn']['quote'] == '' and invalid['product_turn']['raw_text'] == 'It runs locally.'
    async with model({**value, 'issue': 'off_topic'}) as c:
        unrelated = await agent.respond('It runs locally.', c)
    assert unrelated['product_turn']['quote'] == ''


@pytest.mark.anyio
async def test_recap_uses_committed_wording_without_inference():
    agent = interviewer()
    agent.accept_turn({'quote': 'Customer deployment is planned.', 'raw_text': 'Customer deployment is planned.', 'issue': 'none'})
    result = await agent.respond('Could you recap my account?')
    assert 'Customer deployment is planned.' in result['reply']
    assert 'product_turn' not in result
    assert 'approved' not in result['reply']


def test_product_session_settings_and_provenance_are_server_bound(tmp_path, monkeypatch):
    import os
    import uuid

    from fastapi.testclient import TestClient

    from services.sme_interviewer.conversation_store import ConversationStore
    from services.sme_interviewer.sales_preview import sales_app
    monkeypatch.setattr(os, 'environ', os.environ.copy())
    app = sales_app(tmp_path / 'sales', 'http://core')
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kw: original(
        **kw, transport=httpx.MockTransport(lambda r: httpx.Response(200, json=json.loads(r.content)))))
    with TestClient(app, base_url='http://127.0.0.1') as client:
        token = client.get('/api/bootstrap').json()['token']
        headers = {'x-sme-token': token}
        body = {'request_id': str(uuid.uuid4()), 'accept_local_storage': True,
                'scope': {'region': 'unknown', 'variant': 'unknown', 'date': ''},
                'product_interview': {'contributor': 'Chris', 'topic': 'deployment'}}
        result = client.post('/api/interviews', json=body, headers=headers)
        assert result.status_code == 200
        session = result.json()
        assert session['evidence_current'] and 'Chris' in session['title']
        result = client.post('/api/interviews', json={**body, 'product_interview': {'contributor': 'Dan', 'topic': 'deployment'}},
                             headers=headers)
        assert result.status_code == 409
        store = ConversationStore(app.state.interviews.store)

        def add(saved):
            saved['product_turns'] = [dict(id='turn1', contributor='Chris', topic='deployment', question='What exists?',
                                          raw_text='Actual captured wording.', issue='none')]
            return {}
        store.update(session['id'], session['revision'], 'test_turn', add)
        data = dict(session_id=session['id'], turn_id='turn1', text='Corrected wording.', status='planned',
                    expected_hash=None, wording_confirmed=True, contributor='Dan', raw_text='Forged original.')
        assert client.post('/api/sales/proposals', json=data).status_code == 403
        response = client.post('/api/sales/proposals', json=data, headers=headers)
        assert response.status_code == 200
        assert response.json()['contributor'] == 'Chris'
        assert response.json()['raw_text'] == 'Actual captured wording.'


def test_native_approval_cannot_bypass_interview_scope_or_uncertainty(tmp_path):
    k = knowledge(tmp_path)
    row = k.propose(proposal())
    k.register.update(row['source_id'], approval_status='approved')
    assert not k.catalog()[-1]['eligible']
    resolve(k, row)
    assert k.catalog()[-1]['eligible']
    uncertain = k.propose(proposal(session_id='other', status='uncertain'))
    k.register.update(uncertain['source_id'], approval_status='approved')
    assert not k.catalog()[-1]['eligible']
