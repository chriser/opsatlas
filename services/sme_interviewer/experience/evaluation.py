"""Second-round, local-only model audition. Not a live Tibi backend."""
import argparse
import hashlib
import json
import os
import time

from .benchmark import CASES as ORIGINAL_CASES
from .catalog import REFERENCE_TEXT, RUNTIME

DIRECTORY = RUNTIME / 'evaluation-2026-09-24'
CANDIDATES = {
    'breeze-directed': 'Breeze TTS 2 BF16 · British reference, restrained direction',
    'breeze-designed': 'Breeze TTS 2 BF16 · designed British female voice',
    'fish': 'Fish S2 Pro BF16 · British reference',
    'higgs': 'Higgs TTS 3 · BF16 language model, FP32 codec, British reference',
}
CASES = [dict(c, seed=41) for c in ORIGINAL_CASES if c['id'] in
         ('greeting', 'original-intro', 'repair', 'numbers')]
DIRECTION = ('Speak in clear British English, as a kind colleague talking to one person. '
             'Warm but understated. Give complete sentences a natural pause and finish statements decisively. '
             'Do not rush or sound theatrical.')
MODEL_REVISIONS = {
    'breeze': ('mlx-community/Breeze-TTS-2-mlx', '3c8829fb7fd335818f085cd2ef49b4100c0e46c8'),
    'fish': ('mlx-community/fish-audio-s2-pro-bf16', 'eccd57bf5c1ebc13cb2f993df867f4e49931a36a'),
    'higgs': ('bosonai/higgs-tts-3-4b', '239f63fb7b02b1aa085f98d9efae5e35cc5523e8'),
}


def load_evaluation_model(key, model_path):
    from mlx_audio.tts.utils import load_model

    if key != 'higgs':
        return load_model(str(model_path))
    from contextlib import contextmanager
    from types import SimpleNamespace
    from unittest.mock import patch

    import mlx.core as mx
    from safetensors import safe_open

    @contextmanager
    def native_bf16(path, framework, **kwargs):
        # safetensors' MLX bridge currently detours through NumPy, which rejects
        # BF16. MLX reads the original dtype directly, including the bundled codec.
        if framework == 'mlx':
            weights = mx.load(str(path))
            yield SimpleNamespace(keys=weights.keys, get_tensor=weights.__getitem__)
        else:
            with safe_open(path, framework=framework, **kwargs) as file:
                yield file

    with patch('safetensors.safe_open', native_bf16):
        return load_model(str(model_path), model_type='higgs_audio_v3')


def provision(candidate):
    from huggingface_hub import snapshot_download

    from .provision import SOURCES

    repo, revision = MODEL_REVISIONS[candidate]
    snapshot_download(repo, revision=revision, local_dir=RUNTIME / ('audition2-'+candidate),
                      allow_patterns=['*.safetensors', '*.json', '*.jinja', 'LICENSE*', 'NOTICE*', 'README.md', 'PROMPTING.md'])
    _, reference_repo, reference_revision, _ = next(s for s in SOURCES if s[0] == 'references')
    snapshot_download(reference_repo, revision=reference_revision, local_dir=RUNTIME / 'references',
                      allow_patterns=['vctk/p254_023_enhanced.wav', 'README.md'])


def generate(candidate, smoke=False, resume=False):
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1')
    import mlx.core as mx
    import numpy as np
    import soundfile as sf
    from mlx_audio.utils import load_audio

    key = candidate.split('-')[0]
    model_path = RUNTIME / ('audition2-'+key)
    reference = RUNTIME / 'references/vctk/p254_023_enhanced.wav'
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    mx.set_cache_limit(256 * 1024**2)
    load_start = time.perf_counter()
    model = load_evaluation_model(key, model_path)
    if key == 'higgs':
        # Keep waveform computation out of BF16's coarse amplitude grid.
        # This changes codec arithmetic, not waveform speed or post-processing.
        model._codec.set_dtype(mx.float32)
    model.eval()
    mx.eval(model.parameters())
    load_ms = (time.perf_counter()-load_start)*1000
    ref = load_audio(str(reference), sample_rate=model.sample_rate) if key == 'fish' else str(reference)
    result_file = DIRECTORY / f'{candidate}.json'
    rows = json.loads(result_file.read_text()) if resume and result_file.exists() else []
    generated_this_process = 0
    for case in CASES[:1] if smoke else CASES:
        if resume and any(r['case'] == case['id'] and (DIRECTORY / r['file']).exists() for r in rows):
            continue
        mx.random.seed(case['seed'])
        settings = {'text': case['text'], 'stream': False, 'max_tokens': 1000}
        if key == 'breeze':
            settings.update(instruct=DIRECTION, cfg_scale=4.0, seed=case['seed'], split_pattern=None)
            if candidate == 'breeze-directed':
                settings.update(ref_audio=ref, ref_text=REFERENCE_TEXT)
            else:
                settings['instruct'] = 'An adult British woman with a clear, warm, medium-pitched voice. '+DIRECTION
        elif key == 'fish':
            settings.update(ref_audio=ref, ref_text=REFERENCE_TEXT, instruct=DIRECTION, speed=1.0, chunk_length=1000)
        else:
            settings.update(ref_audio=ref, ref_text=REFERENCE_TEXT, seed=case['seed'], fade_in_ms=0, fade_out_ms=0)
            settings['text'] = case['text'].replace('. ', '. <|prosody:pause|> ')
            if case['style'] in ('warm', 'gentle'):
                settings['text'] = '<|emotion:contentment|>'+settings['text']
        start = time.perf_counter()
        first = None
        chunks = []
        for result in model.generate(**settings):
            samples = np.asarray(result.audio, dtype=np.float32).reshape(-1)
            if first is None:
                first = (time.perf_counter()-start)*1000
            chunks.append(samples)
            rate = result.sample_rate
        elapsed = (time.perf_counter()-start)*1000
        audio = np.concatenate(chunks)
        if not len(audio) or not np.isfinite(audio).all():
            raise ValueError('Invalid audio')
        path = DIRECTORY / f'{candidate}-{case["id"]}.wav'
        sf.write(path, audio, rate, subtype='PCM_16')
        row = {'candidate': candidate, 'case': case['id'], 'file': path.name, 'seed': case['seed'],
               'codec_compute_dtype': 'float32' if key == 'higgs' else 'adapter default',
               'output_dtype': str(result.audio.dtype),
               'first_output_ms': round(first, 1), 'total_ms': round(elapsed, 1),
               'audio_seconds': round(len(audio)/rate, 3), 'rtf': round(elapsed/1000/(len(audio)/rate), 3),
               'load_ms': round(load_ms, 1), 'cold_first_generation': generated_this_process == 0,
               'peak_memory_bytes': mx.get_peak_memory(), 'peak': float(np.max(np.abs(audio))),
               'clipped_samples': int(np.sum(np.abs(audio)>=1)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
               'model_repo': MODEL_REVISIONS[key][0], 'model_revision': MODEL_REVISIONS[key][1],
               'reference_sha256': hashlib.sha256(reference.read_bytes()).hexdigest() if candidate != 'breeze-designed' else None,
               'settings': {k: v for k, v in settings.items() if k != 'ref_audio'}}
        rows.append(row)
        generated_this_process += 1
        # Publish complete JSON atomically while the audition server can read it.
        temp = DIRECTORY / f'{candidate}.json.tmp'
        temp.write_text(json.dumps(rows, indent=2)+'\n')
        temp.replace(DIRECTORY / f'{candidate}.json')
        print(json.dumps(row), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('candidate', choices=list(CANDIDATES)+['provision'])
    parser.add_argument('--model', choices=MODEL_REVISIONS)
    parser.add_argument('--smoke', action='store_true')
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    if args.candidate == 'provision':
        if not args.model:
            parser.error('--model is required for provisioning')
        provision(args.model)
    else:
        import fcntl
        DIRECTORY.mkdir(parents=True, exist_ok=True)
        with (DIRECTORY / 'generation.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            generate(args.candidate, args.smoke, args.resume)
