"""The Digital SME's text channel (DSME S1): Tibi's own engine answering typed questions, without audio."""
import asyncio
import json

import pytest

from services.sme_interviewer import text_channel as channel_module
from services.sme_interviewer.text_channel import CHANGED, TextChannel
from services.sme_interviewer.tibi import CONVERSATION, EVIDENCE, EvidenceChanged
from tests.test_sme_tibi import hit, make, run

QUESTION = 'What is OpsAtlas used for?'
REPLIES = {EVIDENCE: ['OpsAtlas combines approved document retrieval with structured knowledge. ',
                      'It gives cited answers, process intelligence and governance workflows.'],
           CONVERSATION: ['OK', '\nVery well, thank you. ', 'How is your day going?']}
RANKING = {QUESTION: [hit('overview', 0.86), hit('process', 0.76)]}


class Log:
    def __init__(self):
        self.lines = []

    def write(self, kind, **fields):
        self.lines.append({'kind': kind, **fields})


def engine(history):
    t = make(REPLIES, RANKING, history=history)

    async def warm():
        return None

    t.warm = warm  # never reach a real model server from a test
    return t


def test_a_typed_question_gets_the_answer_the_voice_engine_gives(tmp_path):
    activity = Log()
    channel = TextChannel(engine, tmp_path, activity)

    async def scenario():
        opened = channel.open()
        first = await channel.turn(opened['id'], QUESTION)
        second = await channel.turn(opened['id'], 'Hello, how are you?')
        return opened, first, second

    opened, first, second = asyncio.run(scenario())
    assert opened['id'].startswith('sme-') and opened['channel'] == 'digital_sme' and opened['engine']
    # The same engine and the same evidence give the same words as the voice path would speak.
    segments, voice = asyncio.run(run(engine([]), QUESTION))
    assert first['reply'] == voice['reply'] and first['segments'] == [s.text for s in segments]
    assert first['route'] == 'product' and first['grounding'] == 'grounded_synthesis'
    assert first['records'][0]['id'] == 'overview' and set(first['records'][0]) == {'id', 'title', 'source_id', 'status'}
    assert first['engine']['version'] and first['total_ms'] >= 0
    assert second['route'] == 'conversation' and second['reply'].startswith('Very well')
    # The conversation continues: both turns are in Tibi's history, as in a spoken conversation.
    tibi = channel.sessions[opened['id']]['tibi']
    assert [m['content'] for m in tibi.history if m['role'] == 'user'] == [QUESTION, 'Hello, how are you?']
    # Each turn is in the conversation log as a typed Digital SME turn; the activity log never has the wording.
    lines = [json.loads(line) for path in (tmp_path / 'logs/conversations').glob('*.jsonl') for line in path.read_text().splitlines()]
    assert [(line['mode'], line['typed'], line['voice'], line['turn']) for line in lines] == [
        ('digital_sme', True, 'anam', 0), ('digital_sme', True, 'anam', 1)]
    assert lines[0]['heard'] == QUESTION and lines[0]['reply'] == first['reply'] and lines[0]['records'][0] == 'overview'
    assert {line['event'] for line in activity.lines} >= {'conversation opened', 'turn'}
    assert not any(QUESTION in json.dumps(line) or 'retrieval' in json.dumps(line) for line in activity.lines)


def test_conversations_are_separate_limited_and_forgotten(tmp_path, monkeypatch):
    monkeypatch.setattr(channel_module, 'LIMIT', 2)
    channel = TextChannel(engine, None)

    async def scenario():
        a = channel.open()['id']
        await channel.turn(a, QUESTION)
        b = channel.open()['id']
        assert not channel.sessions[b]['tibi'].history  # a new conversation starts afresh
        c = channel.open()['id']  # over the limit: the one idle longest (a) is dropped
        with pytest.raises(KeyError):
            await channel.turn(a, QUESTION)
        assert channel.close(b) and not channel.close(b)
        return c

    c = asyncio.run(scenario())
    assert list(channel.sessions) == [c]
    channel.sessions[c]['used'] -= channel_module.IDLE_SECONDS + 1
    channel._prune()
    assert not channel.sessions


def test_changed_evidence_asks_again_and_commits_nothing(tmp_path):
    def changing(history):
        t = engine(history)

        async def produce(turn):
            raise EvidenceChanged('changed')

        t._produce = produce
        return t

    channel = TextChannel(changing, tmp_path)

    async def scenario():
        opened = channel.open()
        return opened['id'], await channel.turn(opened['id'], QUESTION)

    identifier, result = asyncio.run(scenario())
    assert result['reply'] == CHANGED and result['route'] == 'evidence_changed'
    assert not channel.sessions[identifier]['tibi'].history


def test_the_service_exposes_the_channel_behind_its_token(tmp_path, monkeypatch):
    import os

    from fastapi.testclient import TestClient

    from services.sme_interviewer.sales_preview import sales_app
    monkeypatch.setattr(os, 'environ', os.environ.copy())
    app = sales_app(tmp_path / 'sales', 'http://core')
    app.state.text_channel.factory = engine
    with TestClient(app, base_url='http://127.0.0.1') as client:
        assert client.post('/api/text/sessions', json={}).status_code == 403  # the service's own token is required
        headers = {'x-sme-token': client.get('/api/bootstrap').json()['token']}
        assert 'digital_sme' in client.get('/api/health').json()['modes']
        assert client.post('/api/text/sessions', json={'channel': 'other'}, headers=headers).status_code == 400
        opened = client.post('/api/text/sessions', json={}, headers=headers).json()
        path = f"/api/text/sessions/{opened['id']}"
        assert client.post(path + '/turns', json={'text': '   '}, headers=headers).status_code == 400
        answer = client.post(path + '/turns', json={'text': QUESTION}, headers=headers).json()
        assert answer['route'] == 'product' and answer['reply'].startswith('OpsAtlas combines')
        assert client.post(path + '/close', json={}, headers=headers).json() == {'closed': True}
        gone = client.post(path + '/turns', json={'text': QUESTION}, headers=headers)
        assert gone.status_code == 404 and 'Start a new one' in gone.json()['detail']
