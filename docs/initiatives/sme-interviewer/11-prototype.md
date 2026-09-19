# Initial prototype: local speech audition

> Current follow-up: the [complete synthetic interview](12-synthetic-interview.md) is now available alongside this voice audition. The measurements and remaining acoustic limits below retain their original scope.

**19 September 2026 · #1519 delivered; #1520 partial; Human selected Voice B under #1521.** This is the first executable slice of the approved isolated trial. It is not yet the full interview/evidence/review workflow.

## Headset confirmation and currency read-back correction

**Follow-up, 19 September 2026.** The Human confirmed that their headset captured the requested phrase exactly: “The limit is £15,000, not £50,000. Approval happens before activation.” This is one successful physical-device capture, not a broad human recognition or automatic turn-taking acceptance.

The Human then reported Voice B spoke the £ symbol before the amount. The TTS boundary now uses deterministic British-English sterling rendering (`en-gb-sterling-v1`): `£15,000` → “fifteen thousand pounds”; it preserves the displayed/captured text and does not use a model to rewrite numerical values. Regression coverage includes decimal pence, signs, singular/plural, malformed notation and unchanged surrounding negation. Unsupported notation is not partially interpreted.

The corrected original phrase was synthesised with B under the network-deny policy, and its local recognition round trip retained both amounts and “before”. A separate decimal probe correctly supplied “one penny” to TTS for £0.01, but recognition of that audio returned £1.00. That round trip **failed**; whether recognition or acoustic rendering caused it is not established. Keep it as a remaining fidelity case rather than claiming all monetary amounts are verified. [Raw correction evidence](evidence/2026-09-19/currency-fix.json).

Verification for this fix: **503 backend tests passed**, including 33 speech-rendering regression cases; Ruff passed. The live worker was replaced while idle, retaining the browser transcript and selected B. No Atlas startup import was allowed outside temporary `KP_DATA_DIR`. #1520 stays Active for remaining acoustic/endpointing and fidelity work.

## What runs

Open <http://127.0.0.1:8767> on the Mac Studio. The standalone [service](../../../services/sme_interviewer/README.md) provides 60 prepared samples (20 passages × three voices), optional hidden model labels, custom speech, bounded microphone capture, editable transcripts, and cancellation. **B / Kokoro `bf_isabella` is the selected default.** The Human said B has the best voice style; C would otherwise be preferable but sounds American. Record C as failing the accent preference, not as an accepted British voice. A remains a comparison, not a Human-approved fallback.

The microphone only starts on an explicit button press. Recording or Stop interrupts playback; Stop also terminates active model computation. This is a push-to-talk fallback. Automatic endpointing, acoustic barge-in, spontaneous hesitations, room echo and the intended physical microphone still need evaluation. Transcript review precedes read-back. No dialogue model consumes microphone text and nothing is published into Atlas.

## Pinned configuration and actual host

Host queries confirmed Apple M4 Max, arm64, 16 CPU cores and 64 GiB unified memory; macOS 26.6.2. The 40-core GPU count is Human-supplied. A separate Python 3.12 environment contains Kokoro ONNX 0.6.1, MLX Audio 0.5.4 and their hashed dependencies. whisper.cpp v1.9.4 is compiled with Metal and uses `base.en`. The model/source/checksum lock and upstream licences are in [model-lock.json](../../../services/sme_interviewer/model-lock.json), [requirements.lock](../../../services/sme_interviewer/requirements.lock) and [third-party provenance](../../../services/sme_interviewer/THIRD_PARTY.md).

| Candidate | Configuration | First-request wall time | Warm synthesis p50 / p95 | Peak worker RSS |
|---|---|---:|---:|---:|
| A | Kokoro `bf_emma`, fp32, CPU ONNX, 4 threads | 3.30 s | 1.06 / 1.36 s | 0.96 GiB |
| **B, selected** | Kokoro `bf_isabella`, fp32, CPU ONNX, 4 threads | 1.96 s | 1.08 / 1.32 s | 0.94 GiB |
| C, accent rejected | Qwen3-TTS 1.7B VoiceDesign, MLX 4-bit, seeded descriptive voice | 18.61 s | 2.02 / 2.63 s | 2.43 GiB |

Each candidate has one first request and 19 subsequent passages. “First request” starts a new worker; filesystem, shared-library and OS caches were not flushed, so these are not equivalent cold-boot comparisons. The warm figures measure completed waveform generation. Qwen's median first internal chunk was 111 ms, but this UI waits for its complete WAV and does not claim that playback latency. RSS is sampled every 25 ms and excludes some shared/Metal allocations. No 100-turn end-to-end latency gate is passed by these measurements.

[Raw speech and recognition evidence](evidence/2026-09-19/report.json) contains every observed timing, prompt and configuration. Raw synthetic audio is retained locally in the ignored runtime; model binaries and recordings are not committed.

## Recognition, cancellation and offline checks

Nine clean synthetic TTS-to-ASR probes (welcome, challenge, numbers for A/B/C) retained the key meaning. All retained the 15,000-versus-50,000 and before-versus-after distinctions. The first recogniser execution took 15.20 seconds including first-use startup/Metal work; later process invocations took 174–246 ms for these short recordings. This is not human word-error-rate evidence.

A second [16-case stress probe](evidence/2026-09-19/recognition-stress.json) used B for numbers, acronyms, correction wording and uncertainty, with clean audio and seeded Gaussian noise at 20, 10 and 0 dB SNR. At clean/20/10 dB the recorded transcripts retained the scripted wording apart from punctuation/case/number rendering. At 0 dB, acronyms and the correction passage developed substantive errors (for example SME → FME and sequence → city). Numbers/negation survived that fixture, but this must not be generalised to other speakers or noise. Every live transcript remains explicitly reviewable.

[Native runtime checks](evidence/2026-09-19/runtime-checks.json) cancelled one warm worker per candidate after 50 ms of synthesis. Cancellation-to-process-exit was A 5.5 ms, B 5.9 ms and C 24.2 ms, with no late audio file. These are software measurements, not user-speech-to-speaker-stop timing or a false-cut-off rate. Deterministic browser tests additionally cover a late create response after Stop and Stop while an earlier job is being cancelled.

All native synthesis and recognition calls ran under the macOS `offline.sb` network-deny profile. Explicit external and loopback socket attempts under that exact profile failed with `PermissionError`. Model acquisition is an explicit online provisioning step; serving performs no model downloads. The controller/browser uses only local same-origin routes. Loopback binding, host/origin validation, a per-process action token, bounded bodies and a restrictive content policy protect this single-operator trial.

## Simultaneous Atlas workload

A disposable Atlas instance used its existing HTTP Ask route, lexical retrieval and real local `qwen2.5:7b-instruct` (Q4_K_M, digest recorded in the evidence), with one synthetic approved supplier document. Context was 8192, temperature 0.1, RAG-only, with rewrite/rerank/grounding validation excluded. Five sequential questions were asked per condition after warm-up, while the candidate continuously generated speech. The fixture created no production source or approval records.

| Condition | Ask p50 / observed p95 | Completed overlapping TTS requests |
|---|---:|---:|
| Atlas alone | 289 / 423 ms | 0 |
| Atlas + A | 325 / 536 ms | 2 |
| Atlas + B | 310 / 488 ms | 2 |
| Atlas + C | 321 / 468 ms | 1 |

All 20 measured answers were non-refusals with one citation and the RAG path. Minimum observed system-available memory was 25.75 GiB in the C condition; this is a machine-wide observation, not total speech GPU memory. The development desktop remained running, condition order was fixed and this very small sample has uncontrolled cache/thermal/background effects. It establishes successful coexistence for this bounded fixture only. It does not establish full-corpus production capacity, parallel governance performance, or a meaningful tail-latency estimate. [Raw concurrent evidence](evidence/2026-09-19/concurrent-report.json).

## Verification and remaining work

- Root backend regression: **470 passed**, including 20 new service tests. The service tests also pass in the separate speech environment. Repository Ruff passed; two deterministic Node cancellation-race tests passed; JavaScript syntax passed; existing Atlas frontend production build passed.
- Browser checks: sample playback, custom speech, model-label reveal and rapid Stop verified; no warning/error console entries. The microphone HTTP route was exercised with synthetic audio without activating a physical microphone. Microphone permission, live capture and the Human's device are not claimed as tested.
- Existing Starlette/httpx deprecation and Vite bundle-size notices remain. The separate environment also reports an AnyIO deprecation. Qwen emitted a loader compatibility notice and a semaphore-cleanup warning on process termination; all requested waveform probes completed. No target inference call failed.
- Test side effect: the first full regression invocation imported Atlas without `KP_DATA_DIR` isolation and triggered its existing startup rebuild of the derived ontology. Source documents/register were not edited. The full run was repeated successfully with a temporary data directory. Future full-suite commands must set `KP_DATA_DIR` before importing Atlas.
- #1519 is ready to Resolve after push/wiki read-back. #1520 stays Active: labelled acoustic endpoint/interruption, hesitation/noise and physical-device evidence remain incomplete. Human voice preference is recorded in #1521; it does not accept those other criteria.
- The Human confirmed a headset with a built-in microphone and headphone playback. The next required evidence is a live recording/transcription trial through that device; brand/model is not a blocker. Later session ledger, adaptive dialogue, evidence packs, Atlas navigation and review/publication stories remain unimplemented.

Run instructions and actual transient-data retention are in the [service README](../../../services/sme_interviewer/README.md). The service uses its own ignored runtime, never directly opens Atlas's store and does not change Atlas dependencies, provider configuration or Anam behaviour.
