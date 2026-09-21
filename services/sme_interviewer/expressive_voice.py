"""Local Chatterbox stream; fixed reference identity, no per-utterance voice switch."""
import asyncio


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
        # Turbo accepts acoustic event tags, not general emotion instructions.
        for result in self.model.generate(text=text, stream=True, streaming_interval=0.4, max_tokens=700):
            yield result.audio, result.sample_rate
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
