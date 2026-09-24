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


def test_voice_decodes_sentences_once_without_incremental_seams():
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
    assert chunks == [([0.1, 0.2, 0.1], 24000)] * 2


def test_voice_rejects_sample_rate_change():
    rates = iter([24000, 22050])
    voice = ExpressiveVoice.__new__(ExpressiveVoice)
    voice.model = SimpleNamespace(generate=lambda **kwargs: iter([
        SimpleNamespace(audio=[0.1], sample_rate=next(rates))]))

    async def collect():
        return [chunk async for chunk in voice.create_stream('First. Second.')]

    with pytest.raises(ValueError, match='sample rate'):
        asyncio.run(collect())
