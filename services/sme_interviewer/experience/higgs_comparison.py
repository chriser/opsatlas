"""Matched female/male Higgs audition; original evaluations remain immutable."""
import hashlib
import json
import os
import time

from .catalog import REFERENCE_TEXT, REFERENCES, RUNTIME
from .evaluation import CASES, MODEL_REVISIONS, load_evaluation_model

DIRECTORY = RUNTIME / 'higgs-comparison-2026-09-24'
CANDIDATES = {'higgs-female': 'Higgs · female reference (VCTK p228)',
              'higgs-male': 'Higgs · male reference (VCTK p254)'}


def generate():
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1')
    import mlx.core as mx
    import numpy as np
    import soundfile as sf

    DIRECTORY.mkdir(parents=True, exist_ok=True)
    mx.set_cache_limit(256 * 1024**2)
    model = load_evaluation_model('higgs', RUNTIME / 'audition2-higgs')
    model._codec.set_dtype(mx.float32)
    model.eval()
    mx.eval(model.parameters())
    for candidate, speaker in zip(CANDIDATES, ('anna', 'charles'), strict=True):
        reference = RUNTIME / 'references/vctk' / REFERENCES[speaker]
        # One encoded reference reused for every passage in this voice column.
        codes = model.encode_reference_audio(str(reference))
        code_hash = hashlib.sha256(np.asarray(codes).tobytes()).hexdigest()
        rows = []
        for case in CASES:
            settings = {'text': case['text'].replace('. ', '. <|prosody:pause|> '),
                        'ref_text': REFERENCE_TEXT, 'seed': 41, 'temperature': 1.0,
                        'max_tokens': 1000, 'stream': False, 'fade_in_ms': 0, 'fade_out_ms': 0}
            start = time.perf_counter()
            chunks = []
            first = None
            for result in model.generate(ref_audio_codes=codes, **settings):
                chunks.append(np.asarray(result.audio, dtype=np.float32).reshape(-1))
                if first is None:
                    first = (time.perf_counter()-start)*1000
            elapsed = (time.perf_counter()-start)*1000
            audio = np.concatenate(chunks)
            if not len(audio) or not np.isfinite(audio).all():
                raise ValueError('Invalid generated audio')
            path = DIRECTORY / f'{candidate}-{case["id"]}.wav'
            sf.write(path, audio, result.sample_rate, subtype='PCM_16')
            duration = len(audio)/result.sample_rate
            rows.append({'candidate': candidate, 'case': case['id'], 'file': path.name,
                         'first_output_ms': round(first, 1), 'total_ms': round(elapsed, 1),
                         'audio_seconds': round(duration, 3), 'rtf': round(elapsed/1000/duration, 3),
                         'clipped_samples': int(np.sum(np.abs(audio)>=1)),
                         'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                         'reference_file': reference.name,
                         'reference_sha256': hashlib.sha256(reference.read_bytes()).hexdigest(),
                         'reference_codes_sha256': code_hash,
                         'model_repo': MODEL_REVISIONS['higgs'][0],
                         'model_revision': MODEL_REVISIONS['higgs'][1],
                         'codec_compute_dtype': 'float32', 'settings': settings})
            temp = DIRECTORY / f'{candidate}.json.tmp'
            temp.write_text(json.dumps(rows, indent=2)+'\n')
            temp.replace(DIRECTORY / f'{candidate}.json')
            print(candidate, case['id'], round(elapsed), flush=True)


if __name__ == '__main__':
    import fcntl

    from .evaluation import DIRECTORY as PREVIOUS_DIRECTORY
    with (PREVIOUS_DIRECTORY / 'generation.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        generate()
