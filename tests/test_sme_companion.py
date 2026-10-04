"""Semantic boundary, history isolation and malformed model output handling."""
import asyncio
import json

import httpx
import pytest

from services.sme_interviewer.companion import MODEL, Companion


def test_schema_history_and_commit_are_explicit():
    async def run():
        seen = []
        def handler(request):
            seen.append(json.loads(request.content))
            return httpx.Response(200, json={'message': {'content': json.dumps(
                {'reply': 'That sounds tiring. We can keep this short.', 'style': 'gentle', 'phase': 'social'})}})
        c = Companion()
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url='http://local') as client:
            reply = await c.respond('It has been an exhausting day.', client)
            assert c.history == []  # cancelled/stale responses cannot become memory
            c.commit('It has been an exhausting day.', reply['reply'])
            await c.respond('Thank you.', client)
        assert seen[0]['model'] == MODEL and seen[0]['think'] is False
        assert seen[1]['messages'][-3]['content'] == 'It has been an exhausting day.'
        for i in range(20):
            c.commit(str(i), 'A reply')
        assert len(c.history) == 12
    asyncio.run(run())


@pytest.mark.parametrize('value', [
    {'reply': '[laugh] Hello', 'style': 'amused', 'phase': 'social'},
    {'reply': 'x'*281, 'style': 'warm', 'phase': 'social'},
    {'reply': 'Hello', 'style': 'angry', 'phase': 'social'},
    {'reply': 'Approved.', 'style': 'neutral', 'phase': 'publish'},
])
def test_invalid_outputs_are_not_spoken(value):
    async def run():
        def handler(request):
            return httpx.Response(200, json={'message': {'content': json.dumps(value)}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url='http://local') as client:
            with pytest.raises(ValueError):
                await Companion().respond('Hello', client)
    asyncio.run(run())
