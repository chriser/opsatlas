# OpsAtlas local interviewer and voice audition


Initial G1 prototype for #1519 and the manual recording/cancellation portion of #1520. It runs independently of Atlas, on **macOS Apple Silicon**, at <http://127.0.0.1:8767>. The standalone synthetic interview at `/interview` adds saved sessions, checked local questions and unpublished drafts. Atlas integration, automatic endpoint detection and approved-knowledge publication remain later work.

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

There is one active job per server. Cancelling a synthesis job terminates its worker, so the next use reloads the model. The browser tracks request generations and discards stale responses. The interview requires the already-installed `gpt-oss:20b` at `127.0.0.1:11434`. It runs entirely on the Mac: low reasoning for coverage/review and medium reasoning for question writing. The interview sends confirmed wording to this local model; provisional text and audio are not sent to that planner. No captured content is uploaded or published into Atlas. There are no background microphone recordings, telemetry integrations or external inference calls.

The interview includes named microphone selection, input metering, elapsed time, local recording playback and provisional retry/discard. Recordings without usable amplitude are rejected before inference; near-silent edges are trimmed with padding. This is not a speech detector. The first Chrome/Edge headset interview failed with “you”; digital silence reproduced that exact recognizer output. The Human subsequently confirmed successful recording across multiple questions. See the [recording fix and retest history](../../docs/initiatives/sme-interviewer/12-synthetic-interview.md#headset-trial-failure-and-recovery-fix--19-september-2026).

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

These development probes use fictional accounts and write to ignored `.runtime/`. They are not held-out acceptance evidence. Policy v4 incrementally assesses 15 details, then writes one short follow-up from the confirmed conversation and actual earlier questions. It explores decisions, conditions and unclear terms without automatically reading back an excerpt. Current source references and a local semantic review precede speech; one repair is allowed. Explicit unknowns use a brief source-finding guide. Hypotheticals must remain conditional. Expand **What this question draws on** to inspect the related wording. Saved question IDs preserve replay across follow-ups on the same topic. Invalid output/timeouts leave a visible pending follow-up and a review prompt (45-second overall planning limit); retry **Ask next question**. A deferred question does not automatically speak a generic review prompt. Prior source-backed coverage survives additions, retries and failures; corrections invalidate dependent coverage. Unknown answers retain the exact question in drafts. Local follow-ups are slower than v2; recent probes took roughly 12–29 seconds, with longer corrections sometimes requiring a retry. This remains a synthetic trial, not Human G2 acceptance.
