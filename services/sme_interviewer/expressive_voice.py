"""Local Chatterbox stream; fixed reference identity, no per-utterance voice switch."""
import asyncio
import re


def speech_sentences(text):
    """Keep sentence wording intact; avoid splitting common title abbreviations."""
    start = 0
    for boundary in re.finditer(r'[.!?][\"\u201d\u2019]?\s+', text):
        end = boundary.end()
        prefix = text[start:boundary.start() + 1]
        if re.search(r'\b(?:Mr|Mrs|Ms|Dr|Prof|St|e\.g|i\.e)\.$', prefix, re.I):
            continue
        yield text[start:end].strip()
        start = end
    if text[start:].strip():
        yield text[start:].strip()


class ExpressiveVoice:
    def __init__(self, runtime):
        import mlx.core as mx
        from mlx_audio.tts.utils import load_model
        self.mx = mx
        mx.set_cache_limit(256 * 1024**2)
        self.model = load_model(str(runtime / 'experience/chatterbox'))
        weights = mx.load(str(runtime / 'experience/s3tokenizer/model.safetensors'))
        if hasattr(self.model._s3tokenizer, 'sanitize'):
            weights = self.model._s3tokenizer.sanitize(weights)
        self.model._s3tokenizer.load_weights(list(weights.items()))
        self.model.eval()
        mx.eval(self.model.parameters())
        self.model.prepare_conditionals(str(runtime / 'experience/references/vctk/p254_023_enhanced.wav'))

    async def create_stream(self, text, **kwargs):
        # Decode each complete sentence once. Incremental prefix decoding can
        # change phase/timbre at joins; smoothing a join cannot restore prosody.
        # The worker still packetises these buffers for bounded playback/ACKs.
        rate = None
        for sentence in speech_sentences(text):
            for result in self.model.generate(text=sentence, stream=False, max_tokens=700):
                if rate is None:
                    rate = result.sample_rate
                if result.sample_rate != rate:
                    raise ValueError("Voice sample rate changed within an utterance")
                if len(result.audio):
                    yield result.audio, rate
                await asyncio.sleep(0)


class CustomVoice:
    def __init__(self, runtime):
        import mlx.core as mx
        from mlx_audio.tts.utils import load_model
        mx.set_cache_limit(256 * 1024**2)
        self.model = load_model(str(runtime / 'experience/qwen-custom'))
        self.model.eval()
        mx.eval(self.model.parameters())

    async def create_stream(self, text, style='warm', **kwargs):
        from .experience.social_audition import DIRECTIONS
        direction = DIRECTIONS.get(style, 'Speak naturally and conversationally, with clear, unhurried phrasing.')
        for result in self.model.generate_custom_voice(text=text, speaker='Aiden', language='English',
                instruct='Use clear British English. ' + direction, stream=True,
                streaming_interval=0.4, max_tokens=700, temperature=0.7):
            yield result.audio, result.sample_rate
            await asyncio.sleep(0)
