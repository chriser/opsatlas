"""The stutter guard (PI F16): Tibi starts speaking only when playback will not overtake the voice being generated."""
import asyncio
import base64
import time

import pytest

from services.sme_interviewer import speech
from services.sme_interviewer.speech import PreparedSpeech

RATE = 24000
PIECE = 0.02  # seconds of audio per chunk


class Voice:
    """Generates PIECE seconds of audio per chunk, ``speed`` times faster than real time."""

    def __init__(self, speed, pieces, recent_rate=None):
        self.speed, self.pieces = speed, pieces
        if recent_rate is not None:
            self.recent_rate = recent_rate

    async def stream(self, text):
        pcm = base64.b64encode(b'\0\0' * int(RATE * PIECE)).decode()
        for index in range(self.pieces):
            if index:
                await asyncio.sleep(PIECE / self.speed)
            yield {'chunk': index, 'rate': RATE, 'pcm': pcm}


def gaps(voice, started):
    """Seconds playback would wait for audio, playing from ``started`` as the chunks arrived."""
    waited, play_end = 0.0, started
    for at, seconds in voice.arrived:
        if at > play_end:
            waited += at - play_end
            play_end = at
        play_end += seconds
    return waited


def test_a_voice_well_ahead_of_playback_starts_at_once():
    async def run():
        for worker in (Voice(4, 40), Voice(4, 40, recent_rate=1.36)):
            voice = PreparedSpeech(worker, 'Fifteen chars.')
            await voice.wait_ready()
            before = len(voice.arrived)
            await voice.hold()
            assert len(voice.arrived) == before  # nothing waited for
            await voice.task
    asyncio.run(run())


def test_a_voice_slower_than_playback_waits_for_enough_to_play_without_a_gap():
    async def run():
        worker = Voice(0.8, 60, recent_rate=0.8)  # 1.2 s of audio, generated in 1.5 s
        voice = PreparedSpeech(worker, 'A reply of about one second.')  # 28 characters: taken as 1.9 s
        await voice.wait_ready()
        await voice.hold()
        started = time.monotonic()
        in_hand = sum(s for _, s in voice.arrived)
        await voice.task
        return voice, started, in_hand
    voice, started, in_hand = asyncio.run(run())
    assert in_hand >= 0.5  # waited for audio in hand, not just the first chunk
    assert gaps(voice, started) < 0.05  # and playback from there never ran dry
    first = voice.arrived[0][0]
    assert gaps(voice, first) > 0.1  # starting at the first chunk, as before, would have stuttered


def test_the_hold_never_lasts_beyond_its_limit(monkeypatch):
    monkeypatch.setattr(speech, 'HOLD_LIMIT', 0.2)

    async def run():
        worker = Voice(0.2, 200, recent_rate=0.2)  # hopelessly slow
        voice = PreparedSpeech(worker, 'A long reply that would need a very long wait before it could play.')
        await voice.wait_ready()
        first = voice.arrived[0][0]
        await voice.hold()
        waited = time.monotonic() - first
        voice.cancel()
        return waited
    assert 0.15 <= asyncio.run(run()) < 0.6


def test_the_voice_remembers_how_fast_it_has_lately_been_generated():
    async def run():
        worker = Voice(0.9, 60)  # 1.2 s of audio
        await PreparedSpeech(worker, 'First reply.').task
        first = worker.recent_rate
        worker.speed = 2.0
        await PreparedSpeech(worker, 'Second reply.').task
        return first, worker.recent_rate
    first, second = asyncio.run(run())
    assert 0.7 < first < 1.0 and first < second  # measured, then averaged with the faster second utterance


# The voice's resilience (PI F20): on 29 September a busy machine slowed the voice; an interruption restarted it after
# one second, and every later reply waited for a 12 GB reload that its own 30 s limit then cut off.

def fake_worker(tmp_path):
    from types import SimpleNamespace

    worker = speech.SpeechWorker('higgs', tmp_path)
    replies, writes, closed = asyncio.Queue(), [], []

    async def nothing():
        pass

    async def close():
        closed.append(True)
    worker.start, worker.close, worker._read = nothing, close, replies.get
    worker.process = SimpleNamespace(stdin=SimpleNamespace(write=writes.append, drain=nothing))
    return worker, replies, writes, closed


def test_an_interruption_that_takes_a_while_to_stop_does_not_restart_the_voice(tmp_path):
    async def run():
        worker, replies, writes, closed = fake_worker(tmp_path)

        async def consume(text):
            return [c async for c in worker.stream(text)]
        first = asyncio.create_task(consume('A long reply.'))
        await asyncio.sleep(0)
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        second = asyncio.create_task(consume('The next reply.'))
        await asyncio.sleep(1.3)  # the worker is still stopping after a second: once, this restarted it
        await replies.put({'done': True})  # the interrupted reply's end
        await replies.put({'chunk': 0, 'pcm': 'AAA=', 'rate': 24000})
        await replies.put({'done': True})
        return await second, closed, writes
    chunks, closed, writes = asyncio.run(run())
    assert len(chunks) == 1 and not closed
    assert len(writes) == 3  # the request, its cancel, and the next request only after the drain


def test_a_voice_that_does_not_stop_is_restarted(tmp_path, monkeypatch):
    monkeypatch.setattr(speech, 'DRAIN_SECONDS', 0.2)

    async def run():
        worker, replies, writes, closed = fake_worker(tmp_path)

        async def consume():
            return [c async for c in worker.stream('A reply.')]
        task = asyncio.create_task(consume())
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await worker.settled()
        return closed
    assert asyncio.run(run()) == [True]


def test_a_reply_that_gives_up_does_not_stop_the_voice_loading(tmp_path):
    async def run():
        worker = speech.SpeechWorker('higgs', tmp_path)
        loads, loaded = [], asyncio.Event()

        async def load():
            loads.append(True)
            await loaded.wait()
            worker.process = type('P', (), {'returncode': None})()
            worker.ready = True
        worker._start = load
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(worker.start(), 0.05)  # the reply's limit passes while the model loads
        loaded.set()
        await asyncio.wait_for(worker.start(), 1)  # the next reply finds it loaded
        return loads, worker.ready
    loads, ready = asyncio.run(run())
    assert loads == [True] and ready


def test_a_reply_whose_voice_is_late_is_given_as_text_and_the_interview_carries_on(tmp_path, monkeypatch):
    import json
    import uuid

    import httpx

    from services.sme_interviewer import continuous
    from services.sme_interviewer.continuous import Conversation
    from services.sme_interviewer.evidence import FixtureEvidence
    from services.sme_interviewer.interview import Interviews
    from services.sme_interviewer.process_interviewer import ProcessInterviewer
    from tests.test_sme_continuous_tibi import Engine
    from tests.test_sme_process_interviewer import FakeModels, reply

    monkeypatch.setattr(continuous, 'VOICE_WAIT', 0.2)

    class StuckVoice(Engine):
        engine = 'higgs'

        async def stream(self, text):
            await asyncio.Event().wait()  # never any audio
            yield {}

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
        c = Conversation(tmp_path, interviews, session, send, Engine(), Engine(), StuckVoice())
        c.paused = False
        await c.social_chat("I'm Bruno.", c.generation)
        saved = interviews.store.get(session['id'])
        await c.close()
        return events, saved
    events, saved = asyncio.run(run())
    kinds = [e['type'] for e in events]
    assert 'error' not in kinds and 'social_reply' in kinds
    assert kinds.index('social_reply') < kinds.index('quality_notice') < kinds.index('speech_done')  # shown, noticed, done
    notice = next(e for e in events if e['type'] == 'quality_notice')
    assert 'written only' in notice['message']
    assert [m['content'] for m in saved['social_transcript']][-2:] == ["I'm Bruno.", 'And your role?']
    assert json.dumps(saved)  # the reply was kept with the interview
