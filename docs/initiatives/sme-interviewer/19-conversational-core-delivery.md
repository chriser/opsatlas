# Conversational core — accepted plan and timing foundation

20 September 2026 · Implements the Human's request to adopt the independent review. Baseline: `ebbe010`, including v6 and Claude's published review. Next release slice: #1581 (S114).

## Review disposition

The review's structural findings are accepted. Keep the v6 local runtime and service/ledger isolation. Stop adding supplier-specific guards and stop expanding #1524; resolve its delivered v5/v6 coverage/planning scope. Generalisation belongs to #1587. Voice B remains interim. The evidence is development evidence, not a conversational-quality gate.

ADR-013–017 are accepted directions, pending implementation evidence. One clarification: checking names/numbers alone cannot prove an arbitrary generated factual assertion is grounded. S115 must constrain the live response grammar (including verbatim eligible evidence and source-bound reflections), while full claim validation remains off the speech path. Raw provisional transcript events may be persisted as observations; persistence must never imply validated or confirmed claims.

## Revised delivery order

| Order | Items | Delivery |
|---|---|---|
| 1 | #1581 / S114 | Timing foundation now; extend acoustic and streaming milestones as those capabilities arrive |
| 2 | #1576 / S109 | One duplex transport with session, turn, revision and generation identity; reconnect/replay |
| 3 | #1577 / S110 and #1580 / S113 | Continuous listening/endpointing and persistent recognition; clause synthesis |
| 4 | #1579 / S112 | Talker/thinker lanes, background analysis during speech; remove filler and model review from the critical path |
| 5 | #1578 / S111 and #1582 / S115 | Acoustic barge-in and constrained conversational grammar/persona |
| 6 | #1583 / S116 and #1586 / S119 | Recap confirmation with correction invalidation; quality rubric, simulated personas and untouched holdout |
| Gate | #1590 / S123 | Human ten-minute unscripted trial; no buttons/confirmation between turns; median naturalness/pace ≥4/5, p50 ≤1.5 s, zero fabricated spoken facts |
| 7 | #1587–#1589, #1584, #1585 | Atlas agenda/evidence, pacing, respectful interruption, expressive British voice comparison |

The conversational core takes priority over E2 capacity. Atlas page #1525 remains behind #1590; #1526 depends on #1586. No new ADO test-management artifacts. The manifest now includes all 71 published items. ADO had #1581 depending on #1576 despite the accepted instrument-first order; change its predecessor to the existing session ledger #1522. Full S114 acceptance will still require streamed events from later slices; this does not block starting S109 after the instrumentation foundation.

## This iteration: measurements before more optimisation

The existing form/voice interaction is instrumented without changing the model, speech engine or question logic. Each attempt has session, page, turn, generation and starting revision identity. A single page-monotonic clock records:

- Capture start and manual endpoint/recording limit.
- WAV encoding completion, ASR request and final transcript arrival.
- Confirmation beginning and the participant's save action, so human time is visible.
- Planning request and checked question arrival.
- Synthesis request, ready response, browser `loadeddata` and `playing` events.

`first_audio` means the browser has decoded playable media (`loadeddata`); `playback_start` means the browser emitted `playing`. Neither proves sound reached the headset. `first_token` and `speech_end` remain null on today's non-streaming, manually stopped path. We do not substitute complete question arrival for a first token or manual stop for acoustic end of speech. Unexpected recorder termination and the three-minute cap are excluded from manual-stop timing.

Session diagnostics are in a separate local `timings.sqlite`, not the transcript/claim ledger. They contain identifiers, statuses and milliseconds, no transcript or audio. `Download session timings` exports records and nearest-rank p50/p95 with n, grouped by input source and cold/warm/unknown residency. Current residency is unknown: prior requests do not prove warm models. All attempt outcomes are retained; incomplete/open attempts and failed/cancelled attempts do not silently become successes. Opening questions and replay are separate from answered turns. Late snapshots cannot rewrite recorded milestones or a terminal outcome. Timing failure shows a notice and does not block interview work.

Instrumentation has no retroactive baseline: old sessions have no timing samples. The true acoustic end-to-end distribution and #1586 rubric remain **not measured**, not zero latency or a pass. The next transport/listening/synthesis stories fill the missing milestones; #1581 stays Active until its complete criteria can be evidenced.

## Validation and remaining limitations

Verification and disposable browser evidence are recorded in [the timing evidence](evidence/2026-09-20/conversation-timing-foundation.json). The browser sample contained four attempts: two completed (opening and sequence check), and two deferred by the existing planner (generated follow-up and retry). The one completed typed answer measured 1,162.6 ms from confirmation action to browser playback; n=1 is only an instrumentation development observation. True acoustic turn-gap n=0; quality rubric n=0. These failures remain open under the conversational-core work, with no new fixture guard. Local model outputs during that check are development observations. No holdout is used or tuned against. Existing HTTP polling remains until S109. This release makes no speed or naturalness improvement claim.

The next iteration is #1576: introduce the duplex event contract and reconnect behaviour, keep explicit cancellation and revision checks, and carry these timings through it. S110 then supplies labelled speech endpoints, S113 supplies actual first audio chunks, and S112 supplies streamed first-token timing. Concurrent 64 GB resource measurements and the held-out writer assessment remain required.
