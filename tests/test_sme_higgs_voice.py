import asyncio

import numpy as np

from services.sme_interviewer.continuous import social_voice_engine
from services.sme_interviewer.higgs_voice import (
    CHUNK_FRAMES,
    CONTEXT_FRAMES,
    EARLY_FRAMES,
    EARLY_UNTIL,
    FIRST_FRAMES,
    LOOKAHEAD_FRAMES,
    SAMPLES_PER_FRAME,
    HiggsVoice,
    decode_window,
    delivery_groups,
    next_target,
)


def test_sales_migrates_old_engine_and_allows_selected_alternative(monkeypatch):
    monkeypatch.setenv('SME_SALES_VOICE', 'higgs')
    assert social_voice_engine({'social_engine': 'chatterbox'}, {'social_voice': 'chatterbox'}) == 'higgs'
    assert social_voice_engine({}, {}) == 'higgs'
    assert social_voice_engine({}, {'social_voice': 'higgs_female'}) == 'higgs_female'
    assert social_voice_engine({'social_engine': 'higgs_female'}, {}) == 'higgs_female'
    monkeypatch.delenv('SME_SALES_VOICE')
    assert social_voice_engine({'social_engine': 'pocket'}, {}) == 'pocket'


def test_first_chunk_is_small_then_grows_once_generation_is_ahead():
    assert FIRST_FRAMES <= 6 and EARLY_FRAMES <= FIRST_FRAMES
    assert next_target(FIRST_FRAMES) == FIRST_FRAMES + EARLY_FRAMES
    assert next_target(EARLY_UNTIL) == EARLY_UNTIL + CHUNK_FRAMES


def test_decode_window_keeps_context_and_lookahead_and_releases_only_settled_frames():
    low, high, first, last = decode_window(emitted=20, end=24, total=40, final=False)
    assert low == 20 - CONTEXT_FRAMES and high == 24 + LOOKAHEAD_FRAMES
    assert (first, last) == (CONTEXT_FRAMES * SAMPLES_PER_FRAME, (CONTEXT_FRAMES + 4) * SAMPLES_PER_FRAME)
    # The first chunk has no context; the final chunk decodes to the end with no look-ahead.
    assert decode_window(0, 6, 20, False)[:3] == (0, 6 + LOOKAHEAD_FRAMES, 0)
    assert decode_window(30, 40, 40, True)[:2] == (30 - CONTEXT_FRAMES, 40)


def test_stream_adds_pause_cue_per_group_and_honours_cancellation():
    voice = HiggsVoice.__new__(HiggsVoice)
    voice.model = type('M', (), {'sample_rate': 24000})()
    seen = []

    def chunks(text, cancelled):
        seen.append(text)
        for _ in range(3):
            if cancelled():
                return
            yield np.ones(SAMPLES_PER_FRAME, dtype=np.float32) * .1

    voice.chunks = chunks

    async def run(text, cancelled=lambda: False):
        return [c async for c in voice.create_stream(text, cancelled=cancelled, speed=.5, style='amused')]
    assert len(asyncio.run(run('Hi, Chris. How are you?'))) == 3
    assert seen[-1] == 'Hi, Chris. <|prosody:pause|> How are you?'
    stop = iter([False, True, True, True])
    assert len(asyncio.run(run('One. Two.', lambda: next(stop)))) == 1


def test_delivery_groups_preserve_words_and_sentence_boundaries():
    text = 'Hi, Chris. Dr. Jones can help explain how this platform works for your team. ' + (
        'It brings approved information together so people can find answers and understand processes.')
    assert delivery_groups(text) == [text]
    long_text = ' '.join([text] * 3)
    parts = delivery_groups(long_text)
    assert len(parts) > 1 and ' '.join(parts) == long_text
    assert all(len(p) <= 320 for p in parts)
