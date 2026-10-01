# Independent audit of 27 September 2026: remediation

ADO Feature #1862 (Bugs #1863–#1871, #1874; Tasks #1872, #1873). The audit is in `docs/audits/2026-09-27-opsatlas-tibi-audit.md`,
with its probes in `evaluation/evidence/audits/2026-09-27/`. Branch `claude/audit-remediation`, engine 1.4.0.

## Assessment

The audit was fair and consistent with how OpsAtlas is governed: nothing is approved automatically, and Tibi says
only what the Human approved. All twelve findings reproduced on the reviewed head. They also reproduced on the later
head, d1a0428, which added the Digital SME on engine 1.3.0. Every probe is now a regression test.

The audit advised building the Digital SME only after the evidence fixes. It was delivered before the audit was read.
It uses Tibi's engine, so every engine fix below covers both channels.

## What changed

| Finding | Change | Evidence |
|---|---|---|
| F01 P1 Editing evidence kept approvals | A record's approval records the evidence versions it was given against. If a supporting document's words change, the records citing it show **Reconfirm** and are unavailable until the Human enables them again. A formatting-only change keeps approval. The answer digest covers the evidence versions. | `test_a_changed_supporting_document_withdraws_the_records_citing_it_until_reconfirmed`, the reformatting test and the start-up binding test. The audit's probe through the publish API now leaves the record unavailable and changes the digest. |
| F02 P1 Stale evidence reached audio | Every evidence-based reply is authorised against the current evidence before delivery. This covers the approved-wording fallback, answers prepared while the participant spoke, and Digital SME replies. If the evidence service can't be reached, Tibi refuses. **Policy:** an answer authorised at its start is delivered whole; a change during it applies from the next answer. | Fallback, prepared-answer and text-channel tests. Both audit probes now refuse. |
| F03 P1 Lexical checks let unsupported facts through | The question's figures support only a denial. A figure must keep what it counts ("10 teams", "2 weeks"). Figures in words equal digits. "In the proof of concept" is a place, not a qualifier. In a product answer, a sentence with content of its own must share its wording with a record or fact, or approved wording is spoken instead. One gate (`tibi.sentence_gate`) serves the voice, the Digital SME and the evaluation. | Labelled suites in `evaluation/`: see the table below. |
| F04 P1 Ontology facts outlived their records | Capabilities, components and limitations hold only while their records are at the version they were curated from, or at a version the Human confirmed. **Confirm it still holds** is under Tibi Knowledge › Product ontology. Topics and aspects only route questions, so edits don't withdraw them. The ontology revision is part of the answer digest. | The ontology and end-to-end API tests. The audit's probe yields no stale limitations. |
| F05 P1 An old decision withdrew a corrected record | An answer records every source's version, content and approval when it is proposed. Approval re-checks them, and a changed answer becomes **stale** without being applied. A finding whose statements were edited no longer stands. The record decision is applied before any issue closes. | Stale, withdrawn and deleted, and failed-decision tests. |
| F06 P2 Changes during a review were dropped | A request during a running review queues exactly one follow-up review, which reads the newest revision. Status shows the reviewed and current revisions. A failed review keeps a queued change visible. Results are written atomically. The Governance tile says when a review will run again or is out of date. | Coalescing and failure tests. |
| F07 P1 The scorecard overstated grounding | "grounded" became "supported" (every statement passes the gate), and "grounding precision" became **citation coverage (lexical)**. Other changes: <ul><li>Abstentions are scored apart.</li><li>Length limits apply to approved wording too.</li><li>Fallback rate, abstention rate and blocked sentences are reported.</li><li>Rehearsal is measured apart from conversation.</li><li>Sample sizes and the scenario file's hash are stamped.</li><li>The judge sees the records.</li><li>A held-out name test was added.</li><li>The replay has a rehearsal mode.</li><li>The control panel's own client is tested in CI.</li></ul> | `test_sme_scorecard.py`, `test_sme_voice_client.mjs`, `evaluations/2026-09-27T1924-wake-heldout.*`. |
| F08 P2 Interrupted turns vanished from the log | Every accepted turn writes one outcome: completed, interrupted, refused, failed (with the stage) or abandoned. An interrupted reply records what was sent apart from what was planned. The transcript keeps only what was heard. | Five-outcome test. The audit's probe logs one turn with the delivered prefix. |
| F09 P2 End didn't cancel a pending start | Each start checks it is still current after every awaited step. A late session is paused on the service, never connected. A stale start's failure can't overwrite state. Signing out ends Tibi. | `tests/test_sme_voice_client.mjs` drives `frontend/src/tibi/voice.ts`. Three of its four tests fail on the old code. |
| F10 P2 Engine identity was incomplete | The service records a manifest at start: <ul><li>code components and the Git commit;</li><li>Ollama digests;</li><li>recogniser, speech-detection and voice-reference hashes;</li><li>the Higgs revision and precision;</li><li>settings, platform and packages.</li></ul> It is at `/api/manifest` and in `logs/manifests`. Health says when the code on disk differs from what is running. Scorecards and replays carry the manifest. | `test_sme_manifest.py`. |
| F11 P2 The 50-session stop | Once 50 conversations are in use, the oldest ended ones are archived, then any untouched for an hour. Nothing is deleted, and archived sessions stay readable and their contributions visible. The service refuses a new conversation only when 50 are genuinely in use. | 60 start/end cycles. |
| F12 P2 The rehearsal's retention promise | The opening says the meeting isn't kept without a transcript, and that requests and replies are logged. The side panel lists what is kept. Without a transcript, a blocked sentence's wording is not logged. | A distinctive phrase checked across every stored file, with the transcript off and on. |

## Measured, as measured

**Sentence gate** (`tests/test_sme_sentence_gate.py` keeps these results as floors):

| Set | Unsupported blocked | Faithful allowed |
|---|---|---|
| Adversarial: the audit's 3 cases, plus cases written with the fix, which shaped it | 14 of 17 | 9 of 9 |
| Held out: written before the fixed gate was run, not tuned | 6 of 9 | 7 of 7 |

The misses are what a lexical check cannot see:
- a change of subject ("approved by Tibi" instead of by a person);
- a change of scope ("any laptop", "in every organisation");
- modality on words outside the claim vocabulary ("An audit export is available now" when it is planned).

Closing these needs a semantic check, which must itself be evaluated, and must not approve knowledge.

**Held-out name test** (10 voices, phrases never used to change the rules, run once):

| Measure | Result |
|---|---|
| Name recognised | 79 of 80 |
| Right kind of help | 46% |
| Accidental triggers | 1 of 100 |
| Two speakers | 100% |
| Own voice as echo | 100% |

- **The accidental trigger** was the recogniser hearing "Toby" as "Tibi", not the rule.
- **The kinds of help** are recognised too narrowly. These phrasings fall back to a plain question:
  - "How would you answer that?"
  - "Anything I've forgotten to mention?"
  - "Help me with that one"
  - "What's a good example for…?"

  Improving this needs its own tuning set and a fresh held-out set (follow-up).

**Engine 1.4.0 scorecard** (`evaluations/2026-09-27T1934-engine-1.4.0.*`; same knowledge as 1.3.0, 56 turns, 2 runs):

| Measure | 1.4.0 | 1.3.0 |
|---|---|---|
| Routing accuracy | 1.00 | 1.00 |
| Appropriateness | 0.985 | 0.988 |
| Rehearsal appropriateness | 0.952 | (not separated) |
| Citation coverage (lexical) | 0.974 | (not measured) |
| Fallback rate | 0.154 | (not measured) |
| Abstention rate | 0 | (not measured) |
| Blocked sentences | 10 | (not measured) |
| First sentence, median | 524 ms | 464 ms |
| First sentence, 95th percentile | 1,311 ms | 1,130 ms |

**What the measures show:**
- **The blocked sentences.** Every one was an unsupported second sentence after a supported first sentence, for
  example "This ensures your data stays secure and up-to-date", a security claim no record makes. No faithful
  sentence was blocked.
- **The slower first sentence.** The changes add nothing to that path: the evidence check applies only to fallbacks
  and prepared answers. The scorecard ran straight after Ollama was restarted, and the latency replay below is the
  voice's measure.
- **The two failures.** They are the length limit now applying to approved fallbacks (a long record read out in full)
  and the known example-content gap from guide 51.

**Latency replays for engine 1.4.0** (disposable copy of the live workspace, the other project's model server idle):

| Replay | Turns | First audio, median | 95th percentile | Errors |
|---|---|---|---|---|
| Chat (`2026-09-27T2042-latency-replay-engine-1.4.0.json`) | 40 | 1,479 ms | 1,833 ms | 0 |
| Chat, engine 1.3.0 for comparison | 40 | 1,501 ms | 1,723 ms | 0 |
| Rehearsal requests, first measured (`...T2052-latency-replay-rehearsal-engine-1.4.0.json`) | 20 | 1,909 ms | 2,119 ms | 0 |

- **Budget.** Both replays are within the budget (1,950 / 3,100 ms). The rehearsal requests' median is close to it
  because they are not prepared while the salesperson speaks.
- **Meeting lines.** The rehearsal replay's 12 meeting lines were all heard and none was answered.
- **Manifest.** Each replay records the manifest it measured (F10).

## Delivered is not accepted

- Engine 1.2.0's latency replay passed its non-regression budget. That is not G1.5 (#1590), which still needs a p50
  of 1.5 s or less over at least 100 turns, the Human's ten-minute rating, and no fabricated spoken facts.
- Feature #1695 and rehearsal #1844 are Resolved as delivered code. Their acceptance still needs the Human:
  - a sustained rehearsal with interruptions on the Jabra (guide 51);
  - a replay in `--rehearsal` mode.

## For the Human

1. Restart Ollama, the local model server for OpsAtlas (the Ollama app), so the scorecard and replay can run, and so
   Tibi and the Digital SME can answer.
2. After the merge, check **Tibi Knowledge**:
   - records shown as **Reconfirm**, whose evidence was edited after you enabled them;
   - **Product ontology › Withdrawn until you confirm them**, for records you edited since the facts were written.

   These are expected: they are the audit's point.
3. The Jabra protocol in guide 51, including a sustained pitch with interruptions.
