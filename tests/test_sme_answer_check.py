"""Model failures remain visible and assessment never validates facts."""
import asyncio
import json

import httpx
import pytest

from services.sme_interviewer.answer_check import AnswerCheck


@pytest.mark.parametrize('category', ['responsive', 'unknown', 'off_topic', 'unclear', 'inconsistent'])
def test_classification_and_cache(monkeypatch, category):
    calls = []
    class Client:
        def __init__(self, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def post(self, path, json):
            calls.append(json)
            return httpx.Response(200, request=httpx.Request('POST', 'http://localhost'),
                                  json={'message': {'content': '{"category":"' + category + '"}'}})
    monkeypatch.setattr('services.sme_interviewer.answer_check.httpx.AsyncClient', Client)
    async def run():
        checker = AnswerCheck()
        result = await checker.check('Question?', 'Answer', 'Earlier account')
        assert result['clarify'] == (category not in {'responsive', 'unknown'})
        assert result['factual_validation'] == 'not_performed'
        assert await checker.check('Question?', 'Answer', 'Earlier account') == result
        assert len(calls) == 1
        assert json.loads(calls[0]['messages'][1]['content'])['earlier_account'] == 'Earlier account'
        assert (await checker.check('Q', 'A', '', {'warning': 'Sparse recognition'}))['category'] == 'recording_issue'
        assert len(calls) == 1
    asyncio.run(run())


def test_failure_is_advisory_and_not_cached(monkeypatch):
    calls = []
    class Client:
        def __init__(self, **kwargs):
            calls.append(1)
            raise httpx.ConnectError('offline')
    monkeypatch.setattr('services.sme_interviewer.answer_check.httpx.AsyncClient', Client)
    async def run():
        checker = AnswerCheck()
        for _ in range(2):
            result = await checker.check('Q', 'A', '')
            assert result['category'] == 'unavailable' and result['clarify']
        assert len(calls) == 2
    asyncio.run(run())
