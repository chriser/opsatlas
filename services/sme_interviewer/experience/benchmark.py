"""Reproducible native-delivery audition; synthetic text only, no live service changes."""
import argparse
import asyncio
import hashlib
import json
import os
import time
from pathlib import Path

from .catalog import ROOT, RUNTIME

DIRECTORY = RUNTIME / 'benchmark-2026-09-24'
_DATA = json.loads((Path(__file__).parent / 'benchmark-cases.json').read_text())
CASES = _DATA['CASES']
CANDIDATES = {
    'turbo': 'Current Chatterbox Turbo 4-bit · British reference',
    'v3': 'Chatterbox Multilingual V3 · same British reference',
    'qwen4': 'Qwen CustomVoice 1.7B 4-bit · Aiden, directed',
    'qwen8': 'Qwen CustomVoice 1.7B 8-bit · Aiden, directed',
    'vibe': 'VibeVoice Realtime 0.5B FP16 · Frank (accent to assess)',
}
DIRECTIONS = _DATA['DIRECTIONS']


async def generate(candidate):
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1')
    import mlx.core as mx
    import numpy as np
    import soundfile as sf
    from mlx_audio.tts.utils import load_model

    DIRECTORY.mkdir(parents=True, exist_ok=True)
    mx.set_cache_limit(256 * 1024**2)
    load_start = time.perf_counter()
    if candidate == 'turbo':
        from ..expressive_voice import ExpressiveVoice
        model = ExpressiveVoice(ROOT / '.runtime')
    elif candidate == 'v3':
        from unittest.mock import patch
        # The library's hook otherwise searches the global HF cache. Use the already pinned local tokenizer.
        def local_tokenizer(repo_id, **kwargs):
            if repo_id != 'mlx-community/S3TokenizerV2':
                raise ValueError('Unexpected dependency')
            return str(RUNTIME / 's3tokenizer')
        with patch('huggingface_hub.snapshot_download', local_tokenizer):
            model = load_model(str(RUNTIME / 'chatterbox-v3'))
        model.eval()
        mx.eval(model.parameters())
        conds = model.prepare_conditionals(str(RUNTIME / 'references/vctk/p254_023_enhanced.wav'), 24000, exaggeration=0.35)
    elif candidate == 'vibe':
        from unittest.mock import patch

        from transformers import AutoTokenizer
        tokenizer_loader = AutoTokenizer.from_pretrained
        def local_vibe_tokenizer(repo_id, **kwargs):
            if repo_id != 'Qwen/Qwen2.5-0.5B':
                raise ValueError('Unexpected tokenizer dependency')
            return tokenizer_loader(str(RUNTIME / 'vibe-tokenizer'), local_files_only=True)
        with patch('transformers.AutoTokenizer.from_pretrained', local_vibe_tokenizer):
            model = load_model(str(RUNTIME / 'vibevoice'))
        model.eval()
        mx.eval(model.parameters())
    else:
        model = load_model(str(RUNTIME / ('qwen-custom' if candidate == 'qwen4' else 'qwen-custom-8bit')))
        model.eval()
        mx.eval(model.parameters())
    load_ms = (time.perf_counter() - load_start) * 1000
    rows = []
    for case in CASES:
        mx.random.seed(41)
        start = time.perf_counter()
        chunks = []
        first = None
        rate = 24000
        def consume(audio, sr):
            nonlocal first, rate
            samples = np.asarray(audio, dtype=np.float32).reshape(-1)
            if first is None:
                first = (time.perf_counter() - start) * 1000
            rate = sr
            chunks.append(samples)
        if candidate == 'turbo':
            async for audio, sr in model.create_stream(case['text']):
                consume(audio, sr)
        else:
            if candidate == 'v3':
                iterator = model.generate(text=case['text'], conds=conds, lang_code='en', exaggeration=0.35,
                                          cfg_weight=0.5, temperature=0.7, stream=False, max_tokens=700, verbose=False)
            elif candidate == 'vibe':
                iterator = model.generate(text=case['text'], voice='en-Frank_man', stream=False,
                                          max_tokens=700, verbose=False)
            else:
                iterator = model.generate_custom_voice(text=case['text'], speaker='Aiden', language='English',
                    instruct=DIRECTIONS[case['style']], stream=False, max_tokens=700, temperature=0.7)
            for result in iterator:
                consume(result.audio, result.sample_rate)
        elapsed = (time.perf_counter() - start) * 1000
        audio = np.concatenate(chunks)
        if not np.isfinite(audio).all() or not len(audio):
            raise ValueError('Invalid audio')
        path = DIRECTORY / f'{candidate}-{case["id"]}.wav'
        # No tempo, gain, silence, concatenation-overlap or loudness post-processing.
        sf.write(path, audio, rate, subtype='PCM_16')
        rows.append({'candidate': candidate, 'case': case['id'], 'file': path.name,
            'first_output_ms': round(first, 1), 'total_ms': round(elapsed, 1), 'audio_seconds': round(len(audio) / rate, 3),
            'rtf': round(elapsed / 1000 / (len(audio) / rate), 3), 'cold_first_generation': not rows,
            'peak': float(np.max(np.abs(audio))), 'clipped_samples': int(np.sum(np.abs(audio) >= 1)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'load_ms': round(load_ms, 1),
            'peak_memory_bytes': mx.get_peak_memory(), 'seed': 41})
        (DIRECTORY / f'{candidate}.json').write_text(json.dumps(rows, indent=2)+'\n')
        print(json.dumps(rows[-1]), flush=True)
    return rows


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('candidate', choices=CANDIDATES)
    asyncio.run(generate(parser.parse_args().candidate))
