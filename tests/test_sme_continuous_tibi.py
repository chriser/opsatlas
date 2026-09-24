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
        await c.tibi_chat('What is OpsAtlas used for?', c.generation)
        await asyncio.sleep(0.01)
        assert c.pending_checks and tibi.reviews == 1
        c.interrupt()                       # the participant starts speaking
        await asyncio.sleep(0.01)
        assert c.pending_checks              # still queued, not dropped
        await c.close()                      # session ends before it can run
        return c
    c = asyncio.run(run())
    checks = c.interviews.store.get(c.session['id'])['knowledge_checks']
    assert checks[-1]['status'] == 'unavailable' and 'ended before' in checks[-1]['reason']


def test_completed_product_check_is_saved_after_speech(tmp_path):
    async def run():
        c, events, tibi, _ = setup(tmp_path, {EVIDENCE: ['OpsAtlas combines approved document retrieval with structured knowledge.']})
        tibi.review_gate.set()
        await c.tibi_chat('What is OpsAtlas used for?', c.generation)
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
