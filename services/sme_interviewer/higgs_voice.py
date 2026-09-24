"""Resident Higgs speech with the accepted audition settings and fixed identity."""
import asyncio

from .experience.catalog import REFERENCE_TEXT
from .experience.evaluation import load_evaluation_model


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

        # Decode the whole response once, preserving cross-sentence prosody.
        # The worker packetises the finished waveform; this is not native streaming.
        for result in self.model.generate(
                text=text.replace('. ', '. <|prosody:pause|> '),
                ref_audio_codes=self.reference_codes, ref_text=REFERENCE_TEXT,
                seed=41, temperature=1.0, max_tokens=1800, stream=False,
                fade_in_ms=0, fade_out_ms=0):
            audio = np.asarray(result.audio, dtype=np.float32).reshape(-1)
            if not len(audio) or not np.isfinite(audio).all():
                raise ValueError('Invalid Higgs waveform')
            yield audio, result.sample_rate
            await asyncio.sleep(0)
