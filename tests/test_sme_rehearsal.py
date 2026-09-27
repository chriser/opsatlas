"""Sales rehearsal and name activation (TIBI E3): Tibi observes the meeting and helps only when asked."""
import asyncio
import base64
import copy
import json
import uuid
from pathlib import Path

from services.sme_interviewer.continuous import Conversation
from services.sme_interviewer.evidence import FixtureEvidence
from services.sme_interviewer.interview import Interviews
from services.sme_interviewer.rehearsal import RehearsalCoach, intent_of
from services.sme_interviewer.tibi import EVIDENCE, Evidence
from services.sme_interviewer.wake import addressed, echo_of

RECORDS = {r['id']: {**r, 'eligible': True, 'sha256': r['id'] * 4, 'source_id': 's-' + r['id'], 'references': [],
                     'audience': 'internal_rehearsal'}
           for r in json.loads((Path(__file__).parents[1] / 'services/opsatlas_sales/corpus/product.json').read_text())}


class FakeEvidence(Evidence):
    def __init__(self):
        super().__init__('fake', 'http://core')
        self.records, self.variants, self.digest, self.live = dict(RECORDS), [], 'd1', 'd1'
        self.searches = []

    async def search(self, text):
        self.searches.append(text)
        return {'digest': self.digest, 'mode': 'hybrid', 'results': [
            {'id': 'overview', 'similarity': 0.8, 'relevant': True, 'score': 1, 'lexical': 1}]}

    async def current(self):
        return self.live

    async def refresh(self, digest=None):
        pass


def coach(replies=None, customer=''):
    c = RehearsalCoach([], 'fake', 'http://core', customer=customer)
    c.evidence = FakeEvidence()
    c.calls = []

    async def stream(system, user, history=()):
        c.calls.append((system, json.loads(user)))
        for piece in (replies or {}).get(system, ['OpsAtlas answers from approved evidence. ']):
            await asyncio.sleep(0)
            yield piece
    c._stream = stream
    return c


async def run(t, text):
    turn = t.begin(text)
    spoken = []
    while (segment := await turn.next()) is not None:
        spoken.append(segment.text)
    await turn.task
    return spoken, turn.result


def test_the_name_counts_only_when_tibi_is_addressed():
    for said, request in (('Tibi, what have I missed?', 'what have I missed?'), ('Hey Tiberius, explain that more simply.',
                          'explain that more simply.'), ('What have I missed, Tibi?', 'What have I missed'), ('Tibi?', ''),
                          ('Tibby, help me answer that.', 'help me answer that.'), ('OK Tibi give me an example', 'give me an example'),
                          ('Tibi what have I missed', 'what have I missed'),
                          ('We have forty branches. Tibi, what have I missed?', 'what have I missed?'),
                          # As the spoken test heard them (evaluate_wake, 26 September 2026).
                          ('OkTibi, give an example relevant to this customer.', 'give an example relevant to this customer.'),
                          ('OKTb, give an example.', 'give an example.'), ('ATB, explain that more simply.', 'explain that more simply.'),
                          ('Tibiarius, help me answer that question.', 'help me answer that question.')):
        assert addressed(said) == (True, request), said
    for said in ('I told Tibi about it yesterday.', "Tibi's voice is nice.", 'The TV was on.', 'Toby, can you pass that?',
                 'We met at the Tiber.', 'Our team uses Tibco.', 'Tibi is our assistant.', 'Tibi helped us last week.',
                 'TB is still a problem in some regions.', 'A TBC answer is not good enough.'):
        assert addressed(said)[0] is False, said
    reply = 'My day is a steady stream of conversations like this one.'
    assert echo_of('steady stream of conversations like this one', reply)
    assert not echo_of('we are a regional bank with forty branches', reply) and not echo_of('yes', reply)


def test_requests_are_recognised_by_what_they_ask_for():
    assert intent_of('What have I missed?') == 'missed' and intent_of('Anything I left out?') == 'missed'
    assert intent_of('Explain that more simply.') == 'simpler' and intent_of('Can you put it in plain English?') == 'simpler'
    assert intent_of('Help me answer that question.') == 'answer' and intent_of('How should I answer that?') == 'answer'
    assert intent_of('Give an example relevant to this customer.') == 'example'
    assert intent_of('Does it support single sign-on?') == 'ask'


def test_each_request_is_shaped_by_the_meeting():
    c = coach(customer='Regional bank, head of operations')
    for line in ('OpsAtlas answers questions from approved company knowledge.', 'We are a regional bank with forty branches.',
                 'How long would it take to set up for us?'):
        c.observe(line)
    answer = asyncio.run(c.route('Help me answer that question.'))
    assert answer.kind == 'rehearsal' and answer.question == 'How long would it take to set up for us?'
    assert answer.context['meeting_so_far'][-1] == 'How long would it take to set up for us?'
    assert 'regional bank' in answer.context['customer'].lower() and 'no question' in answer.voice.lower()
    simpler = asyncio.run(c.route('Explain that more simply.'))
    assert simpler.question == 'Explain more simply: OpsAtlas answers questions from approved company knowledge.'
    example = asyncio.run(c.route('Give an example relevant to this customer.'))
    assert 'regional bank' in example.question.lower()
    missed = asyncio.run(c.route('What have I missed?'))
    chosen = [r['id'] for r in missed.ranking['results']]
    assert len(chosen) == 3 and 'overview' not in chosen  # the records the meeting has said least about


def test_a_rehearsal_reply_is_brief_grounded_and_hands_back_the_floor():
    c = coach({EVIDENCE: ['OpsAtlas answers from approved evidence. ', 'It cites the records it used. ', 'Shall I say more?']})
    c.observe('How does it make sure answers are right?')
    spoken, result = asyncio.run(run(c, 'Help me answer that question.'))
    assert result['route'] == 'rehearsal' and result['route_reasons'] == ['rehearsal: answer']
    assert not any(s.endswith('?') for s in spoken) and len(' '.join(spoken)) <= 300
    sent = c.calls[-1][1]
    assert sent['question'] == 'How does it make sure answers are right?' and sent['meeting_so_far']
    assert 'how_to_answer' in sent


class Engine:
    engine = 'higgs'

    def __init__(self):
        self.spoken = []

    async def start(self):
        pass

    async def infer(self, pcm):
        return {'probability': 0, 'text': 'Hello', 'no_speech': 0.01}

    async def stream(self, text, style=None):
        self.spoken.append(text)
        yield {'rate': 24000, 'pcm': base64.b64encode(bytes(480)).decode()}

    async def close(self):
        pass


def conversation(tmp_path, keep=False, name=False):
    interviews = Interviews(tmp_path)
    tibi = coach({EVIDENCE: ['OpsAtlas answers from approved evidence. ']})
    interviews.rehearsal_companion_factory = lambda session: tibi
    evidence = {**FixtureEvidence().snapshot(), 'sales_rehearsal': {'customer': '', 'listen_for_name': name, 'keep_transcript': keep}}
    session = interviews.store.create(evidence, {'region': 'unknown', 'variant': 'unknown', 'date': ''}, str(uuid.uuid4()))
    events = []

    async def send(event):
        events.append(copy.deepcopy(event))
        if event['type'] == 'audio_chunk':
            c.audio_ack({'generation_id': event['generation_id'], 'index': event['index']})
    speaker = Engine()
    c = Conversation(tmp_path, interviews, session, send, Engine(), Engine(), speaker)
    c.paused = False
    return c, events, tibi, speaker


def test_the_meeting_is_heard_not_answered_and_not_kept_unless_chosen(tmp_path):
    async def go():
        c, events, tibi, speaker = conversation(tmp_path)
        assert c.rehearsal
        await c.rehearsal_heard('We are a regional bank with forty branches.', c.generation)
        await c.close()
        return c, events, tibi, speaker
    c, events, tibi, speaker = asyncio.run(go())
    assert [e['type'] for e in events if e['type'] in ('meeting_line', 'speech')] == ['meeting_line']
    assert speaker.spoken == [] and list(tibi.meeting) == ['We are a regional bank with forty branches.']
    saved = c.interviews.store.get(c.session['id'])
    assert 'meeting_transcript' not in saved and not saved.get('product_turns')


def test_ask_tibi_makes_the_next_utterance_a_request_and_the_floor_returns(tmp_path):
    async def go():
        c, events, tibi, speaker = conversation(tmp_path, keep=True)
        await c.rehearsal_heard('How does it make sure answers are right?', c.generation)
        await c.activate()
        await c.rehearsal_heard('Help me answer that question.', c.generation)
        await c.rehearsal_heard('Thanks, that helps.', c.generation)
        await c.close()
        return c, events, speaker
    c, events, speaker = asyncio.run(go())
    assert speaker.spoken == ['OpsAtlas answers from approved evidence.']
    states = [e['state'] for e in events if e['type'] == 'rehearsal']
    assert states[:2] == ['addressed', 'answering'] and states[-1] == 'observing'  # the floor is back
    saved = c.interviews.store.get(c.session['id'])
    assert [m['text'] for m in saved['meeting_transcript']] == ['How does it make sure answers are right?', 'Thanks, that helps.']
    assert saved['social_transcript'][-1]['content'] == 'OpsAtlas answers from approved evidence.'


def test_the_name_asks_tibi_and_tibis_own_voice_is_ignored_and_mute_stops_listening(tmp_path):
    async def go():
        c, events, tibi, speaker = conversation(tmp_path, name=True)
        await c.rehearsal_heard('I told Tibi about the pilot yesterday.', c.generation)  # in passing: meeting context
        await c.rehearsal_heard('Tibi, what have I missed?', c.generation)
        heard_echo = 'OpsAtlas answers from approved evidence'
        await c.rehearsal_heard(heard_echo, c.generation)  # the speakerphone let Tibi hear itself
        await c.rehearsal_heard('Tibi?', c.generation)  # the name alone
        waiting = c.awaiting_request
        await c.cancel_request()
        await c.set_muted(True)
        await c.feed({'sequence': c.sequence + 1, 'pcm': base64.b64encode(bytes(1024)).decode()})
        muted = c.speech is False and c.muted
        await c.close()
        return events, tibi, speaker, waiting, muted
    events, tibi, speaker, waiting, muted = asyncio.run(go())
    assert list(tibi.meeting) == ['I told Tibi about the pilot yesterday.']
    assert speaker.spoken[0] == 'OpsAtlas answers from approved evidence.' and 'Yes?' in speaker.spoken
    assert any(e['type'] == 'listener_action' and e.get('action') == 'ignored_echo' for e in events)
    assert waiting and muted
    assert [e['state'] for e in events if e['type'] == 'rehearsal'][-1] == 'muted'


def test_a_rehearsal_session_takes_its_settings_and_refuses_anything_else(tmp_path, monkeypatch):
    import os

    from fastapi.testclient import TestClient

    from services.sme_interviewer.sales_preview import sales_app
    monkeypatch.setattr(os, 'environ', os.environ.copy())
    app = sales_app(tmp_path / 'sales', 'http://127.0.0.1:8780')
    with TestClient(app, base_url='http://127.0.0.1:8773') as client:
        token = client.get('/api/bootstrap').json()['token']
        headers = {'x-sme-token': token, 'origin': 'http://127.0.0.1:8773'}

        def create(settings):
            return client.post('/api/interviews', headers=headers, json={
                'request_id': str(uuid.uuid4()), 'accept_local_storage': True,
                'scope': {'region': 'unknown', 'variant': 'unknown', 'date': ''}, 'sales_rehearsal': settings})
        made = create({'customer': '  Regional   bank ', 'listen_for_name': True})
        assert made.status_code == 200, made.text
        assert made.json()['evidence']['sales_rehearsal'] == {'customer': 'Regional bank', 'listen_for_name': True,
                                                              'keep_transcript': False}
        for bad in ({'customer': 'x' * 201}, {'listen_for_name': 'yes'}, {'record_audio': True}, 'on'):
            assert create(bad).status_code == 400, bad


def test_what_a_rehearsal_keeps_matches_what_it_says(tmp_path):
    # Audit F12: a distinctive meeting phrase is in no stored file without a transcript, and only in the rehearsal's
    # own record with one; requests and replies are logged as the opening says; a blocked sentence that repeats the
    # meeting keeps only its reasons.
    from services.opsatlas_sales.activity import ActivityLog
    phrase = 'Zanzibar ferry timetable'

    async def go(root, keep):
        c, events, tibi, speaker = conversation(root, keep=keep)
        c.activity, c.conversation_log = ActivityLog(root, 'tibi'), root

        async def stream(system, user, history=()):
            for piece in [f'Your {phrase} could change monthly. ', 'OpsAtlas answers from approved evidence. ']:
                yield piece
        tibi._stream = stream
        await c.rehearsal_heard(f'Our {phrase} changes every month.', c.generation)
        await c.activate()
        await c.rehearsal_heard('Help me answer that question.', c.generation)
        await c.close()
        return c

    def stored(root):
        return ' '.join(p.read_text(errors='replace') for p in root.rglob('*') if p.is_file())

    assert 'isn\'t kept unless you keep a transcript' in RehearsalCoach.opening and 'conversation log' in RehearsalCoach.opening
    off = tmp_path / 'off'
    asyncio.run(go(off, keep=False))
    assert phrase not in stored(off)
    assert 'Help me answer that question.' in stored(off / 'logs')  # requests and replies are kept, as said
    assert 'no enabled record or fact supports it' in stored(off / 'logs') or 'blocked' in stored(off / 'logs')
    on = tmp_path / 'on'
    c = asyncio.run(go(on, keep=True))
    assert phrase in json.dumps(c.interviews.store.get(c.session['id']).get('meeting_transcript'))
