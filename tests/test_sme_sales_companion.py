import json

import httpx
import pytest

from services.sme_interviewer.sales_companion import SalesCompanion


@pytest.fixture
def anyio_backend():
    return "asyncio"


class FakeSales(SalesCompanion):
    def __init__(self, rows):
        super().__init__([], 'fake')
        self.rows = rows

    async def catalog(self):
        return self.rows


def record():
    return {'id': 'one', 'title': 'Capability', 'status': 'experimental', 'text': 'A reviewed capability.',
            'source_id': 'source', 'sha256': 'hash', 'references': [], 'audience': 'internal_rehearsal', 'eligible': True}


def client(action='answer', ids=None, callback=None, term=''):
    def handler(request):
        if callback:
            callback()
        value = {'action': 'explain_' + term if action == 'explain' else action, 'ids': ids or []}
        return httpx.Response(200, json={'message': {'content': json.dumps(value)}})
    return httpx.AsyncClient(base_url='http://localhost', transport=httpx.MockTransport(handler))


@pytest.mark.anyio
async def test_only_exact_approved_wording_is_spoken():
    companion = FakeSales([record()])
    async with client(ids=['one']) as c:
        result = await companion.respond('What can it do?', c)
    assert 'A reviewed capability.' in result['reply']
    assert result['reply'].endswith('Was that on point for your question?')
    assert result['evidence'][0]['status'] == 'experimental'


@pytest.mark.anyio
async def test_unknown_id_and_concurrent_revocation_cannot_speak():
    rows = [record()]
    companion = FakeSales(rows)
    async with client(ids=['invented']) as c:
        with pytest.raises(ValueError):
            await companion.respond('Invent a capability', c)
    async with client(ids=['one'], callback=lambda: rows[0].update(eligible=False)) as c:
        result = await companion.respond('What can it do?', c)
    assert result['evidence'] == [] and 'changed' in result['reply']


@pytest.mark.anyio
async def test_no_approved_evidence_requires_review():
    companion = FakeSales([])
    async with client('unknown') as c:
        result = await companion.respond('What is the price?', c)
    assert not result['evidence'] and 'review' in result['reply']


@pytest.mark.anyio
async def test_unknown_questions_do_not_get_model_generated_facts():
    companion = FakeSales([record()])
    async with client('unknown') as c:
        result = await companion.respond('Guarantee savings', c)
    assert not result['evidence'] and "don't have reviewed evidence" in result['reply']


@pytest.mark.anyio
async def test_social_intents_do_not_require_approved_product_facts():
    companion = FakeSales([])
    assert 'Hello' in (await companion.respond('Hello Tibi!'))['reply']
    assert 'welcome' in (await companion.respond('Thank you.'))['reply']
    assert (await companion.respond('Goodbye.'))['phase'] == 'closed'
    async with client('unknown') as c:
        result = await companion.respond('Hello, what does OpsAtlas cost?', c)
    assert not result['evidence'] and 'No product records are approved' in result['reply']


@pytest.mark.anyio
async def test_ontology_repair_changes_explanation_and_then_asks_for_specific_gap():
    companion = FakeSales([])
    replies = []
    for text in ('What is ontology?', "Sorry, that didn't explain it", 'Still not clear'):
        async with client('explain', term='ontology') as c:
            result = await companion.respond(text, c)
        assert not result['evidence'] and result['grounding'] == 'general_explanation'
        replies.append(result['reply'])
        companion.commit(text, result['reply'])
    assert len(set(replies)) == 3
    assert 'labelled map' in replies[1] and 'Which part' in replies[2]


@pytest.mark.anyio
async def test_same_product_excerpt_is_not_repeated_as_a_clarification():
    companion = FakeSales([record()])
    async with client(ids=['one']) as c:
        first = await companion.respond('What can it do?', c)
        companion.commit('What can it do?', first['reply'])
        second = await companion.respond('That did not answer my question', c)
    assert 'A reviewed capability.' not in second['reply']
    assert 'Sorry' in second['reply']


@pytest.mark.anyio
async def test_welcome_name_wellbeing_and_answer_confirmation():
    companion = FakeSales([])
    assert 'ask your name' in companion.opening
    assert 'What should I call you?' in (await companion.respond('Yes'))['reply']
    assert 'straight to your question' in (await companion.respond('Skip'))['reply']
    for question, expected in [('Chris', 'Good to meet you, Chris'), ('I am good, thanks', 'short introduction')]:
        result = await companion.respond(question)
        assert expected in result['reply']
        companion.commit(question, result['reply'])
    companion.commit('What is ontology?', 'Does that make the idea clearer?')
    assert 'Good.' in (await companion.respond('Yes'))['reply']


@pytest.mark.anyio
async def test_explanation_cannot_smuggle_product_evidence():
    companion = FakeSales([record()])
    async with client('explain', ids=['one'], term='ontology') as c:
        result = await companion.respond('Explain ontology', c)
        assert not result['evidence'] and result['grounding'] == 'general_explanation'


@pytest.mark.anyio
async def test_contextual_explanation_repair_and_mixed_product_question():
    companion = FakeSales([record()])
    first = await companion.respond("What is ontology assisted investigation?")
    companion.commit('What is ontology assisted investigation?', first['reply'])
    second = await companion.respond('Can you explain that more simply?')
    assert second['grounding'] == 'general_explanation' and 'Let me use an example' in second['reply']
    async with client('unknown') as c:
        mixed = await companion.respond('Can OpsAtlas guarantee ontology accuracy?', c)
    assert mixed['grounding'] != 'general_explanation'
