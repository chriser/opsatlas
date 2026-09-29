"""The stutter guard (PI F16): Tibi starts speaking only when playback will not overtake the voice being generated."""
import asyncio
import base64
import time

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
