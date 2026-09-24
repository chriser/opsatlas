import json

import httpx
import pytest

from services.sme_interviewer.layered_companion import LayeredCompanion


@pytest.fixture
def anyio_backend():
    return 'asyncio'


def turn(mode='conversation', reply='What have you been growing?', **kwargs):
    return {'mode': mode, 'issue': 'none', 'earlier_quote': '', 'current_quote': '',
            'reply': reply, 'style': 'warm', 'phase': 'social', **kwargs}


def client(*replies, callback=None):
    iterator = iter(replies)

    def handler(request):
        if callback:
            callback(json.loads(request.content))
        return httpx.Response(200, json={'message': {'content': json.dumps(next(iterator))}})
    return httpx.AsyncClient(base_url='http://local', transport=httpx.MockTransport(handler))


class Local(LayeredCompanion):
    def __init__(self):
        super().__init__([], 'fake')
        self.calls = 0
        self.rows = [{'id': 'one', 'text': 'It is a prototype.', 'status': 'experimental', 'title': 'Status',
                      'eligible': True, 'sha256': 'abc', 'source_id': 'source', 'audience': 'internal', 'references': []}]

    async def catalog(self):
        self.calls += 1
        return self.rows


@pytest.mark.anyio
async def test_small_talk_and_general_knowledge_do_not_call_atlas():
    c = Local()
    async with client(turn(), turn('general', 'A database stores organised information.')) as model:
        first = await c.respond('I have been gardening today.', model)
        c.commit('I have been gardening today.', first['reply'])
        second = await c.respond('What is a database?', model)
    assert c.calls == 0 and not second['evidence']
    assert second['grounding'] == 'general_model_knowledge'
    assert c.history[0]['content'] == 'I have been gardening today.'


@pytest.mark.anyio
async def test_product_inference_has_checked_sources_and_separate_status():
    c = Local()
    async with client({'status': 'supported', 'ids': ['one'], 'reply': 'It is still a prototype.'}) as model:
        result = await c.respond('Is OpsAtlas enterprise ready?', model)
    assert c.calls == 2 and result['background_check']
    assert result['grounding'] == 'grounded_synthesis' and result['evidence'][0]['id'] == 'one'


@pytest.mark.anyio
async def test_product_source_revocation_during_inference_blocks_answer():
    c = Local()

    def revoke(payload):
        if 'approved_records' in payload['messages'][-1]['content']:
            c.rows[0]['eligible'] = False
    async with client({'status': 'supported', 'ids': ['one'], 'reply': 'It is a prototype.'},
                      callback=revoke) as model:
        result = await c.respond('What is OpsAtlas?', model)
    assert not result['evidence'] and 'changed' in result['reply']


@pytest.mark.anyio
async def test_fabricated_conversation_conflict_does_not_reach_user():
    c = Local()
    c.commit('My meeting is on Monday.', 'Understood.')
    fabricated = turn(reply='You contradicted yourself.', issue='possible_conflict',
                      earlier_quote='My meeting is on Friday.', current_quote='Tuesday')
    async with client(fabricated) as model:
        result = await c.respond('Tuesday would be better.', model)
    assert 'contradicted' not in result['reply'] and 'clarify' in result['reply']


@pytest.mark.anyio
async def test_product_claim_misrouted_as_small_talk_is_checked():
    c = Local()
    async with client(turn(reply='OpsAtlas is enterprise ready.'),
                      {'status': 'insufficient', 'ids': [], 'reply': 'The records do not establish that guarantee.'}) as model:
        result = await c.respond('Can you reassure me?', model)
    assert 'enterprise ready' not in result['reply'] and c.calls == 2


@pytest.mark.anyio
async def test_review_requires_real_quote_and_current_source(monkeypatch):
    c = Local()
    async def infer(*args, **kwargs):
        return {'status': 'possible_conflict', 'ids': ['one'], 'subject': 'none'}
    monkeypatch.setattr('services.sme_interviewer.layered_companion.infer', infer)
    with pytest.raises(ValueError, match='Unanchored'):
        await c.review('It is a prototype.', 'Yes.')


def test_older_relevant_wording_is_available_without_expanding_recent_window():
    c = Local()
    c.commit('The supplier approval threshold is fifteen thousand pounds.', 'Understood.')
    for i in range(10):
        c.commit(f'We discussed garden topic {i}.', 'Tell me more.')
    assert len(c.history) == 12 and len(c.archive) == 22
    assert any('fifteen thousand' in r['content'] for r in c.relevant_memory('What was the supplier approval threshold?'))


@pytest.mark.anyio
async def test_knowledge_update_help_is_not_a_missing_price_answer():
    c = Local()
    result = await c.respond('How do we ensure that the prices and specific deployment guarantees are in the records?')
    assert result['grounding'] == 'workspace_guidance' and not result['evidence']
    assert 'Contribute product knowledge' in result['reply'] and 'Knowledge review' in result['reply']
    assert 'does not itself establish' in result['reply']
    assert c.calls == 0


def test_overview_scope_does_not_remove_explicit_security_or_price_evidence():
    from services.sme_interviewer.layered_companion import overview_records, workspace_update_question
    rows = [{'id': key} for key in ('overview', 'retrieval', 'commercial', 'limitations')]
    assert [r['id'] for r in overview_records('What is OpsAtlas used for?', rows)] == ['overview']
    for q in ('What is OpsAtlas pricing?', 'Is it enterprise ready?',
              'Can you guarantee offline deployment?', 'Tell me about the product limitations.'):
        assert overview_records(q, rows) == rows
    assert not workspace_update_question('How do you ensure knowledge is accurate?')
    assert not workspace_update_question('What do the records say about the price?')


def test_natural_attribution_preserves_negation_and_missing_evidence():
    from services.sme_interviewer.spoken_style import natural_evidence_wording
    assert natural_evidence_wording('The records confirm OpsAtlas is a prototype.') == 'OpsAtlas is a prototype.'
    assert natural_evidence_wording('The records explicitly state that it does not have multi-user controls.') == (
        'It does not have multi-user controls.')
    assert natural_evidence_wording('The records do not establish pricing.') == "I don't yet have confirmed details on pricing."


@pytest.mark.anyio
async def test_explicit_brand_question_skips_general_model_and_scopes_evidence():
    c = Local()
    c.rows = [dict(c.rows[0], id='overview'), dict(c.rows[0], id='commercial')]
    c.commit('What is the price?', 'Pricing is not yet confirmed.')
    calls = []
    async with client({'status': 'supported', 'ids': ['overview'], 'reply': 'The records confirm it is a prototype.'},
                      callback=calls.append) as model:
        result = await c.respond('What is Ops Atlas used for?', model)
    assert len(calls) == 1 and result['grounding'] == 'grounded_synthesis'
    assert len(calls[0]['messages']) == 2
    assert [r['id'] for r in json.loads(calls[0]['messages'][-1]['content'])['approved_records']] == ['overview']
    assert result['reply'] == 'It is a prototype.'
