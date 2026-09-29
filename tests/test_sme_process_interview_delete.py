"""Deleting a process interview, and not keeping empty ones (PI F15): the Human's decision of 29 September 2026."""
import json
import os
import uuid

from services.opsatlas_sales import conversations
from services.sme_interviewer.conversation_store import ConversationStore
from services.sme_interviewer.evidence import FixtureEvidence
from services.sme_interviewer.interview import Interviews
from services.sme_interviewer.timing import MARKS

SCOPE = {'region': 'unknown', 'variant': 'unknown', 'date': ''}


def interview(interviews, said=None, process=True):
    evidence = {**FixtureEvidence().snapshot(),
                **({'process_interview': {'space': 'beepee', 'space_name': 'BeePee'}} if process else {})}
    session = interviews.store.create(evidence, SCOPE, str(uuid.uuid4()))
    if said:
        def change(saved):
            saved['social_transcript'] = [{'role': 'assistant', 'content': 'Who are you?'}, {'role': 'user', 'content': said}]
            return {'phase': 'social', 'style': 'neutral', 'reasoning_ms': 1, 'user': said, 'assistant': 'Who are you?'}
        session = ConversationStore(interviews.store).update(session['id'], session['revision'], 'social_exchange', change)
    return session['id']


def timing(identifier):
    return {'version': 1, 'id': str(uuid.uuid4()), 'page_id': 'p', 'generation_id': '1', 'revision': 1, 'sequence': 1,
            'source': 'microphone', 'runtime': 'unknown', 'endpoint_kind': 'detected', 'status': 'open',
            'marks': {key: 0 if key == 'capture_start' else None for key in MARKS}}


def test_the_ledger_timings_and_log_forget_one_interview_and_keep_the_rest(tmp_path):
    interviews = Interviews(tmp_path)
    gone, kept = interview(interviews, "I'm Bruno."), interview(interviews, "I'm Alex.")
    interviews.store.delete(gone)
    assert [r['id'] for r in interviews.store.list(include_archived=True, limit=None)] == [kept]
    assert interviews.store.events(kept)
    try:
        interviews.store.get(gone)
        raise AssertionError('deleted')
    except KeyError:
        pass
    for identifier in (gone, kept):
        interviews.timings.save(identifier, timing(identifier))
    interviews.timings.forget(gone)
    assert interviews.timings.export(gone)['records'] == [] and len(interviews.timings.export(kept)['records']) == 1
    for identifier, heard in ((gone, "I'm Bruno."), (kept, "I'm Alex."), (gone, 'We sell tobacco.')):
        conversations.append(tmp_path, {'at': '2026-09-29T08:13:34+0100', 'session': identifier, 'turn': 0, 'heard': heard})
    assert conversations.forget(tmp_path, gone) == 2
    assert [t['heard'] for t in conversations.turns(tmp_path, days=3650)] == ["I'm Alex."]


def service(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from services.sme_interviewer.sales_preview import sales_app
    monkeypatch.setattr(os, 'environ', os.environ.copy())
    app = sales_app(tmp_path / 'sales', 'http://127.0.0.1:8780')
    return app, TestClient(app, base_url='http://127.0.0.1')


def test_empty_interviews_are_removed_at_start_and_never_listed(tmp_path, monkeypatch):
    first, _ = service(tmp_path, monkeypatch)  # the workspace as the service set it up, with interviews from before
    seeded = first.state.interviews
    empty, answered, chat = interview(seeded), interview(seeded, "I'm Bruno."), interview(seeded, process=False)
    app, client = service(tmp_path, monkeypatch)  # started again
    store = app.state.interviews.store
    assert {r['id'] for r in store.list(include_archived=True, limit=None)} == {answered, chat}
    with client:
        started = interview(app.state.interviews)  # a page has just started one: nothing said yet
        listed = client.get('/api/process-interviews', params={'space': 'beepee'}).json()['interviews']
    assert [i['id'] for i in listed] == [answered] and started not in {i['id'] for i in listed} and empty != started
    log = (tmp_path / 'sales' / 'logs' / 'activity').glob('tibi-*.jsonl')
    events = [json.loads(line) for path in log for line in path.read_text().splitlines()]
    assert any(e.get('event') == 'interview deleted' and e['session'] == empty and e['reason'] == 'empty, removed at start'
               for e in events)


def test_the_human_deletes_an_interview_but_not_an_open_one_or_another_kind(tmp_path, monkeypatch):
    app, client = service(tmp_path, monkeypatch)
    interviews = app.state.interviews
    bruno, alex, chat = interview(interviews, "I'm Bruno."), interview(interviews, "I'm Alex."), interview(interviews, 'Hi', False)
    conversations.append(tmp_path / 'sales', {'at': '2026-09-29T08:13:34+0100', 'session': bruno, 'turn': 0, 'heard': "I'm Bruno."})
    with client:
        token = client.get('/api/bootstrap').json()['token']
        assert client.delete(f'/api/process-interviews/{bruno}').status_code == 403  # a change needs the token
        headers = {'x-sme-token': token}
        assert client.delete(f'/api/process-interviews/{uuid.uuid4()}', headers=headers).status_code == 404
        assert client.delete(f'/api/process-interviews/{chat}', headers=headers).status_code == 400
        app.state.open_conversations.add(alex)
        refused = client.delete(f'/api/process-interviews/{alex}', headers=headers)
        assert refused.status_code == 409 and 'End it first' in refused.json()['detail']
        app.state.open_conversations.discard(alex)
        assert client.delete(f'/api/process-interviews/{bruno}', headers=headers).json() == {'deleted': bruno}
        listed = client.get('/api/process-interviews', params={'space': 'beepee'}).json()['interviews']
    assert [i['id'] for i in listed] == [alex]
    assert conversations.turns(tmp_path / 'sales', days=3650) == []


def test_an_interview_closed_with_nothing_said_is_not_kept(tmp_path):
    import asyncio

    from services.sme_interviewer.continuous import Conversation
    from services.sme_interviewer.process_interviewer import ProcessInterviewer
    from tests.test_sme_continuous_tibi import Engine

    async def run():
        interviews = Interviews(tmp_path)
        interviews.process_companion_factory = lambda saved: ProcessInterviewer(saved, 'token', 'http://core')
        identifier = interview(interviews)

        async def send(event):
            pass
        c = Conversation(tmp_path, interviews, interviews.store.get(identifier), send, Engine(), Engine(), Engine())
        c.companion.release = None  # no model server here
        await c.close()
        return interviews, identifier
    interviews, identifier = asyncio.run(run())
    assert interviews.store.list(include_archived=True, limit=None) == []
