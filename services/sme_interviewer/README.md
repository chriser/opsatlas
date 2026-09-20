# OpsAtlas local interviewer and voice audition


Initial G1 prototype for #1519 and the manual recording/cancellation portion of #1520. It runs independently of Atlas, on **macOS Apple Silicon**, at <http://127.0.0.1:8767>. The standalone synthetic interview at `/interview` adds saved sessions, checked local questions and unpublished drafts. The continuous conversation at `/conversation` adds resident ASR/VAD, automatic endpoints, interruptible chunked speech and recap confirmation. Atlas integration and approved-knowledge publication remain later work.

## Continuous conversation

Open <http://127.0.0.1:8767/conversation>. Start once with your headset, then answer naturally. Pause stops microphone capture and output. Review recap stops listening and lets you correct all wording and contribution kinds before confirming once. Numbers/negation can trigger a short readback. Voice B remains selected. The original `/interview` is the push-to-talk fallback; existing sessions remain there.

For an already provisioned checkout, install the additional pinned local components once:

```sh
services/sme_interviewer/.venv/bin/python -m services.sme_interviewer.provision_conversation
```

This adds Silero VAD v6.2 and Whisper small.en, and compiles the resident adapter against the existing pinned whisper.cpp. Both recognition and synthesis children run without network access. The browser sends transient mono 16 kHz PCM over a same-origin authenticated WebSocket; generated PCM returns in bounded chunks. Only one continuous conversation can own the engines at a time. Reopening a saved conversation requires an explicit Resume, so it cannot silently activate a microphone.

See [delivery and measured limitations](../../docs/initiatives/sme-interviewer/21-continuous-voice-increment.md). This is a synthetic prototype: the latency and physical-headset acceptance gates remain open. `?rehearsal=1` exposes a local fictional WAV input instead of requesting microphone access, for testing the same AudioWorklet pipeline.

## Pace candidate: optional GPU Voice B

The continuous candidate combines interpretation and the next question in one local inference, prepares real speech during a settled pause, and moves semantic question review off the speech path. Background review is persisted and included in recap/draft provenance. It does not approve facts. See [measurements and remaining quality failures](../../docs/initiatives/sme-interviewer/22-conversation-pace-candidate.md).

The optional Apple Silicon backend keeps the selected British `bf_isabella` vectors and the existing Kokoro pronunciation/pause handling. Provision its pinned artifacts explicitly, then select it at startup:

```sh
services/sme_interviewer/.venv/bin/python -m services.sme_interviewer.provision_mlx_voice
SME_VOICE_BACKEND=kokoro_mlx ./services/sme_interviewer/start.sh
```

The default remains ONNX Kokoro. A missing or mismatched GPU artifact fails explicitly; inference never downloads it. GPU workers keep a 256 MiB free-buffer cache target and a 2 GiB allocator guideline, not a hard memory cap. Short-question latency does not imply equally fast whole-paragraph synthesis; the conversation splits recap speech into sentences.

Reproduce the synthetic development probes with:

```sh
services/sme_interviewer/.venv/bin/python -m services.sme_interviewer.evaluate_routing_models --combined
services/sme_interviewer/.venv/bin/python -m services.sme_interviewer.evaluate_spoken_flow
services/sme_interviewer/.venv/bin/python -m services.sme_interviewer.evaluate_gpu_voice
services/sme_interviewer/.venv/bin/python -m services.sme_interviewer.concurrent_benchmark --continuous-runtime
```

Run timing probes separately from other model workloads. The concurrency probe creates a separate fictional Atlas fixture; it does not measure a full production workload. Rehearsal mode accepts a sequence of fictional WAVs and runs each after the preceding speech drains. Physical headset and unscripted naturalness acceptance remain open.

## Run on the provisioned Mac

From the repository root:

```sh
./services/sme_interviewer/start.sh
```

Open `/interview` for the [complete synthetic trial](../../docs/initiatives/sme-interviewer/12-synthetic-interview.md), or `/` for the voice studio. Compare the same passage across A/B/C before revealing names. Try numbers/negation and the gentle challenge as well as the welcome. Type your own phrase, or record up to 30 seconds and review the transcript before reading it back. **Stop** cancels synthesis/recognition and playback. Starting a recording also interrupts playback; this is push-to-talk, not automatic acoustic barge-in.

The initial candidates are Kokoro `bf_emma`, Kokoro `bf_isabella`, and Qwen3-TTS 1.7B VoiceDesign 4-bit prompted for a British female voice. The designed voice is regenerated from a description for each utterance; cross-turn voice consistency requires listening. No voice cloning is used. The Human selected B on 19 September 2026 and rejected C’s accent as American-sounding. B is now the default; the comparison remains available. This preference does not establish transcription or acoustic acceptance.

## Reproduce setup and evidence

Prerequisites: macOS arm64, Python 3.12, uv, CMake, a C++ toolchain and ffmpeg. Setup downloads approximately 3 GB of public model artifacts, installs an isolated virtual environment and compiles whisper.cpp with Metal. It never changes Atlas dependencies or `.env`.

```sh
./services/sme_interviewer/setup.sh
# Optional: repeat the bounded simultaneous Atlas experiment; local Ollama must
# already contain qwen2.5:7b-instruct, and the root Atlas .venv must be installed.
services/sme_interviewer/.venv/bin/python -m services.sme_interviewer.concurrent_benchmark
# Deterministic service checks use the existing root test environment:
.venv/bin/pytest tests/test_sme_interviewer.py -q
```

`requirements.lock` pins package artifacts with hashes; `model-lock.json` pins downloaded model files and the whisper.cpp source revision. Provisioning refuses a checksum/revision mismatch. Provisioning is the only online stage. Native synthesis/recognition children run under `offline.sb`, denying all network operations; offline Hugging Face flags add defence in depth. The web server permits only loopback hosts, validates same-origin requests, requires a per-process mutation token and serves no remote assets. Keep the default loopback binding. This single-operator audition is not a remotely deployable authentication design.

Generated synthetic listening samples and measured JSON live in ignored `.runtime/audition/`. The versioned [prototype evidence](../../docs/initiatives/sme-interviewer/11-prototype.md) reports the precise workload and limitations; sample playback itself is not an inference benchmark.

## Spoken amounts

The TTS boundary renders explicit sterling amounts in British English: `£15,000` becomes “fifteen thousand pounds” and `£1.50` becomes “one pound and fifty pence”. Captured and displayed transcripts are unchanged. The deterministic `en-gb-sterling-v1` policy handles whole amounts up to 12 digits, conventional comma grouping, up to two decimal places and leading signs. Unsupported notation is left unchanged, not guessed. This pronunciation transform is separate from recognition: a one-penny synthetic round trip was misrecognised as one pound and remains a documented limitation requiring transcript review.

## Data and cancellation

Microphone WAVs are decoded to mono 16 kHz PCM, bounded to 0.1–180 seconds at the API (the interview UI permits three minutes; the voice-studio UI remains 30 seconds), held in a temporary directory during recognition and removed on normal completion, cancellation or handled failure. Abrupt OS/process termination can leave temporary files in the OS temp area. Voice-studio job transcripts are in server memory for up to roughly 10.5 minutes and in the current browser page until replaced/reloaded. The interview separately persists provisional/confirmed transcripts, revisions and draft packets in `.runtime/interviews.sqlite` after explicit synthetic-storage consent; there is no automatic deletion or retention scheduler. Custom generated audio expires on the same schedule, on Stop, or on clean shutdown. A restart removes leftover custom WAVs in the service-owned transient folder. Prepared synthetic samples are intentionally retained.

There is one active job per server. Cancelling a synthesis job terminates its worker, so the next use reloads the model. The browser tracks request generations and discards stale responses. The interview requires the already-installed `qwen3.5:35b-a3b` writer and `qwen2.5:7b-instruct` reviewer at `127.0.0.1:11434`. Both run entirely on the Mac and remain resident for 30 minutes. The interview sends confirmed wording to the local planner; provisional text and audio are excluded. No captured content is uploaded or published into Atlas. There are no background microphone recordings, telemetry integrations or external inference calls.

The interview includes named microphone selection, input metering, elapsed time, local recording playback and provisional retry/discard. Recordings without usable amplitude are rejected before inference; near-silent edges are trimmed with padding. This is not a speech detector. The first Chrome/Edge headset interview failed with “you”; digital silence reproduced that exact recognizer output. The Human subsequently confirmed successful recording across multiple questions. See the [recording fix and retest history](../../docs/initiatives/sme-interviewer/12-synthetic-interview.md#headset-trial-failure-and-recovery-fix--19-september-2026).

During local question planning, the page immediately shows a quiet animated status. Text changes after 0.9 seconds; a prepared Voice B cue plays only if planning is still running after 2.2 seconds. The cue adds no model request and stops before the checked question is spoken.

## Known limits

- Basic Human headset capture has passed a retest; noisy-room recognition, echo handling, acoustic barge-in and long sessions remain unverified. Synthetic TTS-to-ASR checks do not establish human word-error rate.
- Kokoro currently returns completed audio. Qwen's first internal chunk is measured, but the browser waits for the completed WAV; no end-to-end streaming claim.
- Speech generation failures are shown without exposing request text. Native dependency warnings are recorded in ignored local worker logs. A failed worker can be retried.
- Dialogue writes source-grounded follow-ups and checks them before speech; the model-based semantic review remains fallible, and observations remain unverified. Only the synthetic fixture adapter is implemented. Real Atlas evidence, identity/RBAC, semantic adjudication and publication remain outstanding.

## Contextual dialogue checks

```sh
services/sme_interviewer/.venv/bin/python -m services.sme_interviewer.evaluate_conversation
services/sme_interviewer/.venv/bin/python -m services.sme_interviewer.evaluate_interview
```

These development probes use fictional accounts and write to ignored `.runtime/`. They are not held-out acceptance evidence. Policy v6 updates typed coverage from the answered question and narrow explicit facts, then uses resident Qwen 3.5 35B-A3B to write one short source-grounded follow-up. Deterministic guards and a focused resident Qwen 2.5 7B review precede speech; one repair is allowed. Both calls use the same 8,192-token context and a 30-minute keep-alive. Explicit unknowns use a brief source-finding guide. Hypotheticals must remain conditional. Expand **What this question draws on** to inspect the related wording. Saved question IDs preserve replay across follow-ups on the same topic. Invalid output/timeouts leave a visible pending follow-up and a review prompt (45-second overall planning limit); retry **Ask next question**. A deferred question now speaks an explicit recovery message when automatic speech is enabled. Corrections invalidate dependent coverage. Four final warm seeded v6 turns took 1.622–1.738 seconds on the target Mac; broader and held-out evaluation remains pending. See the [v6 architecture and evidence](../../docs/initiatives/sme-interviewer/17-low-latency-conversation-architecture.md). This remains a synthetic trial, not Human G2 acceptance.

## Turn timing diagnostics

The interview now saves a separate local `timings.sqlite` with browser-monotonic milestones and no transcript content. **Download session timings** exports records, failure/cancellation counts and p50/p95 with sample sizes. Confirmation time is included in manual-stop-to-playback measurements. Acoustic speech-end and first-token timestamps remain null until streaming capture/generation exist; decoded-media and browser playback events are explicitly labelled. Residency is currently unknown, not assumed warm. Historical sessions have no retrospective measurements. See [accepted core plan and timing definitions](../../docs/initiatives/sme-interviewer/19-conversational-core-delivery.md).


### Combined conversation-core increment

The interview uses an authenticated same-origin WebSocket for commands and pushed session/audio completion. It preserves optimistic revisions and request idempotency. Reopen disconnected sessions safely paused; no mutation or old speech is automatically replayed. Only one live tab may control a session. `start.sh` sets an 8 MB WebSocket message limit matching complete recording uploads. Audio remains complete-file capture/playback; this is not continuous recognition or streamed synthesis yet.

Before confirmation is saved, an advisory local Qwen 3.5 35B-A3B check distinguishes relevant/unknown answers from unrelated, unclear or inconsistent wording. Existing capture warnings take the recording-retry route; semantic text alone never proves microphone noise. Clarifications keep the wording editable and preserve the original question; **Keep this answer and continue** explicitly overrides a mistaken assessment. The checker does not verify facts. Changed wording must be checked again.

Committed thinking audio finishes before a prepared question plays; explicit Stop, Pause or Record interrupts immediately. Stop no longer disables automatic speech. Development evidence and limitations: [combined increment](../../docs/initiatives/sme-interviewer/20-conversation-core-increment.md). Reproduce the local semantic probe with `python -m services.sme_interviewer.evaluate_answer_check`; run playback/transport checks with `node --test tests/test_sme*_browser.mjs`.
