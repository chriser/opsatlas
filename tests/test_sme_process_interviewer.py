"""Process interviews, Tibi side (TIBI E5): the reply takes a planned goal, commands need no model, notes are durable."""
import asyncio
import json
import uuid

import httpx
import pytest

from services.sme_interviewer import process_model as pm
from services.sme_interviewer.process_interviewer import NOTE_MODEL, ProcessInterviewer

SESSION = {'id': 's1', 'evidence': {'process_interview': {'space': 'beepee', 'space_name': 'BeePee'}}}


class FakeModels:
    """Stands in for the local model server: the reply model and the note-taker each answer from their own queue."""

    def __init__(self, replies=(), notes=()):
        self.replies, self.notes, self.calls = list(replies), list(notes), []

    def __call__(self, request):
        body = json.loads(request.content)
        if body.get('options', {}).get('num_predict') == 1:
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
    assert 'at BeePee' in t.opening and 'your name' in t.opening and t.resume_line is None


def test_a_reply_takes_the_goal_the_model_chose_and_the_goal_is_counted():
    t, models = make([reply('role', 'Nice to meet you, Sam. And what is your role at BeePee?')])
    result = turn(t, "I'm Sam.")
    context = json.loads(next(c for c in models.calls if c['model'] != NOTE_MODEL)['messages'][-1]['content'])
    assert [g['key'] for g in context['goals']] == ['name', 'role', 'agenda'] and context['answer'] == "I'm Sam."
    assert result['process_turn'] == {'turn': 1, 'question': t.opening, 'goal': 'role', 'notes': True}
    assert t.model['asked'] == {'role': 1} and t.last_question.endswith('your role at BeePee?') and t.model['turns'] == 1


def test_an_unusable_reply_or_no_model_server_falls_back_to_a_plain_question():
    t, _ = make([reply('name', 'What is your name? And your role?')])
    assert turn(t, 'Hello there.')['reply'] == 'Could I start with your name?'
    t, _ = make()
    t.transport = httpx.MockTransport(lambda request: (_ for _ in ()).throw(httpx.ConnectError('down')))
    assert turn(t, 'Hello there.')['reply'] == 'Could I start with your name?'


def test_a_conflict_or_a_read_back_is_never_skipped_for_follow():
    model = pm.new_model('beepee', 'BeePee')
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
    model = pm.new_model('beepee', 'BeePee')
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
        evidence = {**FixtureEvidence().snapshot(), 'process_interview': {'space': 'beepee', 'space_name': 'BeePee'}}
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


def test_closing_unloads_the_note_takers_model_and_notes_keep_it_only_briefly():
    t, models = make(notes=[{'changes': []}])
    asyncio.run(t.take_notes(t.note('Hello.', t.opening, 1)))
    asyncio.run(t.release())
    note, unload = models.calls[0], models.calls[-1]
    assert note['keep_alive'] == '5m' and unload == {'model': NOTE_MODEL, 'keep_alive': 0, 'messages': []}


def test_a_sentence_that_sounds_finished_does_not_end_a_process_answer():
    from services.sme_interviewer.endpointing import CONFIDENT, PROCESS_PATIENCE, TurnBoundary
    chat, interview = TurnBoundary(), TurnBoundary(patience=PROCESS_PATIENCE)
    for boundary in (chat, interview):
        boundary.voiced(0)
        boundary.result(CONFIDENT, 0)
    assert chat.complete(6400)  # chat: 0.4 s after a confident end
    assert not interview.complete(6400) and not interview.complete(16000)  # a thinking pause mid-description
    assert interview.complete(PROCESS_PATIENCE)


def test_an_answer_superseded_before_the_reply_is_withdrawn_and_its_notes_undone():
    notes = {'changes': [{'op': 'participant', 'field': 'name', 'value': 'Sam', 'quote': "I'm Sam"}]}
    t, models = make([reply('role', 'And your role?')], notes=[notes])
    asyncio.run(t.respond("I'm Sam"))  # noted within the budget, then they carry on speaking
    assert t.model['participant']['name']['value'] == 'Sam' and t.open_turn == 1
    t.withdraw_open()
    assert t.model['participant'] == {} and t.pending == [] and t.open_turn is None


def test_in_the_loop_a_superseded_answer_leaves_nothing_and_the_joined_answer_is_noted_once(tmp_path):
    from services.sme_interviewer.continuous import Conversation
    from services.sme_interviewer.evidence import FixtureEvidence
    from services.sme_interviewer.interview import Interviews
    from tests.test_sme_continuous_tibi import Engine

    fragment = {'changes': [{'op': 'step', 'ref': 'n1', 'process': '', 'after': 'start', 'kind': 'task', 'label': 'Ask for product',
                             'who': 'customer', 'system': 'till', 'quote': 'the customer asks'}]}
    whole = {'changes': [{'op': 'step', 'ref': 'n1', 'process': '', 'after': 'start', 'kind': 'task',
                          'label': 'Ask for product behind the till', 'who': 'customer', 'system': '',
                          'quote': 'the customer asks for a product behind the till'}]}

    async def run():
        interviews = Interviews(tmp_path)
        evidence = {**FixtureEvidence().snapshot(), 'process_interview': {'space': 'beepee', 'space_name': 'BeePee'}}
        session = interviews.store.create(evidence, {'region': 'unknown', 'variant': 'unknown', 'date': ''}, str(uuid.uuid4()))
        models = FakeModels([reply('follow', 'Go on.'), reply('who:s2', 'Who hands it over?')], [fragment, whole])
        made = []

        def factory(saved):
            t = ProcessInterviewer(saved, 'token', 'http://core')
            t.transport = httpx.MockTransport(models)
            made.append(t)
            return t
        interviews.process_companion_factory = factory

        async def send(event):
            if event['type'] == 'audio_chunk':
                c.audio_ack({'generation_id': event['generation_id'], 'index': event['index']})
        c = Conversation(tmp_path, interviews, session, send, Engine(), Engine(), Engine())
        c.paused = False
        original = made[0].respond

        async def superseded(text):
            result = await original(text)
            c.generation += 1  # they carried on speaking before the reply
            return result
        made[0].respond = superseded
        await c.social_chat('the customer asks', c.generation)
        assert made[0].model['processes'] == [] and made[0].pending == []  # nothing of the fragment stands
        made[0].respond = original
        await c.social_chat('the customer asks for a product behind the till', c.generation)
        while c.pending_checks:
            await asyncio.sleep(0.01)
        await c.close()
        return interviews.store.get(session['id'])
    saved = asyncio.run(run())
    steps = saved['process_model']['processes'][0]['steps']
    assert [s['label'] for s in steps] == ['Ask for product behind the till'] and steps[0]['system'] == ''
    assert [m['content'] for m in saved['social_transcript'] if m['role'] == 'user'] == ['the customer asks for a product behind the till']


def test_a_proposed_change_is_said_back_and_made_on_yes_left_on_no():
    from tests.test_sme_process_model import ordering
    removal = {'changes': [{'op': 'remove', 'item': 's2', 'quote': 'remove the purchase order step'}]}
    t, _ = make(notes=[removal], session={**SESSION, 'process_model': ordering()})
    asked = turn(t, 'Please remove the purchase order step completely.')
    assert asked['reply'] == 'So you would like me to remove "Raise purchase order". Shall I?'
    done = turn(t, 'Yes please.')
    assert done['reply'].startswith('Done: I\'ve removed "Raise purchase order".')
    assert [s['label'] for s in t.model['processes'][0]['steps']] == ['Check stock report', 'Approve order']
    t2, _ = make(notes=[removal], session={**SESSION, 'process_model': ordering()})
    turn(t2, 'Please remove the purchase order step completely.')
    assert turn(t2, 'No, leave it.')['reply'].startswith("All right, I've left it as it was.")
    assert len(t2.model['processes'][0]['steps']) == 3


def test_a_longer_answer_waits_longer_for_its_notes_and_the_turn_limit_allows_for_it():
    from services.sme_interviewer.process_interviewer import notes_budget
    assert notes_budget('Yes.', 5) == 2.5 and notes_budget(' '.join(['word'] * 100), 5) == 5.0
    assert notes_budget(' '.join(['word'] * 400), 5) == 7.0
    t, _ = make()
    assert t.turn_timeout(' '.join(['word'] * 100)) >= notes_budget(' '.join(['word'] * 100), 1) + 6


def test_a_map_edit_during_the_interview_applies_at_once_and_is_saved(tmp_path):
    from services.sme_interviewer.continuous import Conversation
    from services.sme_interviewer.evidence import FixtureEvidence
    from services.sme_interviewer.interview import Interviews
    from tests.test_sme_continuous_tibi import Engine
    from tests.test_sme_process_model import ordering

    async def run():
        interviews = Interviews(tmp_path)
        evidence = {**FixtureEvidence().snapshot(), 'process_interview': {'space': 'beepee', 'space_name': 'BeePee'}}
        session = interviews.store.create(evidence, {'region': 'unknown', 'variant': 'unknown', 'date': ''}, str(uuid.uuid4()))
        interviews.process_companion_factory = lambda saved: ProcessInterviewer({**saved, 'process_model': ordering()}, 't', 'http://core')
        events = []

        async def send(event):
            events.append(event)
        c = Conversation(tmp_path, interviews, session, send, Engine(), Engine(), Engine())
        assert c.companion.vocabulary().startswith('Tibi, BeePee, ')  # the organisation's own words, from the start
        await c.process_edit({'change': {'op': 'remove', 'item': 's2'}})
        await c.process_edit({'change': {'op': 'who', 'item': 's3', 'value': 'regional director'}})
        await c.close()
        return interviews.store.get(session['id']), events
    saved, events = asyncio.run(run())
    steps = saved['process_model']['processes'][0]['steps']
    assert [s['label'] for s in steps] == ['Check stock report', 'Approve order']
    assert steps[1]['who'] == 'regional director' and steps[1]['status'] == 'confirmed'
    assert [e['message'] for e in events if e['type'] == 'process_edited'] == [
        'removed "Raise purchase order"', 'who of "Approve order" set to "regional director"']


def test_a_long_answer_not_yet_noted_gets_asked_for_more_not_for_what_it_said():
    import services.sme_interviewer.process_interviewer as module
    models = FakeModels([reply('walk:p1', 'Could you walk me through it from the start?')], [{'changes': []}])

    async def slow_notes(request):  # the note-taker is still working when the reply is due
        if json.loads(request.content)['model'] == NOTE_MODEL:
            await asyncio.sleep(0.3)
        return models(request)
    budget = module.notes_budget
    module.notes_budget = lambda text, turn: 0.05
    try:
        t = ProcessInterviewer(SESSION, 'token', 'http://core')
        t.transport = httpx.MockTransport(slow_notes)
        answer = asyncio.run(t.respond(' '.join(['The assistant checks the receipt and then refunds the customer.'] * 6)))
    finally:
        module.notes_budget = budget
    assert answer['reply'] in module.HOLDING and answer['process_turn']['goal'] is None and answer['process_turn']['notes']


def test_a_question_about_the_process_they_answered_past_is_not_asked_again_straight_away():
    """PI F14: "That's the end of it" to "what starts it?" was followed by the same question in other words."""
    from services.sme_interviewer.process_interviewer import ONCE_IN_A_ROW

    model = pm.new_model('beepee', 'BeePee')
    answer = "I'm Alex, the store manager at head office. Customer returns. A customer brings an item back and the assistant refunds it."
    model, _ = pm.apply(model, [
        {'op': 'participant', 'field': 'name', 'value': 'Alex', 'quote': "I'm Alex"},
        {'op': 'participant', 'field': 'role', 'value': 'store manager', 'quote': 'the store manager'},
        {'op': 'participant', 'field': 'team', 'value': 'head office', 'quote': 'at head office'},
        {'op': 'process', 'ref': 'n1', 'name': 'Customer returns', 'quote': 'Customer returns'},
        {'op': 'step', 'ref': 'n2', 'process': 'n1', 'after': 'start', 'kind': 'task', 'label': 'Customer brings item back',
         'who': '', 'system': '', 'quote': 'A customer brings an item back'},
        {'op': 'step', 'ref': 'n3', 'process': 'n1', 'after': 'n2', 'kind': 'task', 'label': 'Refund customer',
         'who': 'assistant', 'system': '', 'quote': 'the assistant refunds it'}], answer, 1)
    [first] = pm.goals(model, limit=1)
    assert first['key'] == 'purpose:p1' and first['key'].startswith(ONCE_IN_A_ROW)
    model = pm.asked(model, first, 2)
    t, models = make([reply('trigger:p1', 'What starts a return?')], [{'changes': []}],
                     session={**SESSION, 'process_model': model})
    t.last_goal, t.last_question = 'purpose:p1', 'What is Customer returns for?'
    result = turn(t, "That's the end of it.")
    context = json.loads(next(c for c in models.calls if c['model'] != NOTE_MODEL)['messages'][-1]['content'])
    assert [g['key'] for g in context['goals']] == ['trigger:p1'] and result['process_turn']['goal'] == 'trigger:p1'


def test_an_interview_counts_as_said_only_once_the_participant_has_said_something():
    from services.sme_interviewer.process_interviewer import said_anything

    assert not said_anything({**SESSION, 'social_transcript': [{'role': 'assistant', 'content': 'Hello, who are you?'}]})
    assert said_anything({**SESSION, 'social_transcript': [{'role': 'user', 'content': "I'm Bruno."}]})
    assert said_anything({**SESSION, 'process_pending': [{'turn': 1, 'answer': "I'm Bruno.", 'question': 'Who?'}]})
    assert said_anything({**SESSION, 'process_model': {'turns': 1}})


def test_the_note_taker_may_move_a_step_before_another():
    from services.sme_interviewer.process_interviewer import NOTE_PROMPT, NOTE_SCHEMA

    moves = [o for o in NOTE_SCHEMA['properties']['changes']['items']['anyOf'] if o['properties']['op'].get('enum') == ['move']]
    assert sorted(tuple(sorted(m['required'])) for m in moves) == [('after', 'item', 'op', 'quote'), ('before', 'item', 'op', 'quote')]
    assert '"before":"s5"' in NOTE_PROMPT


def test_a_note_taker_reply_cut_off_at_its_limit_keeps_every_change_it_completed():
    """The first 1.7.0 replay lost a whole described process: the reply ran past its token limit and none of it was read."""
    from services.sme_interviewer.process_interviewer import read_changes

    whole = {'changes': [{'op': 'step', 'ref': 'n1', 'label': 'Check receipt'}, {'op': 'step', 'ref': 'n2', 'label': 'Refund'}]}
    text = json.dumps(whole, indent=2)
    assert read_changes(text) == (whole['changes'], True)
    assert read_changes(text[:text.rindex('"Refund"')]) == (whole['changes'][:1], False)
    for nothing in ('', '{', '{"changes": ['):  # nothing usable: a failure, so the answer stays pending
        with pytest.raises(ValueError):
            read_changes(nothing)


# The Human's description of 29 September, as heard (1,321 characters): a 1,200 limit refused it (PI F17).
CASHIERING = (
    "So let me explain how it works. So a customer comes in in a shop to the tail and no it comes comes to the tail where "
    "the cashier's not tail tail So the customer comes to the tail TIL and then it's asking for specific product. And here "
    "are three options. They can ask for tobacco or e-cigarette product. They can ask for age restricted non-tobacco product "
    "or they can just ask for product without any limitation or age verification. When we start with the first one, customer "
    "asking for tobacco or e-cigarette product, that triggers immediately a carry out age verification check. That age "
    "verification check needs to be completed by cashier with the customer before the product is being handed over. So what "
    "that means is, is that when the customer asks for specific pack of cigarettes, for example, a cashier will check an ID "
    "and then they will, after verifying and confirming that someone is of age, they will first of all confirm what type of "
    "tobacco is required. Then they will locate that tobacco or that product in a dedicated drawer, which is in alphabetical "
    "order. Then once they located it, they will scan this product on point of sale and then point of sale will prompt them "
    "asking if they have verified customer age and then that prompt will be closed down on point of sale. Do you have any "
    "questions about it?")


LONGER = ' '.join([CASHIERING] * 3)  # about 4,000 characters: noted in parts


def test_a_long_answer_is_split_where_sentences_end_and_every_word_is_kept():
    from services.sme_interviewer.process_interviewer import NOTE_PART, answer_parts

    assert answer_parts(CASHIERING) == [CASHIERING]  # PI F21: a description up to NOTE_PART is noted whole
    parts = answer_parts(LONGER)
    assert len(LONGER) > NOTE_PART and len(parts) >= 2 and all(len(p) <= NOTE_PART for p in parts)
    assert ' '.join(parts).split() == LONGER.split()
    assert parts[0].startswith('So let me explain') and parts[1][0].isupper()  # each part starts a sentence
    assert answer_parts('Just this.') == ['Just this.']
    run_on = 'and then ' * 200  # no sentence ends at all: split between words
    assert all(len(p) <= NOTE_PART for p in answer_parts(run_on)) and ' '.join(answer_parts(run_on)).split() == run_on.split()


def test_a_long_spoken_description_is_taken_and_noted_a_part_at_a_time():
    """PI F17: "the system is unable to continue". The joined answer was refused for its length, and every answer after it."""
    from services.sme_interviewer.process_interviewer import answer_parts

    parts = answer_parts(LONGER)
    notes = [{'changes': [{'op': 'step', 'ref': 'n1', 'process': '', 'after': 'start', 'kind': 'task', 'label': 'Customer comes to till',
                           'who': 'customer', 'system': '', 'quote': 'the customer comes to the tail'}]}]
    notes += [{'changes': []}] * (len(parts) - 1)
    t, models = make([reply('follow', 'Anything else to add there?')], notes)
    result = asyncio.run(t.respond(LONGER))
    assert result['reply'] and result['process_turn']['notes']
    log = asyncio.run(t.finish_notes(result['process_turn']['turn']))
    sent = [json.loads(json.dumps(c))['messages'][1]['content'] for c in models.calls if c['model'] == NOTE_MODEL]
    assert len(sent) == len(parts) and log['parts'] == len(parts) and t.pending == []
    assert sent[0].endswith('ANSWER: ' + parts[0]) and '(the same answer, continued)' in sent[1]
    assert [s['label'] for p in t.model['processes'] for s in p['steps']] == ['Customer comes to till']


def test_in_the_loop_a_failed_reply_keeps_the_answer_and_the_next_one_starts_afresh(tmp_path):
    from services.sme_interviewer.continuous import Conversation
    from services.sme_interviewer.evidence import FixtureEvidence
    from services.sme_interviewer.interview import Interviews
    from tests.test_sme_continuous_tibi import Engine

    async def run():
        interviews = Interviews(tmp_path)
        evidence = {**FixtureEvidence().snapshot(), 'process_interview': {'space': 'beepee', 'space_name': 'BeePee'}}
        session = interviews.store.create(evidence, {'region': 'unknown', 'variant': 'unknown', 'date': ''}, str(uuid.uuid4()))
        models = FakeModels([reply('role', 'And your role?')], [{'changes': []}, {'changes': []}])
        made, events = [], []

        def factory(saved):
            t = ProcessInterviewer(saved, 'token', 'http://core')
            t.transport = httpx.MockTransport(models)
            made.append(t)
            return t
        interviews.process_companion_factory = factory

        async def send(event):
            events.append(event)
            if event['type'] == 'audio_chunk':
                c.audio_ack({'generation_id': event['generation_id'], 'index': event['index']})
        c = Conversation(tmp_path, interviews, session, send, Engine(), Engine(), Engine())
        c.paused = False
        original = made[0].respond

        async def failing(text):
            made[0].note(text, made[0].opening, 1)  # its notes had started, as they do
            raise RuntimeError('the reply model failed')
        made[0].respond = failing
        c.inflight_text = "I'm Bruno."
        await c.social_chat("I'm Bruno.", c.generation)
        failed = (c.inflight_text, list(c.continuation), [p['answer'] for p in made[0].pending])
        made[0].respond = original
        await c.social_chat("I'm a business process manager.", c.generation)
        return failed, events
    (inflight, continuation, pending), events = asyncio.run(run())
    assert inflight is None and continuation == []  # the next words are not joined to the failed answer
    assert pending == ["I'm Bruno."]  # nor is the failed answer lost: it waits for the note-taker
    errors = [e['message'] for e in events if e['type'] == 'error']
    assert errors == ['The local conversation model could not reply. Please retry, or pause.']
    assert any(e['type'] == 'social_reply' for e in events)  # and the next answer is replied to


def test_carrying_on_before_the_last_part_is_transcribed_keeps_that_part(tmp_path):
    """PI F17: a spoken replay lost a description's first 307 characters. The speaker carried on 0.3 s after the turn
    ended, before its wording was known; that transcript belonged to a replaced turn and was dropped."""
    import base64

    from services.sme_interviewer.continuous import Conversation
    from services.sme_interviewer.evidence import FixtureEvidence
    from services.sme_interviewer.interview import Interviews
    from tests.test_sme_continuous_tibi import Engine

    class SlowRecogniser(Engine):
        def __init__(self):
            super().__init__()
            self.heard, self.release = [], asyncio.Event()

        async def final(self, pcm):
            self.heard.append(len(pcm))
            if len(self.heard) == 1:
                await self.release.wait()  # the first part is still being transcribed when they carry on
            return {'text': 'The whole answer.', 'no_speech': 0.01}

    class Voice(Engine):
        probability = 0

        async def infer(self, floats):
            return {'probability': self.probability}

    async def run():
        interviews = Interviews(tmp_path)
        evidence = {**FixtureEvidence().snapshot(), 'process_interview': {'space': 'beepee', 'space_name': 'BeePee'}}
        session = interviews.store.create(evidence, {'region': 'unknown', 'variant': 'unknown', 'date': ''}, str(uuid.uuid4()))
        models = FakeModels([reply('role', 'And your role?')], [{'changes': []}])

        def factory(saved):
            t = ProcessInterviewer(saved, 'token', 'http://core')
            t.transport = httpx.MockTransport(models)
            return t
        interviews.process_companion_factory = factory
        events = []

        async def send(event):
            events.append(event)
            if event['type'] == 'audio_chunk':
                c.audio_ack({'generation_id': event['generation_id'], 'index': event['index']})
        asr, vad = SlowRecogniser(), Voice()
        c = Conversation(tmp_path, interviews, session, send, asr, vad, Engine())
        c.paused, c.smart_endpoint = False, False
        frame, sequence = base64.b64encode(bytes(1024)).decode(), 0

        async def feed(count, probability):
            nonlocal sequence
            vad.probability = probability
            for _ in range(count):
                sequence += 1
                await c.feed({'sequence': sequence, 'pcm': frame})
        c.sequence = 0
        await feed(40, 0.9)   # part A: 1.3 s of speech
        await feed(40, 0.0)   # the pause: the turn ends, and A's transcript is under way
        for _ in range(100):
            if asr.heard:
                break
            await asyncio.sleep(0.01)
        assert any(e['type'] == 'endpoint' for e in events) and len(asr.heard) == 1
        await feed(30, 0.9)   # they carry on before A's wording is known
        asr.release.set()
        await feed(40, 0.0)   # part B ends
        for _ in range(100):
            if len(asr.heard) >= 2:
                break
            await asyncio.sleep(0.01)
        await c.close()
        return asr.heard
    heard = asyncio.run(run())
    first, joined = heard[0], heard[-1]
    assert joined > first + 30 * 2048  # the final transcript covers part A and part B together


def test_a_read_back_asked_for_is_given_not_the_next_question():
    """PI F19: on 29 September "play it back to me" was asked three times, and "go ahead and check" after Tibi offered to."""
    from tests.test_sme_process_model import till

    for said, which in (('Playback to me what you managed to understand from it.', None),
                        ('Can you play it back to me what you already captured as option 1 before we go and cover option 2?', 1),
                        ('Please go ahead and check', None), ('What have you got for the third option?', 3)):
        t, models = make(session={**SESSION, 'process_model': till()})
        result = turn(t, said)
        assert result['reply'].endswith('Is that right?') and models.calls == [], said
        assert ('The first path, Tobacco' in result['reply']) == (which in (None, 1)), said
        assert (which == 3) == result['reply'].startswith('The third path, No age limit: not described yet'), said
    t, _ = make(notes=[{'changes': []}], session={**SESSION, 'process_model': till()})
    t.notes_budget = None
    assert not turn(t, 'The cashier will check that the customer is old enough.')['reply'].startswith('Here is what I have')


def test_after_tibi_offers_to_check_a_yes_or_nothing_more_gets_the_read_back():
    from tests.test_sme_process_model import till

    for answer in ('Yes, please.', 'No, that is all.', 'Go ahead'):
        t, models = make(session={**SESSION, 'process_model': till()})
        t.offered_check = True
        said = turn(t, answer)['reply']
        assert said.startswith('Here is what I have for Carrying out cashiering') and models.calls == [], answer
    t, _ = make([reply('purpose:p1', 'What is it for?')], [{'changes': []}], session={**SESSION, 'process_model': till()})
    assert not turn(t, 'Yes, please.')['reply'].startswith('Here is what I have')  # no offer, no read-back


def test_show_me_asks_for_the_read_back_too():
    """PI F21: on 1 October "show me what you've got" and "just show me the process" were not honoured."""
    from tests.test_sme_process_model import till

    for said in ("Show me what you've got.", 'Not just show me the process', 'No, nothing more just show me the process'):
        t, models = make(session={**SESSION, 'process_model': till()})
        result = turn(t, said)
        assert result['reply'].startswith('Here is what I have for Carrying out cashiering') and models.calls == [], said


def test_starting_from_scratch_is_asked_then_done_on_yes_and_left_on_no():
    """PI F21: "shall we start from scratch? Can you remove all those items you have in the design?" was thanked for
    "a lot of useful detail"."""
    from tests.test_sme_process_model import till

    said = ("So I don't think what you're showing me is correct at all So shall we start from scratch? "
            "Can you remove all those items you have in the design?")
    t, models = make(session={**SESSION, 'process_model': till()})
    asked = turn(t, said)
    assert asked['reply'] == ("Shall I clear everything I've captured for Carrying out cashiering and start again from "
                              "the beginning?") and models.calls == []
    done = turn(t, 'Yes please.')
    assert done['reply'].startswith('Done: I\'ve cleared everything for "Carrying out cashiering".')
    cleared = t.model['processes'][0]
    assert cleared['name'] == 'Carrying out cashiering' and cleared['steps'] == [] and cleared['details'] == {}
    assert t.model['participant'] == till()['participant']
    t2, _ = make(session={**SESSION, 'process_model': till()})
    assert turn(t2, 'Can you delete the diagram?')['reply'].startswith('Shall I clear everything')
    assert turn(t2, 'No, leave it.')['reply'].startswith("All right, I've left it as it was.")
    assert t2.model['processes'][0]['steps'] == till()['processes'][0]['steps']


def test_a_request_is_answered_as_one_never_thanked_for_detail():
    """PI F21: requests were answered "That's a lot of useful detail, thank you. Anything else to add there?"."""
    import services.sme_interviewer.process_interviewer as module
    from tests.test_sme_process_model import till

    t, _ = make(notes=[{'changes': []}], session={**SESSION, 'process_model': till()})
    assert turn(t, 'Can you correct something?')['reply'] == module.ASK_WHICH
    t, _ = make(notes=[{'changes': []}], session={**SESSION, 'process_model': till()})
    assert turn(t, 'Can you make the boxes a different colour for each role?')['reply'] == module.CANNOT

    async def slow_notes(request):  # the note-taker has not finished with the request when the reply is due
        if json.loads(request.content)['model'] == NOTE_MODEL:
            await asyncio.sleep(0.3)
        return FakeModels(notes=[{'changes': []}])(request)
    wait, budget = module.REQUEST_SECONDS, module.notes_budget
    module.REQUEST_SECONDS, module.notes_budget = 0.05, lambda text, turn: 0.05
    try:
        t = ProcessInterviewer({**SESSION, 'process_model': till()}, 'token', 'http://core')
        t.transport = httpx.MockTransport(slow_notes)
        answer = asyncio.run(t.respond('Could you take the drawer step out?'))
    finally:
        module.REQUEST_SECONDS, module.notes_budget = wait, budget
    assert answer['reply'] == module.CATCHING_UP and answer['reply'] not in module.HOLDING


def test_a_short_answer_not_yet_noted_is_not_thanked_for_a_lot_of_detail():
    import services.sme_interviewer.process_interviewer as module
    from tests.test_sme_process_model import till

    async def slow_notes(request):
        if json.loads(request.content)['model'] == NOTE_MODEL:
            await asyncio.sleep(0.3)
        return FakeModels(notes=[{'changes': []}])(request)
    budget = module.notes_budget
    module.notes_budget = lambda text, turn: 0.05
    try:
        for n in range(3):  # whichever line the turn would pick
            t = ProcessInterviewer({**SESSION, 'process_model': till()}, 'token', 'http://core')
            t.transport = httpx.MockTransport(slow_notes)
            t.turn = n
            answer = asyncio.run(t.respond('Then the cashier scans it.'))
            assert answer['reply'] not in module.HOLDING[:2], answer['reply']
    finally:
        module.notes_budget = budget
