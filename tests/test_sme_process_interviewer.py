"""Process interviews, Tibi side (TIBI E5): the reply takes a planned goal, commands need no model, notes are durable."""
import asyncio
import json
import uuid

import httpx

from services.sme_interviewer import process_model as pm
from services.sme_interviewer.process_interviewer import NOTE_MODEL, ProcessInterviewer

SESSION = {'id': 's1', 'evidence': {'process_interview': {'space': 'bipi', 'space_name': 'BiPi'}}}


class FakeModels:
    """Stands in for the local model server: the reply model and the note-taker each answer from their own queue."""

    def __init__(self, replies=(), notes=()):
        self.replies, self.notes, self.calls = list(replies), list(notes), []

    def __call__(self, request):
        body = json.loads(request.content)
        if body['options'].get('num_predict') == 1:
            return httpx.Response(200, json={'message': {'content': ''}})
        self.calls.append(body)
        queue = self.notes if body['model'] == NOTE_MODEL else self.replies
        content = queue.pop(0) if queue else '{'
        return httpx.Response(200, json={'message': {'content': content if isinstance(content, str) else json.dumps(content)}})


def make(replies=(), notes=(), session=None):
    t = ProcessInterviewer(session or SESSION, 'token', 'http://core')
    models = FakeModels(replies, notes)
    t.transport = httpx.MockTransport(models)
    return t, models


def reply(goal, text, style='neutral'):
    return {'goal': goal, 'style': style, 'reply': text}


def turn(t, text):
    result = asyncio.run(t.respond(text))
    t.commit(text, result['reply'])
    return result


def test_the_opening_names_the_organisation_and_asks_who_they_are():
    t, _ = make()
    assert 'at BiPi' in t.opening and 'your name' in t.opening and t.resume_line is None


def test_a_reply_takes_the_goal_the_model_chose_and_the_goal_is_counted():
    t, models = make([reply('role', 'Nice to meet you, Sam. And what is your role at BiPi?')])
    result = turn(t, "I'm Sam.")
    context = json.loads(next(c for c in models.calls if c['model'] != NOTE_MODEL)['messages'][-1]['content'])
    assert [g['key'] for g in context['goals']] == ['name', 'role', 'agenda'] and context['answer'] == "I'm Sam."
    assert result['process_turn'] == {'turn': 1, 'question': t.opening, 'goal': 'role', 'notes': True}
    assert t.model['asked'] == {'role': 1} and t.last_question.endswith('your role at BiPi?') and t.model['turns'] == 1


def test_an_unusable_reply_or_no_model_server_falls_back_to_a_plain_question():
    t, _ = make([reply('name', 'What is your name? And your role?')])
    assert turn(t, 'Hello there.')['reply'] == 'Could I start with your name?'
    t, _ = make()
    t.transport = httpx.MockTransport(lambda request: (_ for _ in ()).throw(httpx.ConnectError('down')))
    assert turn(t, 'Hello there.')['reply'] == 'Could I start with your name?'


def test_a_conflict_or_a_read_back_is_never_skipped_for_follow():
    model = pm.new_model('bipi', 'BiPi')
    model, _ = pm.apply(model, [{'op': 'step', 'ref': 'n1', 'process': '', 'after': 'start', 'kind': 'task', 'label': 'Approve order',
                                 'who': 'finance', 'system': '', 'quote': 'finance approves it'}], 'Finance approves it.', 1)
    model, _ = pm.apply(model, [{'op': 'conflict', 'item': 's1', 'field': 'who', 'now': 'regional director',
                                 'quote': 'the regional director approves'}], 'The regional director approves.', 2)
    t, _ = make([reply('follow', 'Go on.')], session={**SESSION, 'process_model': model})
    result = turn(t, 'And then it goes out to the supplier.')
    assert result['process_turn']['goal'] == 'conflict:o1'
    assert 'I noted who as "finance", and just now I heard "regional director"' in result['reply']
    assert t.model['open'][0]['status'] == 'raised'


def test_recap_stop_and_a_moment_to_think_need_no_model():
    t, models = make()
    assert turn(t, 'Can you recap?')['reply'].startswith("We haven't captured any steps yet")
    assert turn(t, 'Give me a moment.')['reply'] == 'Of course, take your time.'
    stopped = turn(t, "Let's stop here for today.")
    assert stopped['phase'] == 'closed' and 'Everything so far is saved' in stopped['reply']
    assert models.calls == [] and not any(r['process_turn']['notes'] for r in (stopped,))


def test_the_same_question_is_never_asked_twice_in_a_row():
    t, _ = make([reply('name', 'Could I start with your name?'), reply('name', 'Could I start with your name?')])
    turn(t, 'Hello.')
    second = turn(t, 'Sorry, hello again.')
    assert second['reply'] != 'Could I start with your name?' and second['process_turn']['goal'] == 'role'


def test_notes_apply_quoted_changes_and_clear_the_pending_answer():
    notes = {'changes': [{'op': 'participant', 'field': 'name', 'value': 'Sam Patel', 'quote': "I'm Sam Patel"},
                         {'op': 'participant', 'field': 'role', 'value': 'runs operations', 'quote': 'I run operations'},
                         {'op': 'participant', 'field': 'team', 'value': 'head office', 'quote': 'at head office'}]}
    t, models = make(notes=[notes])
    entry = t.note("I'm Sam Patel, I run operations.", t.opening, 1)
    assert t.pending == [entry]
    log = asyncio.run(t.take_notes(entry))
    assert {k: v['value'] for k, v in t.model['participant'].items()} == {'name': 'Sam Patel', 'role': 'runs operations'}
    assert log['changes'] == 3 and log['dropped'][0]['why'] == 'the quote is not in the answer' and t.pending == []
    sent = models.calls[0]
    assert sent['model'] == NOTE_MODEL and sent['options']['temperature'] == 0
    assert "ANSWER: I'm Sam Patel" in sent['messages'][1]['content']


def test_resuming_restores_the_model_the_place_and_the_answers_not_yet_noted():
    model = pm.new_model('bipi', 'BiPi')
    model, _ = pm.apply(model, [{'op': 'participant', 'field': 'name', 'value': 'Sam Patel', 'quote': "I'm Sam Patel"},
                                {'op': 'process', 'ref': 'n1', 'name': 'Customer returns', 'quote': 'customer returns'},
                                {'op': 'step', 'ref': 'n2', 'process': 'n1', 'after': 'start', 'kind': 'task',
                                 'label': 'Log the return', 'who': 'customer service', 'system': 'Zendesk',
                                 'quote': 'customer service logs it in Zendesk'}],
                        "I'm Sam Patel. Customer returns: customer service logs it in Zendesk.", 3)
    session = {**SESSION, 'process_model': model,
               'process_pending': [{'turn': 4, 'answer': 'Then it is checked.', 'question': 'Then?'}],
               'social_dialogue': [{'role': 'assistant', 'content': 'What happens next?'},
                                   {'role': 'user', 'content': 'Then it is checked.'}]}
    t, _ = make(session=session)
    assert t.resume_line == ('Welcome back, Sam. We were on Customer returns, just after "Log the return". '
                             'Shall we carry on from there?')
    assert t.turn == 4 and [p['turn'] for p in t.pending] == [4] and t.last_question == 'What happens next?'


def test_a_process_interview_in_the_conversation_loop_saves_the_model_and_notes_every_answer(tmp_path):
    from services.sme_interviewer.continuous import Conversation
    from services.sme_interviewer.evidence import FixtureEvidence
    from services.sme_interviewer.interview import Interviews
    from tests.test_sme_continuous_tibi import Engine

    notes = [{'changes': [{'op': 'participant', 'field': 'name', 'value': 'Sam', 'quote': "I'm Sam"}]},
             {'changes': [{'op': 'process', 'ref': 'n1', 'name': 'Ordering parts', 'quote': 'ordering parts'}]}]

    async def run():
        interviews = Interviews(tmp_path)
        evidence = {**FixtureEvidence().snapshot(), 'process_interview': {'space': 'bipi', 'space_name': 'BiPi'}}
        session = interviews.store.create(evidence, {'region': 'unknown', 'variant': 'unknown', 'date': ''}, str(uuid.uuid4()))
        models = FakeModels([reply('role', 'And your role?'), reply('agenda', 'Which processes shall we cover?')], notes)

        def factory(saved):
            t = ProcessInterviewer(saved, 'token', 'http://core')
            t.transport = httpx.MockTransport(models)
            return t
        interviews.process_companion_factory = factory

        async def send(event):
            if event['type'] == 'audio_chunk':
                c.audio_ack({'generation_id': event['generation_id'], 'index': event['index']})
        speaker = Engine()
        c = Conversation(tmp_path, interviews, session, send, Engine(), Engine(), speaker)
        c.paused = False
        for text in ("I'm Sam.", 'Mainly ordering parts.'):
            await c.social_chat(text, c.generation)
            while c.pending_checks:
                await asyncio.sleep(0.01)
        await c.close()
        return interviews.store.get(session['id']), speaker
    saved, speaker = asyncio.run(run())
    assert saved['process_model']['participant']['name']['value'] == 'Sam'
    assert [p['name'] for p in saved['process_model']['processes']] == ['Ordering parts']
    assert saved['process_pending'] == [] and [e['turn'] for e in saved['process_log']] == [1, 2]
    assert speaker.spoken == ['And your role?', 'Which processes shall we cover?']
