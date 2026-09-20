"""Local Metal inference with the existing Kokoro phonemizer, voices and pause rules.

The small adapter overrides the pinned kokoro-onnx inference boundary only. It
retains that package's batching, trimming, pronunciation and stream protocol.
"""

import json
from pathlib import Path

import mlx.core as mx
import numpy as np
from kokoro_onnx import Kokoro
from kokoro_onnx.tokenizer import Tokenizer
from mlx_audio.tts.models.kokoro.kokoro import Model, ModelConfig

from .provision import sha256


class MetalKokoro(Kokoro):
    def __init__(self, runtime):
        # MLX otherwise defaults its free-buffer cache to a large fraction of
        # unified memory. A small speech model must not evict the planner.
        mx.set_cache_limit(256 * 1024**2)
        mx.set_memory_limit(2 * 1024**3)  # Allocator guideline, not a hard RAM cap.
        root = Path(__file__).parent
        manifest = json.loads((root / 'model-lock.json').read_text())['files']
        for name in ('models/kokoro-mlx/config.json', 'models/kokoro-mlx/kokoro-v1_0.safetensors', 'models/voices-v1.0.bin'):
            if sha256(runtime / name) != manifest[name]['sha256']:
                raise ValueError('Speech artifact checksum mismatch: ' + name)
        config = json.loads((runtime / 'models/kokoro-mlx/config.json').read_text())
        config.pop('model_type', None)
        self.model = Model(ModelConfig.from_dict(config))
        weights = mx.load(str(runtime / 'models/kokoro-mlx/kokoro-v1_0.safetensors'))
        self.model.load_weights(list(self.model.sanitize(weights).items()))
        self.model.eval()
        mx.eval(self.model.parameters())
        self.tokenizer = Tokenizer(vocab=config['vocab'])
        self.phonemes = {value: key for key, value in config['vocab'].items()}
        self.voices = np.load(runtime / 'models/voices-v1.0.bin')
        self.has_timings = False

    def _infer(self, tokens, style, speed):
        phonemes = ''.join(self.phonemes[token] for token in tokens)
        audio = self.model(phonemes, mx.array(style), speed=speed)
        mx.eval(audio)
        result = np.asarray(audio).reshape(-1)
        if not len(result) or not np.isfinite(result).all():
            raise ValueError('Invalid local GPU speech output')
        return result, None

    async def create_stream(self, text, voice, speed=1.0, lang='en-gb'):
        # This already runs in a dedicated speech process. Keep Metal work on
        # its warmed thread instead of creating a new executor for every turn.
        voice, _, batches = self._prepare(text, voice, speed, lang, False, 0.25, 0.1)
        for phonemes, pause in batches:
            audio, _ = self._create_batch(phonemes, voice, speed, True, pause)
            yield audio, 24000

    def memory(self):
        return {'gpu_active_bytes': mx.get_active_memory(), 'gpu_cache_bytes': mx.get_cache_memory(),
                'gpu_peak_bytes': mx.get_peak_memory(), 'gpu_cache_limit_bytes': 256 * 1024**2}
