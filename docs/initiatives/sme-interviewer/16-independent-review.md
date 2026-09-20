# Independent review — plan, backlog and first iterations

**20 September 2026 · Reviewer: Claude (Review) · Status: accepted by the Human and published.** The review itself changed no code and no runtime behaviour. It covers documents 01–15, `backlog.json`, the live ADO items #1500–#1551 (52 items, matching the manifest) and the service source at commit `221f330`. Latency figures labelled *measured* come from Codex's own evidence files; figures labelled *target* are proposals and have not been measured.

**Baseline note.** The review was written against commit `221f330` (v5). While it was being published, Codex delivered `8ffddd7` (v6, "reduce local planning latency"). The reconciliation below records what v6 changes; the findings are otherwise unchanged and were re-verified against v6 source.

Published to ADO on 20 September 2026: Features [SME-F13 / #1572](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1572), [SME-F14 / #1573](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1573), [SME-F15 / #1574](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1574) and [SME-F16 / #1575](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1575) under Epic #1515, carrying Stories #1576–#1590. Codex's working instruction is [18-codex-instruction.md](18-codex-instruction.md).

## Verdict

1. **The foundation is strong and should be kept.** Service isolation, separate runtime and data, network-denied model workers, the revisioned ledger, provenance hashes and the honest recording of failed trials all match the brief's "do not break Atlas" and "single signed-off truth" requirements.
2. **The documented target architecture is right; the implemented turn loop is not that architecture.** [04-architecture](04-architecture.md) describes a listening, endpointing, interruptible, three-lane design with a 1.5 s response target. What runs today is a turn-based form with voice input and output: press to record, press to finish, review the transcript, choose a category, tick a box, save, wait for the planner, wait for a complete audio file, listen.
3. **The backlog does not contain the stories that would build the conversational loop.** The real-time behaviours exist only as acceptance *measures* in [06-evaluation](06-evaluation-and-delivery.md) and as a "spike" with a push-to-talk fallback in #1520. The fallback became the product. #1524, a 5-point story, has absorbed five iterations (v2–v6) of prompt, guard and runtime tuning. v6 shows what that tuning can achieve on latency; it also shows what it cannot reach, because naturalness does not live in the planner.
4. **Recommendation:** insert a *conversational core* ahead of Atlas page integration (#1525), protected by a Human conversation gate, and re-balance where checking happens (see ADR-013 below). Details and proposed work items follow.

## Reconciliation with v6 (commit `8ffddd7`)

Codex delivered a latency iteration a few hours after this review was drafted, documented in [17-low-latency-conversation-architecture](17-low-latency-conversation-architecture.md). Its diagnosis agrees with Finding 1: the canned phrases were "masking a slow architecture", and the three sequential general-model calls were the cause.

**What v6 genuinely fixes.** Coverage extraction is removed from the critical path: a confirmed answer now inherits the detail identity of the question it answered, so only the writer and a reviewer call remain. The writer moves to `qwen3.5:35b-a3b` in non-thinking mode with a 7B reviewer, both with a 30-minute keep-alive, and an accidental context-size change that was forcing a 23 GB reload between calls is fixed. Measured warm planning fell from 7.7–8.9 s to **1.622–1.738 s** across four seeded questions. The spoken cue is now suppressed unless planning exceeds 2.2 s. This is real progress on the largest single component of machine time and it should be kept.

**What v6 does not change.** Every structural finding below was re-verified against v6 source and still holds:

- Capture is still push-to-talk: `MediaRecorder` starts and stops on a button, with no voice-activity detection or endpointing.
- Per-turn transcript confirmation is unchanged — review, choose a kind, tick, save. On the voice path this is the largest remaining gap, and it is human time that no model change reduces.
- Synthesis still renders a complete WAV before playback.
- Transport is still POST-and-poll, including a 200 ms planning loop.
- One model review call still sits on the speech path (ADR-013 still applies, though it now costs far less).
- The question validator still permits only a bare single question, and the writer prompt still forbids acknowledgement, reflection and preamble. Finding 2 is untouched.
- No persona, barge-in or interviewer-initiated interruption.
- The Atlas adapter is still the single invented fixture.

**Two things v6 adds that need watching.**

1. *Fixture over-fitting increased.* v6 adds literal-string special cases, including an exact-match pass rule for one sentence about supplier activation and hard-coded replacement wording naming the manager's approval. This is the Finding 3 trajectory continuing. S120 (#1587) should remove these, not extend them.
2. *An accepted recall trade-off.* The v6 document states the sidebar "can under-report a detail from the initial free narrative". Coverage of the free account now rests on narrow deterministic recognisers. That is a reasonable trade for latency, but it is a quality regression that needs the S119 (#1586) harness to quantify rather than a seeded scenario to confirm.

The writer model is also the one the v4 checkpoint rejected for "unsupported assumptions and repeated details". Non-thinking mode is a materially different configuration, so this is a legitimate retry, not a contradiction — but it is evidence from four seeded development turns, and it needs the holdout harness before it can be called settled. Memory residency also now assumes a 23 GB writer plus a 7B reviewer plus speech models and Atlas coexisting on 64 GB; measure that under concurrent load.

**Effect on the plan:** none of the proposed work is withdrawn. S112 (#1579) keeps its acceptance criteria, and v6 has already done part of it; what remains there is moving analysis into the SME's speaking time, removing the last review call from the critical path, and proving the target from end of speech to first audio rather than from model-call start to model-call end. The v6 figures measure planning only. The gap the Human actually experiences still includes capture, encoding, recognition, confirmation and whole-file synthesis, and has not yet been measured end to end — which is why S114 (#1581) comes first.

## The turn as it runs today

| Step | Mechanism | Cost |
|---|---|---|
| Capture | Button starts `MediaRecorder`; button ends it. Nothing is processed while the SME speaks ([interview.js](../../../services/sme_interviewer/web/interview.js)) | Whole answer is dead time for the system |
| Encode | Browser decodes the full blob, resamples, base64-encodes a WAV, POSTs it | Grows with answer length |
| Recognise | A new `whisper-cli` process per utterance, reloading `base.en` each time ([speech.py](../../../services/sme_interviewer/speech.py)); browser polls every 150 ms | *Measured* 174–246 ms for short clips; longer for real answers |
| Confirm | SME reviews text, selects one of five contribution kinds, ticks a confirmation, saves | Human time; typically the largest part of the gap |
| Plan | Sequential non-streaming model calls ([dialogue.py](../../../services/sme_interviewer/dialogue.py), [conversation.py](../../../services/sme_interviewer/conversation.py)); browser polls every 200 ms. v5: extraction → writer → reviewer on a reasoning model. v6: writer → reviewer, resident, non-thinking | *Measured* 13–22 s (v4); 6.8–8.9 s (v5); **1.6–1.7 s (v6)**; 45 s ceiling |
| Speak | Kokoro on CPU renders the complete WAV, then playback begins ([worker.py](../../../services/sme_interviewer/worker.py)) | *Measured* warm p50 1.08 s |

The agreed target is p50 ≤ 1.5 s from end of speech to first substantive audio. At v5 the floor was roughly 8–9 s of machine time plus the manual confirmation steps; v6 cuts the planning component to about 1.7 s, leaving recognition, confirmation and whole-file synthesis as the remaining machine and human cost. No measurement yet exists for the complete gap the participant actually experiences, which is what S114 (#1581) exists to establish. The v5 "thinking cue" masked the delay rather than fixing it and contradicted the project's own policy ("avoid repetitive filler that hides system delay", [05](05-interview-experience.md)); v6 correctly demotes it to a fallback after 2.2 s, and S112 removes the need for it.

## Finding 1 — Why it is slow

The delay is structural, not a model-selection problem.

- **Everything is serial and batch.** No stage starts until the previous one has completely finished. Conversational systems overlap them: recognition streams while the person talks, the reply streams token by token, and speech starts on the first clause.
- **The SME's speaking time is wasted.** An SME talks for 30–120 seconds per answer. That is free compute time in which coverage extraction, claim drafting, evidence retrieval and conflict candidates could all be finished before they stop. Today, analysis begins only after the human has also confirmed the transcript.
- **Heavy verification sits on the speech path.** A full LLM review, and a possible regenerate-and-review cycle, runs before every spoken sentence. The brief explicitly allowed the opposite trade ("second layer of validation which is more off-line"), and doc 04's three lanes say the same. Implementation put lane-2 work in lane 1.
- **A reasoning model was on the live path.** Even at low effort it emitted hidden reasoning tokens before constrained JSON. **v6 fixes this**, moving to a non-thinking writer with a resident 7B reviewer and correcting a context-size change that was forcing a 23 GB reload between calls. Reasoning models belong in the background lane, and that is now where they are.
- **Weak recognition forces the manual gate.** `base.en` is the smallest practical model; its errors are the reason every turn needs transcript review. The M4 Max can run a materially better model as a persistent streaming worker.
- **Transport is request-and-poll.** Three polling loops add jitter and make barge-in and endpointing impossible. The research doc already recommended a WebSocket/AudioWorklet or Pipecat WebRTC path; it was not built.

## Finding 2 — Why it does not feel natural

- **Natural speech is forbidden by the validator.** `validate_question` requires output that starts with a question word, contains exactly one question mark and nothing else; the writer prompt says "no summary, quotation, acknowledgement, praise or preamble". "Thanks John, that's helpful — one thing I noticed…" cannot be produced. This contradicts the example exchanges in [05](05-interview-experience.md), which open with acknowledgements.
- **There is no persona layer.** No name, introduction, purpose, reassurance, ice-breaker, time check, humour policy in code, or closing. The first utterance is a bare instruction.
- **The interviewer does not listen.** No voice-activity detection, endpointing, backchannel, acoustic barge-in, or interviewer-initiated interruption. The brief's "interrupting in a respectful way at the right moments" needs live transcripts and a live lane; neither exists.
- **No reflective listening or recap in speech.** Summaries exist only as an on-screen draft.
- **Nothing is given back.** The brief's mutual-benefit idea (relevant facts, other teams' practice, changed rules) depends on Atlas evidence, which is still a one-document fixture.
- **The voice was chosen on read passages.** Voice B (Kokoro) is clear but has little prosodic range and no paralinguistics. The Human noted C "would otherwise be better" but for its accent. C's *measured* first audio chunk was 111 ms; the UI discarded that advantage by waiting for the full file.

## Finding 3 — The planner is over-fitted to one fixture

Fifteen hard-coded detail slots, a hard-coded comparison sentence, and regular expressions such as `(supplier|request) … (activated|released|on hold)` and `I (kept|put|placed) … on hold` encode the supplier-activation story in code. Each Human trial failure has produced another narrow guard, and v6 added more of them, including an exact-string pass rule for one supplier-activation sentence and hard-coded replacement wording that names the manager's approval. [13-checkpoint](13-conversation-checkpoint.md) correctly warned that "more deterministic guards should not be presented as a general solution"; v4 and v5 then added more. None of this transfers to a second process. The interview agenda should be derived from the Atlas ontology, Process Registry and EAM for the chosen process: what Atlas already holds (to verify), what it lacks (to elicit) and where its sources disagree (to resolve).

## Finding 4 — The differentiator has not been exercised

The brief's core value is an interviewer that knows the knowledge base and kindly challenges against it. After five iterations the Atlas adapter (#1523) is still a static JSON file, and the single comparison question is reachable only after all fifteen details are covered. Effort has gone into question selection on a path with no knowledge base behind it.

## Finding 5 — Evaluation does not measure what the Human experiences

Every iteration reports structural passes ("all 40 turn checks passed", 617 tests green) and then fails the Human trial on repetition, relevance or pace. There is no conversation-quality rubric, no simulated-SME multi-turn harness, and latency is measured per model call rather than from end of speech to first audio in the browser, including the confirmation steps.

## Brief-to-backlog coverage

| Brief requirement | Backlog today | Assessment |
|---|---|---|
| Standalone service, Atlas page | ADR-001, #1525 | Covered |
| Real-time conversational response | Targets in doc 06 only; #1520 is a spike | **No build story** |
| Active listening, acknowledgements | "Optional, sparse" in doc 04 | **No story; blocked by validator** |
| Respectful interviewer interruption | Policy in doc 05; one line in #1524 | **No mechanism** |
| User barge-in | #1520 criterion | Button only; acoustic path unbuilt |
| KB-aware questions and live challenge | #1523 + one criterion in #1524 | **Under-weighted; fixture only** |
| Works for any process | E3 pilot mention | **Planner hard-coded to one fixture** |
| Warm, humorous, non-judgemental persona | Policy text in doc 05 | **No story** |
| Mutual benefit, facts given back | One sentence in doc 05 | **No story** |
| Time-bound but thorough sessions | Facilitation example in doc 05 | **No story** |
| Best-in-class voice | #1521, one listener, read passages | Interim only |
| Coffee-break second-layer validation | #1532 | Covered by design |
| Second-owner adjudication | #1533 | Covered; consider a conversational form |
| Who-knows routing and follow-ups | #1537 | Covered, late; acceptable |
| Staged, governed enrichment of the ontology | E2 | Covered well |
| Meeting companion, desk device, projection | E4 parked | Correctly deferred |
| No ADO test cases | Respected | Covered |

## Proposed design decisions

| ADR | Proposal | Reason |
|---|---|---|
| 013 | **Separate speech safety from ledger safety.** Spoken turns get cheap deterministic checks (no number, name or factual assertion that is not in the participant's words or a cited excerpt; evidence quoted verbatim). Claims entering the ledger, drafts and publication keep the full model review, off the critical path | Interviewer utterances are acknowledgements and questions, not knowledge. Today the heaviest checks guard the lowest-risk output |
| 014 | **Talker and thinker lanes.** A fast non-reasoning model streams the spoken reply from a prepared agenda. A background thinker continuously updates coverage, claims, evidence matches and the question agenda from partial transcripts while the SME speaks | Uses the SME's speaking time; removes multi-call planning from the response gap |
| 015 | **One streaming duplex session** (WebSocket with AudioWorklet, or Pipecat Small WebRTC) replaces POST-and-poll on the live path | Prerequisite for endpointing, barge-in and streamed audio |
| 016 | **Confirm at recap, not per turn.** Speak a check only for high-impact ambiguity (numbers, names, negation). Infer contribution kind; the SME corrects it in the recap | Removes the largest human delay while keeping "only confirmed wording supports a claim" |
| 017 | **Agenda from Atlas, not from code.** Slots and gaps derive from the ontology/Process Registry/EAM for the selected process | Generalises beyond the fixture; makes the interviewer genuinely Atlas-aware |

ADR-003 (modular ASR → dialogue → TTS rather than an end-to-end speech model) remains correct: inspectable claims and clause-level cancellation matter more here than the last few hundred milliseconds.

### Target turn budget after these changes (targets, not measurements)

| Stage | Target |
|---|---|
| Endpoint decision after true end of speech | 300–500 ms |
| Final transcript available (already streaming) | +100–250 ms |
| First clause from talker model (warm, short prompt) | +300–500 ms |
| First audio from clause-level synthesis | +200–400 ms |
| **End of speech to first substantive audio** | **≈ 1.0–1.6 s** |

A short pre-rendered *contextual* acknowledgement may start earlier; it is reported separately and never counted as the substantive response, as doc 06 already requires.

## Proposed backlog amendments

New items continue the existing key sequence. Sizes are relative and provisional.

**Feature [SME-F13 / #1572](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1572) — Real-time conversational loop (under E1, before #1525)**

| Story | Scope | Core acceptance |
|---|---|---|
| [S109 / #1576](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1576) | Streaming duplex session transport | No polling on the live path; every event carries session, turn, revision and generation IDs; resume after restart |
| [S110 / #1577](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1577) | Always-listening capture with VAD and endpointing; persistent streaming recogniser; compare `base.en` with larger local models | Premature cut ≤ 5 % on labelled cases; critical-term error rate reported; push-to-talk remains only as a fallback |
| [S111 / #1578](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1578) | Acoustic barge-in on headset | User speech to output stop p95 ≤ 250 ms; no stale generation ever speaks |
| [S112 / #1579](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1579) | Talker/thinker split with a non-reasoning talker | End of speech to first substantive audio p50 ≤ 1.5 s, p95 ≤ 3 s over ≥ 100 in-browser turns; zero model-review calls on the critical path; canned thinking cues removed |
| [S113 / #1580](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1580) | Clause-level streaming synthesis and pre-rendered acknowledgement bank | First audio ≤ 400 ms after first clause; cancel at clause granularity |
| [S114 / #1581](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1581) | Per-turn latency instrumentation | Browser-side timestamps for endpoint, final transcript, first token, first audio; stored per session; reported each iteration |

**Feature [SME-F14 / #1573](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1573) — Interviewer persona and conversational behaviour**

| Story | Scope | Core acceptance |
|---|---|---|
| [S115 / #1582](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1582) | Conversational response grammar: acknowledgement or reflection, optional bridge or cited evidence, then one question; opening, reassurance, time check and closing | Bare-question validator replaced by the ADR-013 speech-safety check; doc 05 example exchanges reproducible |
| [S116 / #1583](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1583) | Active listening: sparse backchannels, periodic spoken reflection, spoken ambiguity checks, recap confirmation (ADR-016) | No per-turn confirmation form on the voice path; every claim in the draft still traces to recap-confirmed wording |
| [S117 / #1584](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1584) | Respectful interviewer-initiated interruption with cooldown and gentle/balanced/on-request setting | Interrupts only on stable transcript plus cited same-scope comparator or critical ambiguity; appropriateness rated in trials |
| [S118 / #1585](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1585) | Voice round two on conversational utterances (acknowledgements, kind challenges, light humour) with a British expressive challenger and streamed first-chunk timing | Human selects from blinded conversational samples; fidelity gate for numbers and negation retained |
| [S119 / #1586](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1586) | Conversation-quality harness: simulated SME personas with a hidden ground-truth process, planted contradictions and unknowns; rubric plus a one-page Human rating sheet | Rubric scores and turn-gap trend reported per iteration; development and holdout personas kept separate. Repository automation only — no ADO test artefacts |

**Feature [SME-F15 / #1574](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1574) — Atlas-grounded interviewing**

| Story | Scope | Core acceptance |
|---|---|---|
| [S120 / #1587](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1587) | Process-agnostic agenda from the Atlas ontology/Process Registry/EAM (read-only adapter; completes #1523) | A second, different synthetic process runs with no code change; fixture-specific regex guards deleted |
| [S121 / #1588](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1588) | Live evidence challenge and give-back within the 350 ms live-lane budget, using a session evidence pack prefetched and embedded at session start | Challenge precision ≥ 95 % on labelled cases; every spoken evidence statement quotes an eligible excerpt verbatim |
| [S122 / #1589](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1589) | Time-boxed agenda pacing with park, extend and coffee-break hand-off to #1532 | Session ends on time with uncovered topics listed; no silent truncation |

**Feature [SME-F16 / #1575](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1575) — Human conversation gate**

| Story | Scope | Core acceptance |
|---|---|---|
| [S123 / #1590](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1590) | Record the G1.5 conversation gate decision (Human / Review) | Ten unscripted minutes, no button between turns, no per-turn confirmation; median ≥ 4/5 naturalness and pace; measured p50 ≤ 1.5 s; zero fabricated spoken facts |

**Changes to existing items**

| Item | Change | Published |
|---|---|---|
| #1524 (S106) | Resolve as "coverage state and question planning v5" with current evidence. Stop adding fixture-specific guards. Remaining intent moves to S112, S115, S120 and S121 | Re-scope comment added; state left to Codex and the Human |
| #1520 (S102) | Narrow to recognition-quality evidence. Endpointing and barge-in become product stories S110 and S111, not a spike | Re-scope comment added |
| #1521 (S103) | Record Voice B as the interim voice; S118 is the actual selection | Re-scope comment added |
| #1523 (S105) | Fixture adapter intent completed by S120 | Re-scope comment added |
| #1525 (S107) | Make dependent on the conversation gate below; there is no value in embedding the form-based flow into Atlas | Predecessor #1590 linked |
| #1526 (S108) | Make dependent on S119; add turn-gap and rubric measures | Predecessor #1586 linked |

**New gate — G1.5 Conversation gate (Human), [SME-S123 / #1590](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1590).** A ten-minute unscripted headset conversation on a synthetic process with no buttons between turns and no per-turn confirmation. Pass needs median Human rating ≥ 4/5 for naturalness and pace, measured p50 ≤ 1.5 s, and zero fabricated spoken facts. E2 governance work is technically independent and may proceed in parallel, but F13–F15 take priority for Codex capacity.

## What should not change

Service isolation and the non-regression rulebook; the ledger, revisions and provenance; local-only inference; the three validation lanes; the claim lifecycle and Atlas-owned publication; the honest evidence practice. The proposal moves checks to the right lane; it does not remove them.

## Decision record

**20 September 2026 — Human accepted this review** and authorised publication. ADR-013 to ADR-017 are accepted in principle, F13–F16 and the G1.5 gate are added to the backlog, and further prompt and guard iteration on #1524 is paused. These ADRs are recorded here as proposals carried into delivery; each becomes binding in [07-decisions](07-decisions.md) when its implementing story produces evidence, and G1.5 remains a separate Human decision at [#1590](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1590).

Still open for the Human, not blocking a start:

- Whether the second voice round (S118) should compare a new expressive British challenger or re-audition existing candidates on conversational text.
- Whether E2 governance work (#1527) continues in parallel or pauses while Codex builds the conversational core.

## Suggested order of work

Instrument before optimising, then make the loop real, then make it sound human, then ground it in Atlas.

1. **#1581 (S114)** — measure the true turn gap in the browser first, so every later claim has a baseline.
2. **#1576 (S109)** — streaming transport; nothing else in F13 can be built on polling.
3. **#1577 (S110)** and **#1580 (S113)** — listen continuously and speak in clauses; these are independent and can run together.
4. **#1579 (S112)** — the talker/thinker split. This is where the 7-second gap actually closes.
5. **#1578 (S111)** and **#1582 (S115)** — barge-in and the conversational response grammar.
6. **#1583 (S116)** and **#1586 (S119)** — recap confirmation and the quality harness, then the **#1590** gate.
7. **#1587 (S120)**, **#1588 (S121)**, **#1589 (S122)**, **#1584 (S117)**, **#1585 (S118)** — Atlas grounding, live challenge, pacing, interruption and the voice round.

Codex's working instruction, including what not to do, is [18-codex-instruction.md](18-codex-instruction.md).
