# Private evaluation: Breeze, Fish and Higgs

24 September 2026. Owner explicitly clarified that this is personal local testing and requested all three models. This supersedes any suggestion that a paid commercial licence is required before this limited audition.

## Scope and terms

Based on the published terms and the clarified use, proceed with a bounded private listening evaluation. No customer-facing deployment, product promotion, vendor purchase or model training is part of this iteration. Being a PoC or not earning revenue is not, by itself, a universal exemption; the actual limited evaluation purpose is what matters here.

- [Breeze licence](https://huggingface.co/BreezeBlue/Breeze-TTS-2/blob/main/LICENSE), sections 1.6–1.7: personal/limited testing, and explicitly limited internal benchmarking even by a for-profit entity.
- [Fish licence](https://github.com/fishaudio/fish-speech/blob/main/LICENSE), section II: personal use and evaluation/testing within non-commercial purpose; commercial operations have separate terms.
- [Higgs licence](https://huggingface.co/bosonai/higgs-tts-3-4b/blob/main/LICENSE), sections II and III: short-term evaluation/testing and explicitly limited internal benchmarking by a for-profit entity.

This is an operational reading for the stated evaluation, not a blanket commercial-use clearance. Downloaded checkpoints retain their licence/notice files. No output from one model is used to train another. Ratings retain unreviewed/non-training status. Existing live Tibi model and approved knowledge are unchanged.

## Reproducible design

A separate `/voice-evaluation` page preserves the original `/voice-benchmark` aliases, audio and feedback. New ratings are kept in `.runtime/experience/evaluation-2026-09-24/feedback.jsonl` and exported separately. Four configurations:

1. Breeze TTS 2 BF16 with the existing licensed British reference and understated native direction.
2. Breeze TTS 2 BF16 with a designed British female voice and the same restrained delivery instruction.
3. Fish S2 Pro BF16 with the existing British reference and native direction.
4. Higgs TTS 3 with the original BF16 language-model weights and FP32 codec arithmetic with the same British reference, native sentence pause cues and contentment cues for warm/gentle material.

Four representative passages per configuration: greeting, product introduction, accepting a correction and numbers. Breeze generation proved too slow to justify a larger first audition. Six additional Higgs diagnostic clips, including greeting seeds 42/43, are retained locally but excluded from the four-case comparison. Original misleading transcript passages remain labelled audition material, not approved product claims.

The exact engine input (including native tags), settings, checkpoint revision, reference hash, output hash, generation time and peak MLX allocation are recorded. Waveform speed is never changed. Higgs adapter edge fades are explicitly disabled for this raw generation comparison. Any playback edge treatment in the live product is a separate concern. Output files are PCM16 with raw peak/clipping counts recorded; levels are not perceptually matched, so loudness can bias preference. These clips test these configurations, not all possible voices of each model.

All generation runs locally, sequentially on the GPU and inside the existing network-denying inference sandbox. Checkpoint downloading is a separate explicit network step. Full-utterance emission timings are not live microphone-to-speaker latency. Fish's installed MLX adapter does not implement streaming, so success in this audition does not establish suitability for the final live pipeline.

Pinned repositories/revisions are in `services/sme_interviewer/experience/evaluation.py`. Provision each model, then run generation using the existing speech environment:

```sh
services/sme_interviewer/.venv/bin/python -m services.sme_interviewer.experience.evaluation provision --model breeze
services/sme_interviewer/.venv/bin/python -m services.sme_interviewer.experience.evaluation provision --model fish
services/sme_interviewer/.venv/bin/python -m services.sme_interviewer.experience.evaluation provision --model higgs
/usr/bin/sandbox-exec -f services/sme_interviewer/offline.sb services/sme_interviewer/.venv/bin/python -m services.sme_interviewer.experience.evaluation breeze-directed
# Repeat sequentially for breeze-designed, fish and higgs.
```

Model and adapter failures must be reported as failures, never filled with another engine's audio. No voice is promoted until the owner accepts both its prepared delivery and subsequent live behaviour.

## Mac adapter checks

Higgs required an explicit `higgs_audio_v3` model-type selection because the generic loader failed to resolve its upstream alias from the local directory name. Its bundled codec loader also tried to convert BF16 through NumPy; the evaluation-only adapter uses MLX to read the same safetensors directly. A tiny BF16 tensor probe verified preservation of dtype and values. No global package patch or Torch installation was made.

An initial ten-clip Higgs diagnostic exposed BF16 waveform amplitude stepping. The final audition uses FP32 codec arithmetic while retaining the original language-model precision and checkpoint. A separate probe produced finite float32 waveform output without the coarse BF16 grid. This does not establish a perceptual improvement by itself. Initial clips and their manifest are retained locally under `higgs-bf16-diagnostic`; no owner ratings existed when the final set was regenerated. Native emotion/pause cues remain model inputs; no waveform tempo manipulation is used.

## Measured first audition

Sixteen displayed clips: four matched passages for each of four configurations. Six additional Higgs clips remain diagnostic evidence. No subjective winner has been selected.

| Configuration | Warm median generation | Warm median real-time factor | Peak MLX allocation |
|---|---:|---:|---:|
| breeze-directed | 119.9 s | 7.79 | 13.30 GB |
| breeze-designed | 82.3 s | 7.51 | 11.92 GB |
| fish | 11.2 s | 1.06 | 17.47 GB |
| higgs | 4.9 s | 0.50 | 11.94 GB |

Real-time factor is generation time divided by audio duration; below 1 is faster than real time. Small sample counts, warm/cold process differences and concurrent checkpoint downloads make these exploratory measurements, not controlled performance claims. GPU generation jobs were serialised. First-output timing here is full-utterance availability. Peak MLX allocation is not total system RAM.

Breeze BF16 is currently too slow for live Tibi on this adapter. Prepared listening quality can still justify a later quantisation/runtime investigation. Fish streaming is unavailable in the installed adapter. Higgs has the most promising measured latency in this small run, but accent, pronunciation and prosody still require owner listening.

Reproducible measurements, exact inputs, hashes, model provenance and local ASR diagnostics: [evidence](evidence/2026-09-24/tiberius-three-model-evaluation.json). ASR is an automated content check, not a substitute for human listening.

Validation: 23 relevant Python tests passed, including isolated feedback tokens and hiding non-comparison diagnostics; Ruff and JavaScript syntax checks passed. Local HTTP checks verify all sixteen new WAV endpoints and all forty original clips. Existing wider suite earlier in the iteration passed 353 Python and 60 JavaScript tests.

The local Whisper check recovered the full requested content across all sixteen clips, including the £15,000/£50,000 distinction and approval before activation. Higgs's greeting was transcribed as “Tiderius”; this flags the name for listening review and is not proof of a synthesis error. “Tibi” was consistently rendered as “Tibby” by ASR. No subjective naturalness or accent scores were invented. Zero measured clipped samples does not rule out audible artefacts.
