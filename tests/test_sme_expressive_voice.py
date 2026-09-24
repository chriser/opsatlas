import asyncio
from types import SimpleNamespace

import pytest

from services.sme_interviewer.expressive_voice import ExpressiveVoice, speech_sentences


def test_sentence_boundaries_preserve_amounts_titles_and_wording():
    text = 'Dr. Smith approved £15,000. Finance confirmed 1.5 days. "Ready?" Yes!'
    sentences = list(speech_sentences(text))
    assert sentences == ['Dr. Smith approved £15,000.', 'Finance confirmed 1.5 days.', '"Ready?"', 'Yes!']
    assert ' '.join(sentences) == text
    assert list(speech_sentences('   ')) == []


def test_voice_decodes_sentences_once_without_incremental_seams(monkeypatch):
    monkeypatch.setattr("services.sme_interviewer.voice_delivery.settle_phrase", lambda audio, rate: audio)
    calls = []

    def generate(**kwargs):
        calls.append(kwargs)
        yield SimpleNamespace(audio=[0.1, 0.2, 0.1], sample_rate=24000)

    voice = ExpressiveVoice.__new__(ExpressiveVoice)
    voice.model = SimpleNamespace(generate=generate)

    async def collect():
        return [chunk async for chunk in voice.create_stream('First sentence. Second sentence.')]

    chunks = asyncio.run(collect())
    assert [call['text'] for call in calls] == ['First sentence.', 'Second sentence.']
    assert all(call['stream'] is False for call in calls)
    assert chunks[0] == chunks[2] == ([0.1, 0.2, 0.1], 24000)
    assert len(chunks[1][0]) == round(24000 * 0.32)


def test_voice_rejects_sample_rate_change(monkeypatch):
    monkeypatch.setattr("services.sme_interviewer.voice_delivery.settle_phrase", lambda audio, rate: audio)
    rates = iter([24000, 22050])
    voice = ExpressiveVoice.__new__(ExpressiveVoice)
    voice.model = SimpleNamespace(generate=lambda **kwargs: iter([
        SimpleNamespace(audio=[0.1], sample_rate=next(rates))]))

    async def collect():
        return [chunk async for chunk in voice.create_stream('First. Second.')]

    with pytest.raises(ValueError, match='sample rate'):
        asyncio.run(collect())


def test_phrase_pauses_do_not_split_currency_or_short_lists():
    from services.sme_interviewer.expressive_voice import speech_phrases
    phrases = list(speech_phrases('The supplier limit is £15,000, and the manager approves it. People, suppliers and approvals.'))
    assert phrases[0] == ('The supplier limit is £15,000,', 0.20)
    assert phrases[1] == ('and the manager approves it.', 0.32)
    assert phrases[2] == ('People, suppliers and approvals.', 0.0)


def test_delivery_preserves_pitch_caps_loudness_and_has_clean_edges():
    import shutil

    import numpy as np

    from services.sme_interviewer.voice_delivery import settle_phrase
    if not shutil.which('ffmpeg'):
        pytest.skip('Local ffmpeg required for the real delivery filter')
    rate = 24000
    source = (0.7 * np.sin(2 * np.pi * 440 * np.arange(rate * 2) / rate)).astype(np.float32)
    result = settle_phrase(source, rate)
    assert 2.08 < len(result) / rate < 2.15
    dominant = np.argmax(np.abs(np.fft.rfft(result))) * rate / len(result)
    assert abs(dominant - 440) < 2
    assert np.max(np.abs(result)) < 0.2
    assert result[0] == result[-1] == 0
