# Conversation pace candidate — 20 September 2026

This candidate improves the continuous voice path on the Mac Studio, but **does not pass G1.5**. It remains on the isolated preview at `http://127.0.0.1:8768/conversation`; the main service on 8767 has not been replaced. British Voice B and local-only inference remain in use. No acceptance story is closed by these development results.

## Implemented

- One local 35B call interprets an answer and prepares a short follow-up. The existing structural, source, revision, number and name checks remain before speech. A bounded repair cannot change the accepted answer interpretation. Failed questions leave captured wording available instead of asking the participant to repeat a successfully captured answer.
- Planning starts after a 200 ms settled speech pause rather than repeatedly cancelling inference for every partial transcript. Final recognition is reused only for the same generation and last-voice sample, with sufficient trailing silence. Exact matching speculative speech remains silent until the turn is authorised; stale work is cancelled and buffers are bounded.
- Semantic question review runs after speech delivery and is saved with question provenance. Recap waits for a cancelled reply to register its review, and confirmation awaits outstanding review. Concerns remain advisory: a question review neither confirms wording nor approves participant facts. A failed or unavailable review remains visible in draft provenance.
- GPU Kokoro uses the existing British `bf_isabella` vectors, phonemizer, trimming and pause rules. Optional model artifacts are pinned and checksummed. Speech runs in the existing network-denying worker sandbox. A 256 MiB free-buffer cache target and 2 GiB allocation guideline constrain caching; neither is a hard memory cap. ONNX remains the default unless the GPU backend is explicitly selected.
- Cancelling short synthesis drains its bounded in-flight work where possible, retaining the warm worker. The browser handles either ordering of playback drain and server completion, so automatic playback can return to listening reliably. Committed speech is not cut short simply because another question becomes ready; actual interruption and Pause still cancel it.
- Explicit spoken controls bypass inference and are not joined to unfinished answers. A generic near-duplicate check rejects questions produced merely by deleting words from an earlier question. The planner is constrained to currently available topics. This is not a general semantic repetition solution.
- Synthetic rehearsal now accepts a sequence of fictional WAVs, advancing only after speech drains. No physical microphone is used in this mode.

## Measurements

All retained evidence is fictional development data in [the pace evidence directory](evidence/2026-09-20/pace/). These are small, unpaired runs, not an untouched holdout or human quality rubric.

| Browser rehearsal | Audible responses | Detected speech-end to rendered audio p50 / p95 |
|---|---:|---:|
| Before scheduling fix | 5 | 4,224 / 11,546 ms |
| CPU after scheduling fix | 5 | 2,658 / 2,720 ms |
| Initial GPU candidate | 5 | 2,244 / 3,473 ms |
| Final topic-constrained GPU candidate | 5 | **2,379 / 3,485 ms** |

The final run used six WAVs: five fictional answers and a spoken recap command. All five answers were retained provisionally, then confirmed together and saved as a draft through the browser. Four replies were follow-ups (including a guided unknown/source invitation); one was recovery speech after a rejected question. The five-response timing distribution **includes that recovery**, not five successful contextual questions. The recap control is an interrupted timing record. First-audio delivery p50/p95 was **151/222 ms**. Playback means browser rendering, not sound arriving at the headset. The rehearsal travels through the microphone PCM path and is labelled `microphone` by the timing store; its actual source was synthetic WAVs. Residency and first-token timing remain unknown/null. Near-zero final-recognition delivery reflects reuse of a completed partial, not near-zero ASR compute.

A separate sandboxed GPU voice probe produced first audio at 164, 157 and 291 ms for two short questions and a sterling/negation passage. Recognition of that generated audio preserved “£15,000, not £50,000” and the before-activation condition. A whole 20.46-second recap paragraph took 924 ms to its first batch; the live recap path splits sentences. This is a development intelligibility check, not a listening score or proof of perceptual equivalence.

## Concurrent local workload

The final bounded probe ran five synthetic Atlas Ask requests alone and then alongside 35 GPU speech batches, five resident ASR calls and five local 35B planning calls. Atlas p50/p95 rose from **332/487 ms** alone to **582/890 ms** concurrently. All five plans produced a checked question. ASR took 132–231 ms; planning took 1,487–3,161 ms. Speech whole-utterance synthesis p50/p95 was 293/429 ms. These are different boundaries from browser turn-gap timing.

Minimum system-available memory was 16.63 GiB alone and **13.99 GiB** concurrently. Existing swap was 12.50 GiB with **no observed growth during either measured condition**. Peak MLX speech allocation reported by the worker was 2.11 GiB, demonstrating that its 2 GiB setting is a guideline. An earlier unbounded-cache run fell to 3.65 GiB available and reached 26.26 GiB swap; its evidence is retained, but other application state and run order prevent attributing all of that difference to the cache change. Another intermediate compact-planner run rejected all five plans and is explicitly not final success evidence.

This test uses one approved fictional Atlas document, lexical retrieval and a resident 7B answerer. VAD is resident but receives one frame per turn; it is not a complete microphone-throughput or production Atlas capacity test. Five requests per condition cannot establish a capacity gate.

## Quality findings and rejected experiments

The final labelled routing development set matched all expected fields in **17/19** cases. A coherent related detour was incorrectly classified off-topic; garbled wording was correctly classed unclear but rated finished rather than cut off. The latter still takes the clarification path. Nineteen generated questions and two pending recoveries occurred across 21 attempted turns in six seeded multi-turn scenes. The fallible background reviewer flagged 10 of 16 model-generated questions it assessed; these are not ten independently established errors. Some flags were false positives, including an allegation that a buyer's order was assumed when it was explicitly stated.

Unresolved real failures include re-asking an unknown detail, asking for a more specific person after a team has been supplied, implicit assumptions about completion, and paraphrased repetition that survives a lexical duplicate check. The final browser run also needed one recovery after exhausting its bounded question repair. **Naturalness and pace rubric scores remain unmeasured; no ten-minute human gate has passed.**

Rejected candidates and their evidence are retained:

- The smaller 4B router traded speed for classification mistakes.
- Removing planning metadata reduced generation time but worsened premises/repetition.
- A fixed-position compact JSON array reduced decode work but misclassified valid answers and repeatedly produced rejected questions. It is not used.
- A cache-stable topic enum allowed already-covered topics and unnecessary repairs. The final response schema restricts the topic to remaining gaps, accepting some prefill cost.

A vector database would not remove the measured model-generation and voice delays in this bounded conversation. Retrieval for real Atlas evidence remains separate work. The next semantic evaluation should challenge the local planner/model configuration and how it represents answered, unknown, intended and completed events, rather than add more supplier-specific guards. Keep the independent holdout untouched.

## Validation and operation

697 root Python tests, 247 isolated-service Python tests and 43 browser/AudioWorklet tests pass. Ruff and whitespace checks pass. The frontend production build passed earlier in this batch; subsequent changes are confined to the isolated service and its documentation/tests. Existing dependency warnings remain. Automated checks cover revision/provenance, stale generation rejection, bounded preparation, explicit controls, capture preservation, deferred review, recap cancellation and playback message ordering. They do not certify acoustic barge-in or human naturalness.

See [service setup and probe commands](../../../services/sme_interviewer/README.md#pace-candidate-optional-gpu-voice-b). Existing user sessions and the main running service are preserved. The optional GPU backend must be selected explicitly at startup. The current preview is a development candidate, not a promoted release.
