"""Offline, repeatable audition generation. Run one engine per isolated process.

Use the Pocket virtualenv for pocket, the speech virtualenv for the other engines.
Never invoked by the HTTP server. First-chunk measurements exclude model loading;
the first utterance is explicitly marked cold. Playback assets are peak/RMS matched.
"""

import argparse
import asyncio
import hashlib
import json
import os
import time

from .catalog import PROMPTS, REFERENCE_TEXT, REFERENCES, ROOT, RUNTIME, VOICES

os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1', TOKENIZERS_PARALLELISM='false')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('engine', choices=['kokoro', 'pocket', 'chatterbox', 'qwen'])
    parser.add_argument('--smoke', action='store_true')
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    import numpy as np
    import soundfile as sf

    output = RUNTIME / 'clips'
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    if args.engine == 'pocket':
        import importlib.resources

        import yaml
        from pocket_tts import TTSModel

        source = importlib.resources.files('pocket_tts') / 'config/english.yaml'
        config = yaml.safe_load(source.read_text())
        model_path = str(RUNTIME / 'pocket/languages/english/model.safetensors')
        config['weights_path'] = model_path
        config['weights_path_without_voice_cloning'] = model_path
        config['flow_lm']['lookup_table']['tokenizer_path'] = str(RUNTIME / 'pocket/languages/english/tokenizer.model')
        local_config = RUNTIME / 'pocket/local.yaml'
        local_config.write_text(yaml.safe_dump(config))
        model = TTSModel.load_model(config=local_config)
        model.has_voice_cloning = False  # Only the public stock-voice checkpoint is provisioned.
    elif args.engine == 'kokoro':
        from ..mlx_voice import MetalKokoro

        model = MetalKokoro(ROOT / '.runtime')
    else:
        import mlx.core as mx
        from mlx_audio.tts.utils import load_model

        mx.set_cache_limit(256 * 1024**2)
        model = load_model(str(RUNTIME / ('qwen-base' if args.engine == 'qwen' else 'chatterbox')))
        if args.engine == 'chatterbox':
            # Upstream's hook tries an unpinned online download. Explicitly replace
            # those weights from our pinned offline artifact before conditioning.
            weights = mx.load(str(RUNTIME / 's3tokenizer/model.safetensors'))
            if hasattr(model._s3tokenizer, 'sanitize'):
                weights = model._s3tokenizer.sanitize(weights)
            model._s3tokenizer.load_weights(list(weights.items()))
        model.eval()
        mx.eval(model.parameters())
    load_ms = (time.perf_counter() - started) * 1000
    results_path = RUNTIME / f'{args.engine}-results.json'
    records = json.loads(results_path.read_text()) if args.resume and results_path.exists() else []
    completed = {(r['candidate'], r['prompt']) for r in records}
    cold = True
    for candidate, voice in VOICES.items():
        if voice['engine'] != args.engine:
            continue
        prepared = time.perf_counter()
        if args.engine == 'pocket':
            state = model.get_state_for_audio_prompt(str(RUNTIME / f"pocket/languages/english/embeddings/{voice['voice']}.safetensors"))
        elif args.engine == 'chatterbox':
            model.prepare_conditionals(str(RUNTIME / 'references/vctk' / REFERENCES[voice['voice']]))
        preparation_ms = (time.perf_counter() - prepared) * 1000
        for prompt_id, (_, text) in PROMPTS.items():
            if (candidate, prompt_id) in completed:
                continue
            if args.smoke and prompt_id != 'pronunciation':
                continue
            chunks, first_ms, rate = [], None, 24000
            arrivals, sample_count = [], 0
            begin = time.perf_counter()

            def consume(audio):
                nonlocal first_ms, sample_count
                chunk = np.asarray(audio, dtype=np.float32).reshape(-1)
                if len(chunk):
                    if first_ms is None:
                        first_ms = (time.perf_counter() - begin) * 1000
                    chunks.append(chunk)
                    sample_count += len(chunk)
                    arrivals.append({'end_sample': sample_count, 'arrival_ms': (time.perf_counter() - begin) * 1000})

            if args.engine == 'kokoro':
                async def run():
                    async for audio, _ in model.create_stream(text, voice['voice'], lang='en-gb'):
                        consume(audio)
                asyncio.run(run())
            elif args.engine == 'pocket':
                import torch

                torch.manual_seed(42)
                for audio in model.generate_audio_stream(state, text):
                    consume(audio.detach().cpu().numpy())
            else:
                mx.random.seed(42)
                kwargs = {'text': text, 'stream': True, 'streaming_interval': 0.4, 'max_tokens': 1000}
                if args.engine == 'qwen':
                    kwargs.update(ref_audio=str(RUNTIME / 'references/vctk' / REFERENCES[voice['voice']]),
                                  ref_text=REFERENCE_TEXT, lang_code='English')
                for result in model.generate(**kwargs):
                    consume(result.audio)
                    rate = result.sample_rate
            total_ms = (time.perf_counter() - begin) * 1000
            if not chunks:
                failure = {'candidate': candidate, 'prompt': prompt_id, 'error': 'No generated audio'}
                with (RUNTIME / 'generation-failures.jsonl').open('a') as log:
                    log.write(json.dumps(failure) + '\n')
                print(json.dumps(failure), flush=True)
                continue
            audio = np.concatenate(chunks)
            if not np.isfinite(audio).all() or not np.any(audio):
                raise ValueError('Non-finite or silent audio')
            # Same RMS target, peak ceiling. No time stretch, trimming or EQ.
            rms = float(np.sqrt(np.mean(audio ** 2)))
            gain = min(0.1 / max(rms, 1e-8), 0.95 / float(np.max(np.abs(audio))))
            path = output / f'{candidate}-{prompt_id}.wav'
            temporary_audio = path.with_suffix('.tmp.wav')
            sf.write(temporary_audio, audio * gain, rate, subtype='PCM_16')
            temporary_audio.replace(path)
            window = max(1, rate // 100)
            onset = next((i for i in range(0, len(audio) - window, window)
                          if np.sqrt(np.mean((audio[i:i + window] * gain) ** 2)) > 0.005), None)
            energy_chunk_ms = next((chunk['arrival_ms'] for chunk in arrivals
                                    if onset is not None and chunk['end_sample'] > onset), None)
            record = {'candidate': candidate, 'prompt': prompt_id, 'file': path.name,
                      'text': text, 'sample_rate': rate, 'audio_seconds': len(audio) / rate,
                      'first_chunk_ms': first_ms, 'synthesis_ms': total_ms,
                      'rtf': total_ms / 1000 / (len(audio) / rate), 'cold': cold,
                      'load_ms': load_ms, 'voice_preparation_ms': preparation_ms,
                      'gain': gain, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            record.update(first_energy_chunk_ms=energy_chunk_ms,
                          leading_quiet_ms=onset / rate * 1000 if onset is not None else None,
                          chunk_arrivals=arrivals)
            records.append(record)
            cold = False
            temporary_results = results_path.with_suffix('.tmp.json')
            temporary_results.write_text(json.dumps(records, indent=2))
            temporary_results.replace(results_path)
            print(json.dumps(record), flush=True)


if __name__ == '__main__':
    main()
