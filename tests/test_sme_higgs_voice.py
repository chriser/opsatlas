import asyncio
from types import SimpleNamespace

import numpy as np
import pytest

from services.sme_interviewer.continuous import social_voice_engine
from services.sme_interviewer.higgs_voice import HiggsVoice


def test_sales_migrates_old_engine_and_allows_selected_alternative(monkeypatch):
    monkeypatch.setenv('SME_SALES_VOICE', 'higgs')
    assert social_voice_engine({'social_engine': 'chatterbox'}, {'social_voice': 'chatterbox'}) == 'higgs'
    assert social_voice_engine({}, {}) == 'higgs'
    assert social_voice_engine({}, {'social_voice': 'higgs_female'}) == 'higgs_female'
    assert social_voice_engine({'social_engine': 'higgs_female'}, {}) == 'higgs_female'
    monkeypatch.delenv('SME_SALES_VOICE')
    assert social_voice_engine({'social_engine': 'pocket'}, {}) == 'pocket'


def test_higgs_preserves_one_reference_and_whole_response():
    voice = HiggsVoice.__new__(HiggsVoice)
    voice.reference_codes = object()
    calls = []

    def generate(**kwargs):
        calls.append(kwargs)
        yield SimpleNamespace(audio=np.ones(240, dtype=np.float32)*.1, sample_rate=24000)

    voice.model = SimpleNamespace(generate=generate)

    async def run():
        for text in ('Hi, Chris. How are you?', 'Let me explain. Ask me anything.'):
            assert len([c async for c in voice.create_stream(text, speed=.5, style='amused')]) == 1
    asyncio.run(run())
    assert all(c['ref_audio_codes'] is voice.reference_codes for c in calls)
    assert calls[0]['text'] == 'Hi, Chris. <|prosody:pause|> How are you?'
    assert all(c['seed'] == 41 and c['temperature'] == 1 and not c['stream'] for c in calls)
    assert all('speed' not in c and 'style' not in c for c in calls)


def test_higgs_rejects_invalid_audio():
    voice = HiggsVoice.__new__(HiggsVoice)
    voice.reference_codes = object()
    voice.model = SimpleNamespace(generate=lambda **k: iter([SimpleNamespace(audio=np.array([np.nan]), sample_rate=24000)]))

    async def run():
        return [c async for c in voice.create_stream('Hi')]
    with pytest.raises(ValueError, match='Invalid Higgs'):
        asyncio.run(run())


def test_delivery_groups_preserve_words_and_sentence_boundaries():
    from services.sme_interviewer.higgs_voice import delivery_groups
    text = 'Hi, Chris. Dr. Jones can help explain how this platform works for your team. ' + (
        'It brings approved information together so people can find answers and understand processes.')
    parts = delivery_groups(text)
    assert len(parts) == 1  # Short accepted delivery remains whole.
    long_text = text + ' Would you like a practical example of that?'
    parts = delivery_groups(long_text)
    assert len(parts) == 2 and ' '.join(parts) == long_text
    assert 'Dr. Jones' in parts[0] and len(parts[0]) >= 55
