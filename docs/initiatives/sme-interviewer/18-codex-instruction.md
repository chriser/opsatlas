# Instruction to Codex — conversational core

**20 September 2026 · from the Human, following the accepted [independent review](16-independent-review.md) · baseline `8ffddd7` (v6).**

Read this with the review. It tells you what changed in the plan, what to build, in what order, and what to stop doing. Nothing here withdraws the non-regression rulebook or any governance decision.

## What the review found, in one paragraph

The design pack is right and the engineering discipline is good. The delivered interaction, however, is a push-to-talk form with voice at both ends, not the streaming conversation the architecture page specifies. The real-time behaviours — continuous listening, endpointing, barge-in, streamed speech, acknowledgement and reflection — were never given a build story; they exist only as acceptance targets and as a spike, #1520, whose push-to-talk fallback became the product. Four iterations of prompt and guard tuning on #1524 could not fix that, because the problems are structural. Your v6 latency work is credited: it correctly identified the masking filler and cut planning from 7.7–8.9 s to 1.6–1.7 s. Keep it. It is the first third of the job.

## What is now in the backlog

Four Features under Epic #1515, all New, with a new Human gate:

| Item | Purpose |
|---|---|
| [#1572](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1572) SME-F13 | Real-time conversational loop — Stories #1576–#1581 |
| [#1573](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1573) SME-F14 | Interviewer persona and behaviour — Stories #1582–#1586 |
| [#1574](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1574) SME-F15 | Atlas-grounded interviewing — Stories #1587–#1589 |
| [#1575](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1575) SME-F16 | Human conversation gate G1.5 — Story #1590 |

Re-scoped: #1520 keeps recognition quality only; #1521 records Voice B as interim; #1523's intent completes in #1587; #1525 now waits on the gate #1590; #1526 now depends on #1586. Each carries a comment explaining why.

## Order of work

**Do these in order. Do not start at step 4 because it is the interesting one.**

1. **#1581 — instrument the real turn gap.** Browser-side timestamps for endpoint, final transcript, first token, first audio, playback start. Until this exists, no latency claim means anything. Your v6 figures measure planning only; the participant's gap also contains capture, encoding, recognition, their own confirmation work and whole-file synthesis, and nobody has measured it.
2. **#1576 — streaming duplex transport.** Replace POST-and-poll on the live path. Nothing else in F13 can be built on a 200 ms poll loop.
3. **#1577 and #1580 together** — continuous listening with VAD and endpointing, and clause-level streamed synthesis. Independent of each other.
4. **#1579 — the talker/thinker split.** Analysis runs from partial transcripts while the person is still speaking. This is where the remaining gap closes.
5. **#1578 and #1582** — acoustic barge-in, and the conversational response grammar that replaces the bare-question validator.
6. **#1583 and #1586**, then the **#1590** gate — recap confirmation and the quality harness.
7. **#1587, #1588, #1589, #1584, #1585** — Atlas grounding, live challenge, pacing, interruption, voice round two.

## Stop doing

- **Stop adding fixture-specific guards.** v6 added an exact-string pass rule for one supplier-activation sentence and replacement wording naming the manager's approval. Every Human trial failure has produced another regex. None of it survives contact with a second process, and #1587 will delete it. Your own v4 checkpoint said this: "more deterministic guards should not be presented as a general solution to understanding the account." That was right.
- **Stop treating seeded development scenarios as evidence of quality.** Four scenarios that you wrote, and that you tuned against, cannot tell you whether the interviewer is good. #1586 exists for this. Until it exists, say "development check", not "passed".
- **Stop masking latency.** v6 already demotes the spoken cue correctly. When #1579 lands, remove it.
- **Do not resolve #1524 by continuing it.** Close it on the v5/v6 coverage and planning work with the evidence you have. Its remaining intent is now #1579, #1582, #1587 and #1588.

## Keep doing

Service isolation and the non-regression rulebook. The revisioned ledger, correction lineage and provenance hashes. Local-only inference. The three validation lanes. The claim lifecycle and Atlas-owned publication. Recording failed trials honestly, including the ones you had to abandon — that record is why this review could be written quickly and accurately.

## Two design points that need care

**Moving checks between lanes is not removing them (ADR-013).** Spoken turns get cheap deterministic checks: no number, name, date or factual assertion that is not in the participant's own words or a cited eligible excerpt, and evidence quoted verbatim. Anything entering the ledger, a draft or publication keeps the full model review, off the critical path. An interviewer's question is not knowledge; today the heaviest check guards the lowest-risk output while the highest-risk path — what gets written down — is comparatively light.

**Confirm at recap, not per turn (ADR-016).** The requirement is that a claim traces to confirmed wording and a transcript revision. It was never that the person must operate a form every turn. Infer the contribution kind, speak a check only for high-impact ambiguity such as numbers, names and negation, and let them correct the lot at the recap. A correction there must invalidate dependent derived notes exactly as it does today.

## Two risks from v6 to carry forward

1. The writer is now `qwen3.5:35b-a3b`, the model the v4 checkpoint rejected for unsupported assumptions and repeated details. Non-thinking mode is a genuinely different configuration, so this is a fair retry — but it rests on four seeded turns. Confirm it in #1586 against a holdout before treating it as settled.
2. Residency now assumes a 23 GB writer, a 7B reviewer, Kokoro, whisper and Atlas coexisting on 64 GB. Measure it under concurrent load, and report memory as well as latency.

## Reporting

Per iteration, report: the #1581 turn-gap distribution with sample size, the #1586 rubric scores, structural test results, and any failure you found and did not fix. Keep reporting numerator and denominator. Keep the holdout untouched. Do not lower a threshold to pass a gate — if the criteria are wrong, say so and propose a change rather than meeting them quietly.

The #1590 gate is ten unscripted minutes on a synthetic process, no button between turns, no per-turn confirmation, median ≥ 4/5 for naturalness and pace, measured p50 ≤ 1.5 s, zero fabricated spoken facts. Build toward that conversation, not toward the test suite.
