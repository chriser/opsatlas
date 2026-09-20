# Continuous voice and recap — 20 September 2026

The next combined prototype is at `/conversation`. Start listening once, answer naturally, interrupt spoken output, then review and confirm the whole account at recap. British Voice B remains selected. `/interview` remains the push-to-talk fallback and holds earlier sessions. This is a functional synthetic prototype, **not a passed conversational-quality or latency gate**.

## Delivered together

- Same-origin authenticated WebSocket transports microphone PCM and generated PCM, with one active continuous engine owner. A browser AudioWorklet emits 512-sample/32 ms mono 16 kHz frames and renders received audio. Sequence gaps, stalled capture and playback backlog pause explicitly.
- Resident Silero v6.2 speech detection and Whisper small.en recognition replace per-answer model startup in this mode. Both native children and Kokoro run under the existing network-denying sandbox. New artifacts and source revisions are pinned and checked during explicit provisioning.
- Partial recognition starts speculative local interpretation and question preparation during the answer. A result is reused only if its normalised transcript exactly matches the final transcript. Generation changes cancel obsolete work and audio. No cloud planner is used.
- Endpoint silence is 700 ms after a model-rated complete thought, 1,600 ms for an incomplete thought, or 1,100 ms without a rating. Sustained speech onset interrupts playback. Continued speech while a reply is still being prepared carries the interrupted text forward. These are development settings, not validated universal thresholds.
- Voice B returns actual PCM batches. The server permits two unconsumed batches, and the browser acknowledges rendered batches. Consecutive recap clauses keep their playback queue. Explicit Pause rejects already-sent late audio as well as cancelling further synthesis.
- Local routing distinguishes responsive, unknown, unrelated, unclear and inconsistent answers; contribution type remains editable. Numeric/negated short answers receive a wording check. Spoken pause/recap commands and on-screen controls are supported.
- Final recognition is saved as an unassessed hearing attempt before slower reasoning. Accepted turns become provisional contributions. Only a revision-checked, complete recap confirmation makes wording eligible for draft claims. Corrections retain previous text and invalidate derived notes. Unassessed attempts remain visible and are included in provenance, not claims.
- Reopen/resume is explicit. Saved conversations reopen at recap; no microphone starts silently. Reading a recap does not request microphone permission. Confirmed drafts expose Markdown/JSON exports, with factual validation and owner approval still pending.

The existing question validator receives an ephemeral hearing-only copy with eligible source states. That copy is never persisted as confirmed wording or as coverage. Comparison with the fixture guide is disabled on this path before confirmation. Runtime memory and audio are transient; local SQLite stores transcript/events and separate diagnostic timings.

## Findings that changed this release

A development replay found Whisper base.en hearing “VAT” as “V18”. In five synthetic cases (amounts, negation, acronyms, hesitation and added noise), small.en preserved the critical wording. Its warm recognition calls were approximately 76–96 ms on this Mac. This small, synthetic comparison supports the provisional model choice; it does not establish headset accuracy or a general error rate.

A short agreement was incorrectly labelled policy. Routing now explicitly distinguishes agreement about events from describing a rule. Six local development probes exercise agreement, irrelevant speech, unknown information, policy, pause and incomplete thoughts; their results are retained.

The final browser rehearsal uncovered an older `check_evidence` rewrite that changed a bank-check question into a manager-approval question because both appeared in the same source sentence. That rewrite has been removed. A regression test protects subject preservation. The reviewer instruction now distinguishes evidence of an event from whether the event happened. The same stored account then produced “How was the bank details check evidenced or verified?” and passed semantic review on its first attempt. The original failed rehearsal is retained; the successful recheck was at the model/planning boundary, not a second full browser trial.

## Validation and evidence

[Evidence directory](evidence/2026-09-20/continuous-voice/) contains model checksums, recognition comparison, routing probes, review evaluation, browser timings and the failed/successful question checks. Reproduce the development probes with:

```sh
services/sme_interviewer/.venv/bin/python -m services.sme_interviewer.evaluate_resident_speech
services/sme_interviewer/.venv/bin/python -m services.sme_interviewer.evaluate_turn_interpreter
services/sme_interviewer/.venv/bin/python -m services.sme_interviewer.evaluate_question_review
```

Verification: 665 root Python tests; 215 service-environment Python tests; 40 browser-state/AudioWorklet tests; Ruff; frontend production build. The 13-case existing labelled review set passed. Browser rehearsal used fictional WAVs through the actual AudioWorklet/PCM path, without access to the physical microphone. It exercised automatic capture/endpointing, spoken follow-ups, reopening, spoken recap, correction of wording/type and draft confirmation. Automated regressions additionally cover interruption, stale audio, continuation, longer hesitation, backpressure, revision conflicts, authentication, competing connections and cleanup. Neither VM browser tests nor synthetic browser playback prove physical headset echo cancellation.

Timing is deliberately qualified:

| Measurement | Result | Interpretation |
|---|---|---|
| Two browser answer turns before the final wording fix | 1,696.4 / 4,423.5 ms from detected speech end to first rendered audio | n=2; nearest-rank p50/p95; development sample only |
| Later rejected follow-up | 5,158.3 ms to rendered recovery speech | Failure, not a successful contextual question |
| First audio for a representative question | Approximately 0.8 seconds | Kokoro first-batch latency still exceeds the 400 ms target |

The browser clock derives speech end from VAD sample position and measures AudioWorklet rendering. It does not measure sound arriving at a headset. `first_token` remains null: final question JSON is not token streaming. Precomputed exact-match questions help some turns, but the existing writer/reviewer sequence remains on a cache miss. No claim of a ≤1.5 s median, p95 compliance, warm residency, 100-turn success rate or human naturalness pass is made.

## Remaining release gates and next batch

S109–S113/S116 now have an integrated prototype covering duplex PCM, resident recognition, software interruption, speculative preparation, chunked speech and recap confirmation. Their full acceptance remains open. S114 remains open for complete measurements. No acceptance story is closed merely because the interface exists.

The next optimisation batch should reduce writer/reviewer work on misses, benchmark smaller TTS batches or an alternative local speech engine with Voice B quality as a baseline, and run a labelled multi-turn simulation including hesitation, noise, corrections, unrelated speech and deliberate interruption. The larger recognition model must also be measured alongside Atlas under the 64 GB budget. The ten-minute physical-headset trial and independent naturalness rubric remain later gates. No holdout was used for tuning in this release.

Known limitations: a conservative negation check can request readback for “I do not know”; partial transcript changes can waste speculative work; speech inference may restart after cancellation; no automatic reconnection silently resumes listening; combined interrupted answers retain all hearing-attempt events, but no original audio is retained for replay. Real enterprise evidence and publication remain outside this synthetic release.

Post-commit protocol check of `6bd89f9`: the real resident-engine path accepted the fictional account, generated and spoke the bank-check follow-up, clarified an unrelated answer, and honoured the spoken recap command. See `release-protocol-check.json`. Its client acknowledged audio immediately, so its endpoint-to-first-chunk figures are not browser playback latency. Local deployment preserved all existing contribution text; startup recovery paused the previously active legacy session.
