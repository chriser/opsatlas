"""Conversation orchestration of streamed Tibi turns (independent review 2)."""
import asyncio
import base64
import copy
import json
import uuid
from pathlib import Path

from services.sme_interviewer.continuous import Conversation
from services.sme_interviewer.evidence import FixtureEvidence
from services.sme_interviewer.interview import Interviews
from services.sme_interviewer.tibi import CONVERSATION, EVIDENCE, Evidence, Tibi

RECORDS = {r['id']: {**r, 'eligible': True, 'sha256': r['id'] * 4, 'source_id': 's-' + r['id'], 'references': [],
                     'audience': 'internal_rehearsal'}
           for r in json.loads((Path(__file__).parents[1] / 'services/opsatlas_sales/corpus/product.json').read_text())}


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


class FakeEvidence(Evidence):
    def __init__(self):
        super().__init__('fake', 'http://core')
        self.records, self.variants, self.digest, self.live = dict(RECORDS), [], 'd1', 'd1'

    async def search(self, text):
        similarity = 0.86 if 'OpsAtlas' in text else 0.3
        return {'digest': self.digest, 'mode': 'hybrid', 'results': [
            {'id': 'overview', 'similarity': similarity, 'relevant': similarity > 0.55, 'score': 1, 'lexical': 1}]}

    async def current(self):
        return self.live

    async def refresh(self, digest=None):
        pass


def setup(tmp_path, replies):
    interviews = Interviews(tmp_path)
    tibi = Tibi([], 'fake', 'http://core')
    tibi.evidence = FakeEvidence()
    tibi.streams = []

    async def stream(system, user, history=()):
        tibi.streams.append(system)
        for piece in replies[system]:
            await asyncio.sleep(0)
            yield piece

    async def review(text, reply):
        tibi.reviews = getattr(tibi, 'reviews', 0) + 1
        await tibi.review_gate.wait()
        return {'status': 'consistent', 'ids': [], 'subject': 'none', 'quote': '', 'question': ''}

    tibi._stream, tibi.review, tibi.review_gate = stream, review, asyncio.Event()
    interviews.companion_factory = lambda history: tibi
    session = interviews.store.create(FixtureEvidence().snapshot(), {'region': 'unknown', 'variant': 'unknown', 'date': ''},
                                      str(uuid.uuid4()))
    events = []

    async def send(event):
        events.append(copy.deepcopy(event))
        if event['type'] == 'audio_chunk':
            c.audio_ack({'generation_id': event['generation_id'], 'index': event['index']})

    speaker = Engine()
    c = Conversation(tmp_path, interviews, session, send, Engine(), Engine(), speaker)
    c.paused = False
    return c, events, tibi, speaker


def types(events):
    return [e['type'] for e in events]


def test_segments_play_in_order_as_one_utterance_and_commit_after_speech(tmp_path):
    async def run():
        c, events, tibi, speaker = setup(tmp_path, {CONVERSATION: ['OK\n', 'Ready to listen. ', 'How is your day?']})
        await c.tibi_chat('Hello, how are you?', c.generation)
        await c.close()
        return c, events, tibi, speaker
    c, events, tibi, speaker = asyncio.run(run())
    kinds = types(events)
    assert kinds.count('speech') == 1 and kinds.count('speech_append') == 1 and kinds.count('audio_end') == 1
    assert kinds.index('reply_preparing') < kinds.index('speech') < kinds.index('speech_done') < kinds.index('social_reply')
    assert speaker.spoken == ['Ready to listen.', 'How is your day?']
    assert tibi.history[-1]['content'] == 'Ready to listen. How is your day?'
    saved = c.interviews.store.get(c.session['id'])
    assert saved['social_transcript'][-1]['content'] == 'Ready to listen. How is your day?'
    assert saved['turn_marks'][-1]['route'] == 'conversation' and 'first_segment' in saved['turn_marks'][-1]


def test_matching_speculation_is_adopted_and_a_mismatch_is_discarded(tmp_path):
    async def run():
        c, events, tibi, _ = setup(tmp_path, {CONVERSATION: ['OK\n', 'Sure thing.']})
        c.tibi_preview = {'text': 'Hello there', 'turn': tibi.begin('Hello there', speculative=True),
                          'generation': c.generation, 'audio': {}}
        c.tibi_preview['feeder'] = c.task(c.prepare_preview(c.tibi_preview))
        await asyncio.sleep(0.01)
        await c.tibi_chat('Hello there', c.generation)
        adopted = next(e for e in events if e['type'] == 'reply_preparing')['speculative']
        streams = len(tibi.streams)
        stale = tibi.begin('Something else', speculative=True)
        c.tibi_preview = {'text': 'Something else', 'turn': stale, 'generation': c.generation, 'audio': {}}
        c.tibi_preview['feeder'] = c.task(c.prepare_preview(c.tibi_preview))
        await c.tibi_chat('Hello again', c.generation)
        await asyncio.gather(stale.task, return_exceptions=True)
        await c.close()
        return adopted, streams, stale, tibi
    adopted, streams, stale, tibi = asyncio.run(run())
    assert adopted is True and streams == 1  # one model call: the speculative one
    assert tibi.history[-1]['content'] == 'Sure thing.'


def test_product_check_survives_interruption_and_is_recorded_when_the_session_ends(tmp_path):
    async def run():
        c, events, tibi, _ = setup(tmp_path, {EVIDENCE: ['OpsAtlas combines approved document retrieval with structured knowledge.']})
        await c.tibi_chat('I heard OpsAtlas supports enterprise roles.', c.generation)
        await asyncio.sleep(0.01)
        assert c.pending_checks and tibi.reviews == 1
        c.interrupt()                       # the participant speaking does not stop a check on its own model
        await asyncio.sleep(0.01)
        assert not c.product_check.done()
        c.pause_checks()                     # preparing the next reply does
        await asyncio.sleep(0.01)
        assert c.product_check.done() and c.pending_checks  # still queued, not dropped
        await c.close()                      # session ends before it can run
        return c
    c = asyncio.run(run())
    checks = c.interviews.store.get(c.session['id'])['knowledge_checks']
    assert checks[-1]['status'] == 'unavailable' and 'ended before' in checks[-1]['reason']


def test_completed_product_check_is_saved_after_speech(tmp_path):
    async def run():
        c, events, tibi, _ = setup(tmp_path, {EVIDENCE: ['OpsAtlas combines approved document retrieval with structured knowledge.']})
        tibi.review_gate.set()
        await c.tibi_chat('I heard OpsAtlas supports enterprise roles.', c.generation)
        await asyncio.sleep(0.05)
        pending = list(c.pending_checks)
        await c.close()
        return c, pending
    c, pending = asyncio.run(run())
    assert not pending
    assert c.interviews.store.get(c.session['id'])['knowledge_checks'][-1]['status'] == 'consistent'


def test_changed_evidence_speaks_a_retry_message_not_the_answer(tmp_path):
    async def run():
        c, events, tibi, speaker = setup(tmp_path, {EVIDENCE: ['OpsAtlas combines approved document retrieval.']})
        tibi.evidence.live = 'changed'
        await c.tibi_chat('What is OpsAtlas used for?', c.generation)
        await c.close()
        return speaker
    speaker = asyncio.run(run())
    assert speaker.spoken == ['The evidence changed while I checked. Please ask again so I can use the current version.']


def test_approved_answer_uses_pre_rendered_audio(tmp_path):
    async def run():
        c, events, tibi, speaker = setup(tmp_path, {})
        key = 'b' * 64
        tibi.evidence.variants = [{'id': 'v', 'record_id': 'overview', 'text': 'OpsAtlas brings approved knowledge together.',
                                   'text_sha256': key, 'usable': True}]
        c.spoken_audio.put('higgs', key, [{'rate': 24000, 'pcm': base64.b64encode(bytes(960)).decode()}])
        await c.tibi_chat('What is OpsAtlas?', c.generation)
        await c.close()
        return events, speaker
    events, speaker = asyncio.run(run())
    assert speaker.spoken == []  # no synthesis: the approved audio was pre-rendered
    assert sum(e['type'] == 'audio_chunk' for e in events) == 1


def test_settled_partial_covering_all_speech_is_reused_as_the_final_wording(tmp_path):
    class Recognizer(Engine):
        finals = 0

        async def final(self, pcm):
            Recognizer.finals += 1
            return {'text': 'Hello there', 'no_speech': 0.01}

    async def run(covering):
        c, events, tibi, _ = setup(tmp_path / str(covering), {CONVERSATION: ['OK\n', 'Hi.']})
        c.asr = Recognizer()
        c.markers = {'speech_end_sample': 16000}
        c.last_recognition = {'result': {'text': 'Hello there', 'no_speech': 0.01}, 'end': 19200,
                              'voice': 16000 if covering else 12000, 'generation': c.generation}
        await c.complete(b'\0' * 4096, c.generation)
        await c.close()
        return [e['text'] for e in events if e['type'] == 'final_transcript']
    assert asyncio.run(run(True)) == ['Hello there'] and Recognizer.finals == 0
    assert asyncio.run(run(False)) == ['Hello there'] and Recognizer.finals == 1


def test_recognition_vocabulary_is_bounded_and_asr_only(tmp_path):
    import pytest

    from services.sme_interviewer.resident import Resident
    assert Resident(tmp_path, 'asr', 'ggml-small.en.bin', 'OpsAtlas, Tibi.').vocabulary == 'OpsAtlas, Tibi.'
    assert Resident(tmp_path, 'vad', 'ggml-small.en.bin', 'OpsAtlas').vocabulary is None
    with pytest.raises(ValueError):
        Resident(tmp_path, 'asr', 'ggml-small.en.bin', 'x' * 401)


def test_idle_prerender_renders_approved_wording_once_in_the_live_voice(tmp_path):
    async def run():
        c, events, tibi, speaker = setup(tmp_path, {})
        key = 'c' * 64
        tibi.evidence.variants = [{'id': 'v', 'record_id': 'overview', 'text': 'OpsAtlas brings approved knowledge together.',
                                   'text_sha256': key, 'usable': True}]
        loop = asyncio.create_task(c.prerender_loop())
        for _ in range(60):
            await asyncio.sleep(0.1)
            if c.spoken_audio.get('higgs', key):
                break
        loop.cancel()
        await asyncio.gather(loop, return_exceptions=True)
        await c.close()
        return c, speaker, key
    c, speaker, key = asyncio.run(run())
    assert speaker.spoken == ['OpsAtlas brings approved knowledge together.']
    assert c.spoken_audio.get('higgs', key)


def test_background_sound_captions_are_not_answered(tmp_path):
    from services.sme_interviewer.continuous import spoken
    assert spoken('(gentle music)') == '' and spoken('[BLANK_AUDIO]') == '' and spoken('♪♪') == ''
    assert spoken('(laughs) Yes, go on.') == 'Yes, go on.'

    class Music(Engine):
        async def final(self, pcm):
            return {'text': ' (gentle music)', 'no_speech': 0.01}

    async def run():
        c, events, tibi, speaker = setup(tmp_path, {CONVERSATION: ['OK\n', 'Pending checks will clarify that.']})
        c.asr = Music()
        c.markers = {'speech_end_sample': 16000}
        await c.complete(b'\0' * 4096, c.generation)
        await c.close()
        return events, speaker, tibi
    events, speaker, tibi = asyncio.run(run())
    assert speaker.spoken == [] and not tibi.streams
    assert [e['action'] for e in events if e['type'] == 'listener_action'] == ['ignored_sound']


def test_a_governance_interview_saves_through_the_streamed_path_only_after_speech(tmp_path):
    from services.sme_interviewer.governance_interviewer import GovernanceInterviewer

    item = {'key': 'k1', 'kind': 'issue', 'check': 'readability', 'category': 'compliance', 'severity': 'low',
            'spoken_title': 'Design notes', 'source_title': 'Design notes', 'detail': '3 long sentences',
            'examples': ['A very long sentence.'], 'answer': None,
            'issues': [{'key': 'k1', 'source_id': 's1', 'source_title': 'Design notes', 'check': 'readability', 'detail': 'd'}]}

    async def run():
        interviews = Interviews(tmp_path)
        session = interviews.store.create(FixtureEvidence().snapshot(), {'region': 'unknown', 'variant': 'unknown', 'date': ''},
                                          str(uuid.uuid4()))
        g = GovernanceInterviewer({**session, 'evidence': {'governance_interview': {'contributor': 'Chris'}}}, 't', 'http://core')
        posted = []

        async def call(method, path, body=None, timeout=30):
            posted.append(path)
            return {'items': [item], 'issues': 1} if path.endswith('agenda') else {'verification': []}
        g._call = call
        await g.load()
        interviews.companion_factory = lambda history: g
        events = []

        async def send(event):
            events.append(event)
            if event['type'] == 'audio_chunk':
                c.audio_ack({'generation_id': event['generation_id'], 'index': event['index']})
        speaker = Engine()
        c = Conversation(tmp_path, interviews, session, send, Engine(), Engine(), speaker)
        c.paused = False
        for text in ('Start', 'Keep them as they are.', 'Yes.'):
            await c.tibi_chat(text, c.generation)
        await c.close()
        return g, posted, speaker
    g, posted, speaker = asyncio.run(run())
    assert posted.count('/api/sales/governance/answers') == 1 and g.state['saved'] == 1
    assert 'Saved for your approval.' in speaker.spoken


def governance_run(tmp_path, items, answers, cut):
    """A governance interview in the streamed loop. ``cut(event)`` says when the Human interrupts: the loop reports
    "speech" when a reply starts playing and "speech_append" when each later line starts, so the lines before it
    have been heard in full. Interruptions are armed for the last answer only."""
    from services.sme_interviewer.governance_interviewer import GovernanceInterviewer

    async def run():
        interviews = Interviews(tmp_path)
        session = interviews.store.create(FixtureEvidence().snapshot(), {'region': 'unknown', 'variant': 'unknown', 'date': ''},
                                          str(uuid.uuid4()))
        g = GovernanceInterviewer({**session, 'evidence': {'governance_interview': {'contributor': 'Chris'}}}, 't', 'http://core')
        posted, armed = [], {'on': False}

        async def call(method, path, body=None, timeout=30):
            posted.append(path)
            return {'items': items, 'issues': len(items)} if path.endswith('agenda') else {'verification': []}
        g._call = call
        await g.load()
        interviews.companion_factory = lambda history: g

        async def send(event):
            if armed['on'] and event['type'] in ('speech', 'speech_append') and cut(event):
                armed['on'] = False
                c.interrupt()
            if event['type'] == 'audio_chunk':
                c.audio_ack({'generation_id': event['generation_id'], 'index': event['index']})
        c = Conversation(tmp_path, interviews, session, send, Engine(), Engine(), Engine())
        c.paused = False
        for n, text in enumerate(answers):
            armed['on'] = n == len(answers) - 1
            await c.tibi_chat(text, c.generation)
        await c.close()
        return g, posted, c
    return asyncio.run(run())


def readability(key):
    return {'key': key, 'kind': 'issue', 'check': 'readability', 'category': 'compliance', 'severity': 'low',
            'spoken_title': 'Design notes', 'source_title': 'Design notes', 'detail': '3 long sentences',
            'examples': ['A very long sentence.'], 'answer': None,
            'issues': [{'key': key, 'source_id': 's1', 'source_title': 'Design notes', 'check': 'readability', 'detail': key}]}


def test_a_save_tibi_has_announced_survives_an_interruption_during_the_next_question(tmp_path):
    """Evaluation 5 follow-up: the Human typed an answer while Tibi read the next question; the save was lost
    although Tibi had said "Saved for your approval.", and the answer was heard against the old question."""
    answers = ('Start', 'Keep them as they are.', 'Yes.')
    # Cut off as the next question starts: "Saved for your approval." was heard, so the save stands.
    g, posted, c = governance_run(tmp_path / 'a', [readability('k1'), readability('k2')], answers,
                                  lambda e: e['type'] == 'speech_append' and e['text'].startswith('Next.'))
    assert posted.count('/api/sales/governance/answers') == 1 and g.state['saved'] == 1 and g.state['position'] == 1
    assert any(t.get('interrupted') for t in c.session['social_transcript'])
    # Cut off before "Saved for your approval." had played: nothing was promised and nothing is saved; the read-back
    # the Human did hear stands, so the interview still waits for their confirmation.
    g, posted, _ = governance_run(tmp_path / 'b', [readability('k1'), readability('k2')], answers,
                                  lambda e: e['type'] == 'speech' and e['text'] == 'Saved for your approval.')
    assert posted.count('/api/sales/governance/answers') == 0 and g.state['saved'] == 0 and g.state['position'] == 0
    assert g.state['phase'] == 'confirm'


def test_an_answer_given_while_tibi_reads_the_question_applies_to_that_question(tmp_path):
    """Typing while Tibi still read question 1 used to discard the turn that moved to question 1."""
    g, _, _ = governance_run(tmp_path, [readability('k1')], ('Start',),
                             lambda e: e['type'] == 'speech_append' and e['text'].startswith('3 very long'))
    assert (g.state['position'], g.state['phase']) == (0, 'ask')  # "Question 1 of 1." was heard
    # Cut off before the question line had played: the interview has not moved.
    g, _, _ = governance_run(tmp_path / 'b', [readability('k1')], ('Start',),
                             lambda e: e['type'] == 'speech' and e['text'] == "Great, let's start.")
    assert g.state['phase'] == 'start'
