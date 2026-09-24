# Independent review 2: Tiberius speed, grounding and retrieval

**24 September 2026 · Reviewer: Claude (Review, then Build) · Status: accepted by the Human, who assigned the remediation to Claude.**

This review covers everything delivered since review 1 ([16-independent-review](16-independent-review.md)): documents 19–40, the 25 commits on `codex/sme-conversation-pace` up to `1bc1056`, the live Tiberius services on ports 8773 and 8780, and the timing database the live service writes. None of those 25 commits had been through the ADO pipeline, because the branch was never merged or raised as a pull request.

The Human's decisions on 24 September:

- Claude owns delivery of every improvement except the licence item.
- The commercial licence question for the Higgs voice is **deferred**. The work is still an evaluation, and the licence is revisited once the speed and safety fixes land.
- **Higgs stays the live voice.** The fix is to make Higgs fast, not to replace it.

## Verdict

1. **Too slow for the G1.5 gate by a factor of three to six.** The median time from the end of the user's speech to Tibi's first audio is **4.6 s** across all recorded microphone turns, and **9–10 s** since the Higgs voice went live. The G1.5 target is 1.5 s.
2. **The delay is structural.** Every stage waits for the previous one to finish completely:
   - endpointing waits a fixed second;
   - the model reply is generated in full, inside JSON, before anything else happens;
   - Higgs renders the whole reply (or its first sentence group) before any audio is released.
   No stage overlaps with the user's own speaking time.
3. **The grounding claim does not hold on the live path.** The live service uses the layered companion. A reply the model labels conversation or general is spoken unchecked unless it contains the literal word "OpsAtlas". Product wording is generated, and is checked only for which records it cites, not for what it says. The evidence review runs only after the audio has played, and an interruption cancels it without trace.
4. **Tiberius bypasses OpsAtlas retrieval.** It places the first 24 enabled records in the prompt and silently drops the rest, while the platform's hybrid retriever (BM25 + embeddings, reranking, relevance threshold) goes unused.

## Where the time goes (measured)

The figures below come from the live timing database (`.runtime/opsatlas-sales/voice/timings.sqlite`): 49 microphone turns across nine sessions, 21–24 September.

| Stage | Median | Range | Cause |
|---|---|---|---|
| End of speech → endpoint | 1.12 s | 1.07–8.85 s | `TurnBoundary.complete` needs two positive checks and at least 16 000 samples (1.0 s) of silence, however confident the turn model is |
| Endpoint → final transcript | 0.12 s | 0.07–0.47 s | Resident whisper.cpp `small.en`; not a problem |
| Reasoning | 1.53 s | 0.94–4.50 s | Every call uses `stream: False` inside a JSON schema. Product turns can need two calls in sequence. The reply only starts once the final transcript arrives. |
| Synthesis to first audio: Chatterbox sessions | 0.3–0.9 s | 0.14–3.28 s | |
| Synthesis to first audio: Higgs sessions | 5.5 s | 3.0–12.5 s | `model.generate(..., stream=False)` over the whole reply or its first sentence group |
| First audio → playback | 0.01 s | | Not a problem |
| **Total, end of speech → playback** | **4.57 s** | **1.37–18.02 s** | **Higgs sessions only: median about 9 s** |

The local model was profiled directly as well (`qwen3.5:4b` via Ollama, 24 September):

- Cold load is 2.8 s. The 5-minute `keep_alive` lets the model unload between sessions.
- A warm conversational reply takes 0.9–1.8 s to generate at about 55 tokens/s.
- The first token arrives after **40–70 ms**.

Streaming alone therefore recovers most of the reasoning share. Roughly 30 of the 55–95 generated tokens are JSON keys and routing fields emitted before the first word of the reply.

## Target latency budget

| Stage | Budget |
|---|---|
| Endpoint | 0.35–0.45 s (confident turn-end, silence floor about 0.3 s) |
| Recognition | 0.12 s |
| Reply, first speakable clause | ≤ 0.4 s, mostly overlapped with the endpoint wait by preparing from the settled partial transcript |
| Speech, first audio chunk | ≤ 0.3 s for generated speech via streamed Higgs decoding; about 0.05 s for pre-rendered approved answers |
| **End of speech → first audio** | **≈ 1.2 s at p50** |

## Improvements (all assigned to Claude except item 22)

The ADO IDs appear in [ado-links.json](ado-links.json) under `SME-F18` and `SME-S127` to `SME-S149`.

### A. Speed

1. **S127:** stream the turn end to end, from model tokens to speakable clauses to Higgs chunks to playback, with cancellation on barge-in.
2. **S128:** stream Higgs audio in chunks, reusing the fixed voice prompt, so first audio does not wait for the whole reply.
3. **S129:** pre-render approved product answers in the Higgs voice. Only approved record text, or spoken variants a human has approved, are pre-rendered. They are invalidated when a record's hash changes.
4. **S130:** close a confident turn after 0.3–0.4 s of silence, and keep the long wait only when the turn model is unsure.
5. **S131:** prepare Tibi's reply, and its first audio, from the settled partial transcript. Nothing is spoken or committed before the endpoint.
6. **S132:** decide the route first, then stream the spoken reply as plain text rather than as a JSON field.
7. **S133:** keep the models resident for the session and warm them before the microphone opens.
8. **S134:** keep the background evidence check away from the foreground turn. It yields to the user's speech and resumes rather than being dropped.

### B. Grounding and safety

9. **S135:** send every product-related or uncertain turn through the evidence layer. There is no literal-word escape hatch.
10. **S136:** verify spoken product wording against the cited records before speech. Numbers, prices, percentages, standards, capability claims and negations must be supported.
11. **S137:** product answers are checked before they are spoken. An interrupted check is recorded, never silently lost.
12. **S138:** the product interviewer sees only enabled records.
13. **S139:** planned and not-yet-verified qualifiers survive paraphrase into the spoken answer.

### C. Retrieval

14. **S140:** retrieve product evidence through the OpsAtlas hybrid retriever over enabled records only, with a relevance threshold.
15. **S141:** replace the keyword routing lists and hard-coded record IDs with similarity to the actual records.
16. **S142:** cache the enabled catalogue by content hash, and revalidate before speech.

### D. Architecture and engineering

17. **S143:** collapse Companion, SalesCompanion and LayeredCompanion into one explicit turn pipeline. Tests must exercise the path the live service runs.
18. **S144:** restore the core Avatar prompt (`src/assistant/avatar/style.py`). Tibi-only delivery rules stay in the voice service.
19. **S145:** make the branch CI-green on Python 3.11 and deliver it through a pull request. `asyncio.wait_for` swallowed an interruption's cancellation on Python 3.11, so a cancelled reply could keep running under CI.
20. **S146:** separate the experiment and voice-rating pages from the live Tiberius service. They must not write into the shared runtime from the sales service.
21. **S147:** build an automated replay latency harness: at least 100 turns, per-stage p50 and p95, run on demand against a disposable workspace.

### E. Governance

22. **S148 (Human, deferred):** the commercial licence and speaker-consent decision for the Higgs voice. The downloaded Higgs, Fish and Breeze licences permit evaluation only. This is revisited after the fixes land.
23. **S149:** reconcile ADO, the README and `backlog.json` with the delivered work. This includes the 21 September work that has no ADO record, and the move to a sales companion.
