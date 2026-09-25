# Review 2 delivery: a streamed, grounded Tibi and measured latency

**24–25 September 2026 · Built by Claude (owner of Feature #1695) · Status: delivered for the Human's evaluation; nothing is merged to `main` until the Human accepts it.**

This records the delivery of every improvement in [independent review 2](41-independent-review-2.md) except the voice licence (#1717), which the Human deferred while Tiberius remains an evaluation. **Higgs remains the live voice**; it is now streamed rather than replaced. The work is on branch `claude/tiberius-speed-safety`, raised as a pull request to `main` so that the ADO pipeline runs on Python 3.11.

## Result

Across 100 replayed turns on the live turn path with the Higgs voice, the median time from the end of speech to Tibi's first audio is now **1.82 s (p95 2.89 s)**. Before, it was a median of **4.6 s over 49 live turns, and about 9 s once Higgs went live**. There were no errors in 100 turns, and every reply was prepared from the participant's settled partial transcript.

- 71 of 100 turns started within 2.0 s; 2 started within 1.5 s.
- By route: product answers had a median of 1.74 s, conversation 1.89 s, and general knowledge 2.71 s. The general-knowledge figure was fixed after the run; see below.
- **The G1.5 latency target (p50 ≤ 1.5 s) is not met with full-precision Higgs.** Streaming removed the whole-utterance wait. What remains is structural: preparation starts about 0.3 s after speech ends, the first checked sentence is ready about 0.58 s later, and Higgs needs about 0.78 s for its first audio chunk. That chunk is 21 model steps: 6 frames of audio, 7 frames of codebook delay and 8 frames of look-ahead for clean joins. The options that close the gap are listed under "What remains".
- **With approved spoken answers** (drafted and approved inside the disposable copy only), a 40-turn replay on the final code measured a median of **1.60 s (p95 1.97 s)**. Product answers had a median of 1.51 s, and pre-rendered answers started in 0.44–0.88 s. Approved-wording fallbacks fell from 16% to 5% of turns, and general answers from 2.71 s to 1.97 s, after the final fixes (bounded recall, questions not treated as claims, no widened capabilities).
- The replay ran while another local application's model server, unrelated to OpsAtlas, held about 28 GB and was computing (50–134% CPU sampled). The slow patches around turns 61–80, in two separate runs, coincide with it. These figures are therefore conservative for Tiberius running alone. It was not touched.

## What changed in a turn

| Stage | Before (live, 49 turns) | Now | How |
|---|---|---|---|
| End of speech → endpoint | 1.12 s median (1.0 s silence floor) | 0.38 s median (p95 0.74 s) | A confident turn-model prediction ends the turn after 0.3 s; two positive predictions after 0.5 s; companion turns also end after a 1.6 s pause (#1699) |
| Endpoint → final wording | 0.12 s, plus a 0.2–0.5 s beam re-decode under load | 0.42 s median after end of speech, including the endpoint | A settled partial that covers all speech is the final wording; recognition vocabulary for product names (#1700) |
| Reasoning | 1.5 s median, non-streamed JSON, sometimes two calls | first speakable sentence 0.95 s median after end of speech (0.58 s after preparation starts) | Route first, stream plain text, speak sentence by sentence; prepare from the settled partial; pre-warm evidence prompts during speech; faster measured model (#1696, #1700, #1701, #1702) |
| Speech → first audio | Higgs 5.5 s median (whole utterance), up to 12.5 s | Higgs first chunk 0.62–0.75 s alone | Step-by-step generation, cached voice prompt, chunked codec decode with context and look-ahead; in-worker cancellation (#1697) |
| **End of speech → first audio** | **4.6 s median; about 9 s with Higgs** | **1.82 s median, p95 2.89 s (100 turns, Higgs)** | |

## Delivered, by story

**Speed**
- **#1696 Stream the turn (S127).** `tibi.py` streams the local model's reply and yields each sentence as soon as it passes its checks. `continuous.py` speaks the first sentence while later ones are synthesised in the same worker queue, as one utterance (`speech`, then `speech_append`, then `audio_end`).
- **#1697 Stream Higgs (S128).** `higgs_voice.py` drives the model frame by frame and prefills the fixed reference prompt once. It decodes codec frames in chunks with 16 frames of context and 8 of look-ahead: 48–56 dB SNR against a whole-utterance decode, with no underruns in a real-time playback simulation. Shorter look-ahead was measured and rejected (20–36 dB at the first join). A request-scoped cancel stops synthesis in about 8 ms, so a barge-in no longer kills and reloads the 12 GB worker. First audio is 0.62–0.75 s regardless of reply length, against 3–12.5 s before.
- **#1698 Pre-rendered approved answers (S129).** Spoken wording is drafted by the local model, checked against its record by the core, and stays pending until approved in Knowledge review → Spoken answers. It is withdrawn when the record changes. Approved wording is rendered in the live voice while Tibi is idle, and replayed from a bounded cache for broad questions.
- **#1699 Confident endpointing (S130).** See the table above.
- **#1700 Prepare from partial transcripts (S131).** The reply, and the first sentence's audio, start at the settled partial and are adopted only when the final wording matches exactly. Nothing is spoken, committed or saved before that. While the participant is still speaking, product questions pre-load their retrieved records into the model's prompt cache.
- **#1701 Route first, stream plain text (S132).** Routing is decided before generation. The conversation model writes one tag line (`OK`, `PRODUCT`, `REPEAT`, `CONFLICT | … | …`) and then plain text; evidence answers are plain text.
- **#1702 Resident models (S133).**
  - `qwen2.5:7b-instruct` prefilled a 440-token prompt in 56–104 ms and generated 80–89 tokens/s; `qwen3.5:4b` took 355–605 ms and managed 45–66 tokens/s on this Mac.
  - Keep-alive is 30 minutes, and both system prompts plus the check model are warmed before listening.
  - Every request uses one context size, because a different `num_ctx` makes Ollama reload the model.
  - One Higgs worker is shared across reconnections instead of a 5 s, 12 GB reload per session.
- **#1703 Background checks (S134).** Ollama serves one request at a time per model: a reply waited 3.3 s behind a long request on the same model, and 0.8 s beside one on another model. Checks therefore run on their own warmed model (`qwen3.5:4b`), keep running while the participant speaks, and pause only when a reply is being prepared. An unfinished check is recorded as unavailable at session end, never dropped.

**Grounding** (`services/opsatlas_sales/claims.py`, `tibi.py`)
- **#1704 Every product-related turn goes to evidence (S135).** Product names, generic claim vocabulary (commercial, assurance, security, deployment, integration, customers, timeline), capability questions about "it" or "you", follow-ups to product answers, and close record similarity all route to evidence. Uncertain turns default to evidence. Addressing Tibi by name is not a product question. A conversational sentence that makes a product claim is never spoken; the turn re-routes. Review probes such as "How much would it cost us per year?" and "Is the platform secure enough for a bank?" now reach evidence without naming OpsAtlas.
- **#1705 Wording verified against the records (S136).** Every evidence sentence is checked before speech: figures, currency, acronyms and standards must appear in the retrieved records, claim terms must be present, and a clause-aware check stops a term the records negate from being spoken affirmatively. The first unsupported sentence stops generation. If nothing was spoken, approved wording is spoken instead. Tests pin 16 blocked probes and 16 faithful paraphrases.
- **#1706 Checked before speech (S137).** No generated product sentence reaches speech unchecked. The digest of enabled evidence is revalidated before the first sentence, and a change speaks a retry message. The secondary model check (#1703) raises any concern in the next turn.
- **#1707 Interviewer sees enabled records only (S138).**
- **#1708 Qualifiers survive (S139).** An answer citing a planned, experimental, uncertain or unknown record says so; a qualifier is spoken first when the model drops it.

**Retrieval**
- **#1709 Platform retriever (S140).** `/api/sales/search` ranks every enabled record with the platform's BM25 + embedding fusion and relevance threshold. Nothing is truncated; relevant records come first. The ranking strips punctuation and conversational filler, and indexes each record's curated topic keywords: "cost" now finds the commercial record, which previously ranked fourth.
- **#1710 Routing by similarity (S141).** The hard-coded `overview`/`process` IDs, the forced "how does it work" mapping and the transcript-specific phrase lists are gone. Thresholds were calibrated on nomic-embed-text against the eight records and are documented in `tibi.py`.
- **#1711 Cached catalogue (S142).** Enabled records and usable spoken answers are cached by a content digest and revalidated before speech.

**Architecture and engineering**
- **#1712 One pipeline (S143).** `Companion → SalesCompanion → LayeredCompanion` and `sales_dialogue.py` are replaced by `tibi.py`, the path the live service runs, with 23 pipeline tests and 9 orchestration tests.
- **#1713 Core Avatar prompt restored (S144).** Tibi's delivery rules live in `services/sme_interviewer/spoken_style.py`.
- **#1714 Python 3.11 (S145).** On 3.11, `asyncio.wait_for` could swallow an interruption's cancellation, so a cancelled reply kept running under CI. It is replaced with `asyncio.timeout`. Delivered through a pull request.
- **#1715 Experiments separated (S146).** The rating pages moved to `experience/voice_ratings.py` on port 8774; the live sales service no longer mounts them. See the cleanup list below.
- **#1716 Replay harness (S147).** `replay_latency.py` speaks 20 questions (macOS British system voices) through the browser websocket protocol in real time. It runs against a disposable copy of the sales workspace on ports 8790/8793 and writes per-stage evidence. The Human's live services and conversations are never touched.
- **Recognition vocabulary.** The native recognizer accepts an optional vocabulary prompt. Replayed audio went from "What is all sadness?" to "What is Ops Atlas?", and from "Tell me about TB" to "Tibi".

**Governance**
- **#1717 Licence (S148):** deferred by the Human; unchanged.
- **#1718 Reconciliation (S149):** the README index and voice record, `backlog.json` states and the F18 items, ADO comments for the 21 September work that had no record, and a Handover Log entry.

## Evidence

- `evidence/2026-09-25/latency-replay-100.json`: 100 turns, per-stage client timings, server marks (routing, first token, first sentence), route, grounding, the spoken reply and any blocked sentences.
- `evidence/2026-09-25/latency-replay-40-approved.json`: 40 turns with approved spoken answers pre-rendered (disposable workspace only).
- `evidence/2026-09-25/higgs-q8-comparison.json`: timings for an 8-bit Higgs backbone. The A/B clips are in `.runtime/higgs-q8-comparison/` (git-ignored). Not adopted; for the Human to hear.
- Tests: 864 Python tests pass on Python 3.11 (CI) and 3.12, Ruff passes, and 58 browser tests pass.

## What remains, honestly

1. **The 1.5 s latency target.** With full-precision Higgs, the first audio chunk is the floor: about 0.6 s alone and about 0.78 s while the reply model is still generating. Three levers remain, and each is your decision:
   - **Approve spoken answers.** This needs no code change. Broad product questions then start in under 0.9 s, and the measured median drops to 1.60 s.
   - **Switch Higgs to 8-bit weights.** Set `SME_HIGGS_BITS=8` before `scripts/start-tiberius-sales.sh`. Measured 1.45× faster, with first audio 0.34–0.44 s instead of 0.59–0.62 s, which should save about 0.2–0.25 s per turn. The same voice reference and settings are used, but it is not the exact voice you accepted, so listen to `.runtime/higgs-q8-comparison/bf16-*.wav` against `q8-*.wav` first.
   - **Run Tiberius without the other local model server competing for the GPU.** That server belongs to an application outside OpsAtlas and was left untouched.
2. **G1.5 remains a Human gate.** The replay proves the pipeline end to end, but it is not a headset conversation, a rating or ten unscripted minutes. It uses macOS system voices, and the harness acknowledges audio as it arrives rather than after playback.
3. **Recognition.** 85% of replayed questions were transcribed exactly. The vocabulary prompt fixed the product names, but "Can it draw process diagrams?" was still heard as "Can it all process diagrams?" with the synthetic voice.
4. **The claim checker is deliberately conservative.** It is a vocabulary-and-negation check, not an entailment model. It blocks figures, standards, claim terms and negated capabilities that the records do not support, but a novel capability outside its vocabulary relies on the evidence prompt and the secondary model check.
5. **Conversation persona.** The 4–7B local models sometimes describe having "a busy week". The prompt forbids invented experiences, and this is not a product claim.
6. **The voice licence (#1717)** is deferred by your decision.

## Trial models you can remove

These audition models are not used by the live Tiberius path. They total about 34 GB. Nothing was deleted; remove them yourself if you no longer need the auditions:

```
services/sme_interviewer/.runtime/experience/audition2-fish        11 GB
services/sme_interviewer/.runtime/experience/personaplex-mlx        9.1 GB  (CC BY-NC)
services/sme_interviewer/.runtime/experience/audition2-breeze       7.1 GB
services/sme_interviewer/.runtime/experience/personaplex-official   4.2 GB  (CC BY-NC)
services/sme_interviewer/.runtime/experience/qwen-base              1.6 GB
services/sme_interviewer/.runtime/experience/speech-swift           1.2 GB
```

Keep `audition2-higgs` (the live voice), `chatterbox`, `pocket`, `references`, `listener` (turn model) and `s3tokenizer`.

## How to evaluate

1. Restart the services so they run this branch: `scripts/start-tiberius-sales.sh stop`, then `scripts/start-tiberius-sales.sh`.
2. In Knowledge review, choose **Draft spoken wording for enabled records**, read each draft and approve the ones you are happy to hear. Tibi renders them in the Higgs voice while idle; broad questions are then answered instantly.
3. Talk to Tibi with a headset. The session's timings still record in the browser; `turn_marks` in each saved exchange records routing and first-sentence timing.
4. To re-measure: `services/sme_interviewer/.venv/bin/python -m services.sme_interviewer.replay_latency --turns 100`, optionally with `--approve-spoken`.
