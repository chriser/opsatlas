"""Resident Higgs speech with the accepted audition settings and fixed identity."""
import asyncio

from .experience.catalog import REFERENCE_TEXT
from .experience.evaluation import load_evaluation_model
from .expressive_voice import speech_sentences


class HiggsVoice:
    def __init__(self, runtime, female=False):
        import mlx.core as mx

        mx.set_cache_limit(256 * 1024**2)
        self.model = load_evaluation_model('higgs', runtime / 'experience/audition2-higgs')
        self.model._codec.set_dtype(mx.float32)
        self.model.eval()
        mx.eval(self.model.parameters())
        speaker = 'p228' if female else 'p254'
        self.reference_codes = self.model.encode_reference_audio(
            str(runtime / f'experience/references/vctk/{speaker}_023_enhanced.wav'))

    async def create_stream(self, text, **kwargs):
        import numpy as np

        # Decode complete sentence groups, never overlapping waveform prefixes.
        # Short utterances keep their accepted whole-utterance delivery.
        for group in delivery_groups(text):
            for result in self.model.generate(
                    text=group.replace('. ', '. <|prosody:pause|> '),
                    ref_audio_codes=self.reference_codes, ref_text=REFERENCE_TEXT,
                    seed=41, temperature=1.0, max_tokens=1800, stream=False,
                    fade_in_ms=0, fade_out_ms=0):
                audio = np.asarray(result.audio, dtype=np.float32).reshape(-1)
                if not len(audio) or not np.isfinite(audio).all():
                    raise ValueError('Invalid Higgs waveform')
                yield audio, result.sample_rate
                await asyncio.sleep(0)


def delivery_groups(text):
    """At most two complete-sentence groups; keep tiny greetings with their context."""
    if len(text) <= 180:
        return [text]
    sentences = list(speech_sentences(text))
    first = []
    for index, sentence in enumerate(sentences):
        first.append(sentence)
        if len(' '.join(first)) >= 55 and index < len(sentences)-1:
            return [' '.join(first), ' '.join(sentences[index+1:])]
    return [text]
