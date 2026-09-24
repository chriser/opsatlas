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


def speech_phrases(text):
    """Pause at punctuation, not numeric commas; keep short list items together."""
    sentences = list(speech_sentences(text))
    for index, sentence in enumerate(sentences):
        start = 0
        for boundary in re.finditer(r'[,;:]\s+', sentence):
            # Short lists remain one phrase, avoiding a choppy restart per noun.
            if len(sentence[start:boundary.start()].split()) < 5:
                continue
            yield sentence[start:boundary.start() + 1].strip(), 0.20
            start = boundary.end()
        if sentence[start:].strip():
            yield sentence[start:].strip(), 0.32 if index < len(sentences) - 1 else 0.0


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
        import numpy as np

        from .voice_delivery import settle_phrase

        rate = None
        for sentence, pause in speech_phrases(text):
            for result in self.model.generate(text=sentence, stream=False, max_tokens=700, temperature=0.6):
                if rate is None:
                    rate = result.sample_rate
                if result.sample_rate != rate:
                    raise ValueError("Voice sample rate changed within an utterance")
                if len(result.audio):
                    yield settle_phrase(result.audio, rate), rate
                await asyncio.sleep(0)
            if rate and pause:
                yield np.zeros(round(rate * pause), dtype=np.float32), rate


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
