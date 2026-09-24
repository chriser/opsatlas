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


def client(action='answer', ids=None, callback=None):
    def handler(request):
        if callback:
            callback()
        return httpx.Response(200, json={'message': {'content': json.dumps({'action': action, 'ids': ids or []})}})
    return httpx.AsyncClient(base_url='http://localhost', transport=httpx.MockTransport(handler))


@pytest.mark.anyio
async def test_only_exact_approved_wording_is_spoken():
    companion = FakeSales([record()])
    async with client(ids=['one']) as c:
        result = await companion.respond('What can it do?', c)
    assert result['reply'] == 'A reviewed capability.'
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
    result = await companion.respond('What is the price?')
    assert not result['evidence'] and 'review' in result['reply']


@pytest.mark.anyio
async def test_unknown_questions_do_not_get_model_generated_facts():
    companion = FakeSales([record()])
    async with client('unknown') as c:
        result = await companion.respond('Guarantee savings', c)
    assert not result['evidence'] and "don't have reviewed evidence" in result['reply']
