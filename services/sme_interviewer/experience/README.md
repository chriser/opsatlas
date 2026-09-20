# Local conversation experience lab

This is an isolated audition and turn-taking experiment, not a replacement for the
interviewer. No planner, evidence retrieval or publication runs here. The live
interviewer on 8767 and candidate on 8768 are unaffected.

Run from the repository root:

```sh
services/sme_interviewer/.venv/bin/uvicorn services.sme_interviewer.experience.app:app --host 127.0.0.1 --port 8769 --ws-max-size 4096
```

Open <http://127.0.0.1:8769/>. Voice labels are shuffled on each server start.
Listen, rate naturalness/pronunciation/British accent/pace, then reveal identities.
The eight candidates cover Kokoro, Pocket TTS, Chatterbox Turbo and Qwen Base,
with male and female voices. A missing generated sample is disabled. Ratings are
stored in `.runtime/experience/ratings.jsonl`; `/api/results` exports them with
measurements. Do not interpret agent UI smoke tests as human quality ratings.

Listening practice deliberately uses scripted follow-ups. Native Silero detects
speech in 32 ms frames; Smart Turn estimates completion from the latest eight
seconds of audio. Two confident completion estimates and at least one second
without detected speech are required before a scripted follow-up.
An incomplete answer keeps the floor; encouragement can be delayed or disabled.
A committed cue finishes before a queued question. User speech cancels playback
and the pending queue. Headphones are recommended. This is not emotion recognition,
semantic answer checking or native speech-to-speech. The combined policy is experimental.
The WAV replay control exercises this path without microphone access. Microphone
and replay audio are transient; the server never writes them or creates transcripts.

## Reproduce the voice assets

The existing speech environment supplies MLX Audio 0.5.4. Pocket is isolated so
its Torch dependencies do not modify the running interviewer:

```sh
uv venv --python services/sme_interviewer/.venv/bin/python services/sme_interviewer/.runtime/experience-env
uv pip sync --python services/sme_interviewer/.runtime/experience-env/bin/python services/sme_interviewer/experience/pocket-requirements.lock
services/sme_interviewer/.venv/bin/python -m services.sme_interviewer.experience.provision
/usr/bin/sandbox-exec -f services/sme_interviewer/offline.sb services/sme_interviewer/.runtime/experience-env/bin/python -m services.sme_interviewer.experience.generate pocket
/usr/bin/sandbox-exec -f services/sme_interviewer/offline.sb services/sme_interviewer/.venv/bin/python -m services.sme_interviewer.experience.generate kokoro
/usr/bin/sandbox-exec -f services/sme_interviewer/offline.sb services/sme_interviewer/.venv/bin/python -m services.sme_interviewer.experience.generate chatterbox
/usr/bin/sandbox-exec -f services/sme_interviewer/offline.sb services/sme_interviewer/.venv/bin/python -m services.sme_interviewer.experience.generate qwen
```

Run GPU generators sequentially for meaningful measurements. `--resume` preserves
completed samples; `--smoke` generates only the pronunciation passage. Empty output
is recorded in `generation-failures.jsonl`, never silently replaced with another voice.
All nonempty generated clips are finite PCM16 WAV, RMS-targeted to 0.1 with a 0.95
peak ceiling; this is approximate level matching, not perceptual LUFS matching.
No time stretching, pause editing or EQ is applied. Input wording is identical.

The first-chunk metric begins after loading and voice preparation; it is a synthesis
metric, not microphone-to-audible-response latency. `first_energy_chunk_ms` records
when the chunk containing the first 10 ms window above RMS 0.005 became available;
`leading_quiet_ms` records its location in the level-matched waveform. This is an
energy proxy, not measured word intelligibility. `cold` identifies the first
utterance after loading. Inference is sandboxed without network access; provisioning
is the explicit download step. Revisions are pinned in `provision.py`, and provision
writes SHA256 artifact inventory. Existing Kokoro weights use the service model lock.

## Attribution and model provenance

- [Kyutai VCTK reference clips](https://huggingface.co/kyutai/tts-voices):
  University of Edinburgh [VCTK corpus](https://datashare.ed.ac.uk/handle/10283/3443),
  CC BY 4.0. p228 sentence 23 and p254 sentence 23 are Kyutai's enhanced variants.
  They condition Chatterbox/Qwen; Anna/Charles are Pocket's public stock embeddings.
  The reference sentence was checked with local Whisper. No user's voice is cloned.
- [Chatterbox Turbo MLX model card](https://huggingface.co/mlx-community/chatterbox-turbo-4bit)
  and [Qwen Base MLX model card](https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-0.6B-Base-4bit)
  declare Apache 2.0. Upstream Turbo ignores exaggeration/CFG controls; none are advertised here.
- [Pocket public stock-voice model](https://huggingface.co/kyutai/pocket-tts-without-voice-cloning)
  is used instead of the gated cloning checkpoint.
- [Smart Turn](https://github.com/pipecat-ai/smart-turn) CPU v3.2 endpoint model;
  its output is an uncertain turn-completion estimate, not a fact check.

## PersonaPlex feasibility experiment

The user granted official Hugging Face model access on 20 September 2026. Optional
`provision --personaplex` checks access to NVIDIA's official repository before
downloading the Apple adaptation. Credentials are read from the local HF login;
never put them in source, command arguments or logs.

The Swift port is pinned to `soniqo/speech-swift` commit
`c4c2fabbe825a9290c19e2f45d54ca3eae96b003`. `Probe.Package.swift` builds only its
AudioCommon, MLXCommon, PersonaPlex and benchmark targets. `Probe.swift` uses
prerecorded fictional audio and does not open a microphone. It requests three-frame
(240 ms) streaming chunks and records actual arrival times, generated audio and text.
The probe also exercises real-time inference with two 16-second paced-file feeds.
Neither test opens a microphone or establishes live headset behaviour or grounding.

The port currently ignores explicit `cacheDir` when resolving voice prompts. The
isolated source checkout is patched to retain `modelDir` in `explicitCacheDirectory`
and return it from `modelCacheDirectory()`. Without this fix a missing voice could
silently invalidate the comparison. Neither the main app nor installed libraries
are patched.

The isolated checkout also waits for a complete incoming audio frame in
`respondRealtime`; the upstream loop otherwise inserts silence whenever generation
outruns capture. This input-clock guard is reproduced by `prepare_probe.py`.

The community 8-bit model card declares **CC BY-NC 4.0**, separately from NVIDIA's
official model terms. It is not a deployment choice. If the experiment is promising,
use a conversion of the licensed official checkpoint with reviewed provenance before
any product integration. The measured probe sustains short paced feeds but its
content drifts and number checks fail. See document 24 and the evidence JSON;
PersonaPlex is not connected to the interviewer or selected as its voice engine.

```sh
services/sme_interviewer/.venv/bin/python -m services.sme_interviewer.experience.prepare_probe --build --run
```

The pinned Swift dependencies require the installed Xcode/Swift toolchain and Apple's
Metal compiler component. The first build exposed a missing component on this Mac;
`xcodebuild -downloadComponent MetalToolchain` installed version 27A266a. Dependency
revisions are recorded in `Probe.Package.resolved`. The probe expects provisioned
`personaplex-mlx` files and a generated Pocket numbers passage.
