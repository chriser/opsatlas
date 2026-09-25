"""Resident, streamed Higgs speech with the accepted audition settings and fixed identity.

The installed Higgs v3 ``generate`` decodes every audio frame only after the last one,
so first audio waited for the whole utterance (3-12 s live). This module drives the
same model step by step and releases audio while it is still being generated:

* The fixed part of the prompt (reference transcript and reference audio codes) is
  prefilled once; each utterance only prefills its own text.
* Codec frames are decoded in chunks with left context and look-ahead. Measured on
  24 September 2026 against a whole-utterance decode: 54 dB SNR, max error 0.007
  (16 frames of context, 8 of look-ahead), so chunk joins are inaudible.
* Generation runs at about 1.36x real time on the M4 Max (34 frames/s for 25 frames/s
  of audio), so playback never overtakes synthesis once the first chunk is out.
* A cancellation check runs between frames; a barge-in stops computation at once
  instead of killing and reloading the 12 GB worker.
"""
import asyncio
import os

from .experience.catalog import REFERENCE_TEXT
from .experience.evaluation import load_evaluation_model
from .expressive_voice import speech_sentences

SAMPLES_PER_FRAME = 960  # 24 kHz codec at 25 frames per second
FIRST_FRAMES = 6         # 240 ms of audio in the first chunk
EARLY_FRAMES = 4         # small chunks while the playback buffer is still thin
CHUNK_FRAMES = 12        # 480 ms per chunk once generation is ahead of playback
EARLY_UNTIL = 36         # frames released before switching to full-size chunks
CONTEXT_FRAMES = 16      # left context re-decoded for continuity
LOOKAHEAD_FRAMES = 8     # frames decoded beyond the released region
SEED = 41
TEMPERATURE = 1.0
MAX_FRAMES = 1800


class HiggsVoice:
    def __init__(self, runtime, female=False):
        import mlx.core as mx

        mx.set_cache_limit(256 * 1024**2)
        self.model = load_evaluation_model('higgs', runtime / 'experience/audition2-higgs')
        self.model._codec.set_dtype(mx.float32)
        self.model.eval()
        if os.environ.get('SME_HIGGS_BITS') == '8':
            # Opt-in only: 8-bit backbone weights measured 1.45x faster (first audio 0.34-0.44 s vs
            # 0.59-0.62 s). The Human accepted the BF16 voice; A/B clips are in the evidence for review.
            import mlx.nn as nn

            for layer in self.model.backbone.layers:
                nn.quantize(layer, group_size=64, bits=8)
        mx.eval(self.model.parameters())
        speaker = 'p228' if female else 'p254'
        self.reference_codes = self.model.encode_reference_audio(
            str(runtime / f'experience/references/vctk/{speaker}_023_enhanced.wav'))
        self.references = self.model._normalize_references(
            ref_audio_codes=self.reference_codes, ref_text=REFERENCE_TEXT)
        self.prefix, self.prefix_tokens = self._prefill_prefix()

    def _prefill_prefix(self):
        """Prefill everything before the utterance text once; reuse its key/value state."""
        import mlx.core as mx
        from mlx_audio.lm.models.cache import make_prompt_cache

        builder = self.model._prompt_builder
        parts = builder.build_prompt('x', references=self.references)
        # The prompt ends with <|text|> <utterance tokens> <|audio|>; everything before
        # <|text|> is identical for every utterance with this voice.
        prefix_ids = parts.token_ids[:parts.token_ids.index(builder.text_id)]
        pieces, cursor = [], 0
        for start, codes in parts.audio_segments:
            pieces.append(self.model._text_embeddings(prefix_ids[cursor:start]))
            pieces.append(self.model._embed_audio_codes(codes))
            cursor = start + int(codes.shape[0])
        pieces.append(self.model._text_embeddings(prefix_ids[cursor:]))
        embeddings = mx.concatenate([p for p in pieces if p.shape[0] > 0], axis=0)[None]
        cache = make_prompt_cache(self.model)
        self.model.backbone(mx.zeros((1, embeddings.shape[1]), dtype=mx.int32), cache=cache,
                            input_embeddings=embeddings)
        # Trimmed state arrays: the first update reallocates, so the shared prefix is never mutated.
        state = [(c.keys[..., :c.offset, :], c.values[..., :c.offset, :]) for c in cache]
        mx.eval([array for pair in state for array in pair])
        return state, len(prefix_ids)

    def _cache(self):
        from mlx_audio.lm.models.cache import make_prompt_cache

        cache = make_prompt_cache(self.model)
        for layer, (keys, values) in zip(cache, self.prefix):
            layer.keys, layer.values, layer.offset = keys, values, keys.shape[2]
        return cache

    def chunks(self, text, cancelled=lambda: False):
        """Yield float32 audio as it is generated; each piece covers frames no later decode changes."""
        import mlx.core as mx
        import numpy as np
        from mlx_audio.tts.models.higgs_audio_v3.generation import HiggsSamplerState, reverse_delay_pattern, step

        model, config = self.model, self.model.config
        delay = config.audio_num_codebooks - 1
        mx.random.seed(SEED)
        cache = self._cache()
        builder = model._prompt_builder
        suffix = model._text_embeddings([builder.text_id, *builder.encode_text(text), builder.audio_id])[None]
        hidden = model.backbone(mx.zeros((1, suffix.shape[1]), dtype=mx.int32), cache=cache, input_embeddings=suffix)
        last = hidden[:, -1, :]
        state = HiggsSamplerState(num_codebooks=config.audio_num_codebooks)
        rows, emitted, target = [], 0, FIRST_FRAMES

        def release(end, final):
            raw = reverse_delay_pattern(mx.stack(rows, axis=0).astype(mx.int32))
            low, high, first, last = decode_window(emitted, end, int(raw.shape[0]), final)
            audio = np.asarray(model._codec.decode(raw[low:high]).astype(mx.float32).reshape(-1), dtype=np.float32)
            piece = audio[first:last]
            if not len(piece) or not np.isfinite(piece).all():
                raise ValueError('Invalid Higgs waveform')
            return piece

        for _ in range(MAX_FRAMES):
            if cancelled():
                return
            codes = step(model._audio_logits(last)[0], state, temperature=TEMPERATURE, top_p=None, top_k=None,
                         boc_id=config.audio_boc_token_id, eoc_id=config.audio_eoc_token_id)
            rows.append(codes)
            if state.generation_done:
                break
            hidden = model.backbone(mx.zeros((1, 1), dtype=mx.int32), cache=cache,
                                    input_embeddings=model._embed_audio_codes(codes)[None])
            last = hidden[:, -1, :]
            settled = len(rows) - delay - LOOKAHEAD_FRAMES
            if settled >= target:
                yield release(settled, False)
                emitted, target = settled, next_target(settled)
        if len(rows) > delay and len(rows) - delay > emitted:
            yield release(len(rows) - delay, True)

    async def create_stream(self, text, cancelled=lambda: False, **kwargs):
        for group in delivery_groups(text):
            for audio in self.chunks(group.replace('. ', '. <|prosody:pause|> '), cancelled):
                yield audio, self.model.sample_rate
                await asyncio.sleep(0)
            if cancelled():
                return


def next_target(emitted):
    """Small early chunks keep a thin playback buffer fed; larger ones once generation is ahead."""
    return emitted + (EARLY_FRAMES if emitted < EARLY_UNTIL else CHUNK_FRAMES)


def decode_window(emitted, end, total, final):
    """Frames to decode (with context and look-ahead) and the sample range to release."""
    low = max(0, emitted - CONTEXT_FRAMES)
    high = total if final else min(total, end + LOOKAHEAD_FRAMES)
    return low, high, (emitted - low) * SAMPLES_PER_FRAME, (end - low) * SAMPLES_PER_FRAME


def delivery_groups(text):
    """Bound one generation's length; streaming makes the first group's size irrelevant to latency."""
    if len(text) <= 320:
        return [text]
    groups, current = [], []
    for sentence in speech_sentences(text):
        if current and len(' '.join([*current, sentence])) > 320:
            groups.append(' '.join(current))
            current = []
        current.append(sentence)
    if current:
        groups.append(' '.join(current))
    return groups
