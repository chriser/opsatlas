# Tiberius: voice audition and reviewed improvement loop

24 September 2026. Research and audition iteration; live voice remains Chatterbox Turbo. Human preference and live-stream acceptance are open.

## Decision

Separate three questions: can the voice perform naturally, can the dialogue answer the intended question, and does approved evidence support the product claims? A new TTS model cannot correct an irrelevant or misleading answer. Audition natural native delivery first; then test the chosen candidate through live playback with ASR and reasoning running. Do not slow the waveform to compensate for a poorly delivered performance.

Local audition: http://127.0.0.1:8773/voice-benchmark . Eight passages include verbatim answers from Chris's transcript, proposed repairs, a greeting, technical names and a diagnostic amount/negation phrase. Original misleading statements are deliberately labelled voice-test material, not endorsed product facts. Proposed explanations are not automatically added to the approved corpus.

The page blinds model names until requested and records naturalness, pace, pronunciation and British-accent ratings plus notes and preferred wording. Audio plays only on request. Feedback stays in the ignored local runtime folder and carries the candidate identity and clip hash. It cannot mark itself eligible for training. Export includes cases, measurements and feedback. No microphone or training job is started by this page.

## Candidates and research

| Candidate | Why test it | Limits |
|---|---|---|
| Chatterbox Turbo 4-bit, current British reference | Current production baseline | Existing complete-sentence playback; style labels do not provide reliable emotion control |
| Chatterbox Multilingual V3, same reference | Revised model with native exaggeration and guidance controls | Different model performance may not preserve the preferred voice; must listen |
| Qwen3-TTS CustomVoice 1.7B, 4-bit and 8-bit, Aiden | Native delivery instructions; compare quantisation under identical directions | Instructing British English does not guarantee an authentic accent; precision alone is not a quality guarantee |
| VibeVoice Realtime 0.5B FP16, Frank | A different small streaming-oriented architecture | Preset accent must be assessed; prepared full-utterance clips do not demonstrate live streaming |

Chatterbox V3 and VibeVoice model cards report MIT; Qwen CustomVoice reports Apache 2.0. The existing British reference is reused, not a newly collected or impersonated speaker. Check upstream model and reference terms again before external distribution.

Sources: [Chatterbox official project](https://github.com/resemble-ai/chatterbox), [MLX V3 checkpoint](https://huggingface.co/mlx-community/chatterbox-multilingual-v3), [Qwen official project](https://github.com/QwenLM/Qwen3-TTS), [Qwen technical report](https://arxiv.org/abs/2601.15621), [Microsoft VibeVoice](https://github.com/microsoft/VibeVoice), [MLX VibeVoice checkpoint](https://huggingface.co/mlx-community/VibeVoice-Realtime-0.5B-fp16).

Other promising research options are not default commercial candidates: [Voxtral TTS](https://docs.mistral.ai/models/voxtral-tts-26-03) has non-commercial open-weight terms; [Breeze TTS](https://github.com/breezeblue-ai/breeze-tts) and [Higgs TTS 3](https://huggingface.co/bosonai/higgs-tts-3-4b) also require attention to research/non-commercial restrictions. [Fish Speech](https://github.com/fishaudio/fish-speech) remains a future hardware/runtime evaluation. Published vendor latency figures are not evidence of latency on this Mac.

## What the transcript reveals

| Observed failure | Likely layer or integration gap | Required change |
|---|---|---|
| Product interest becomes a pricing refusal | Intent misclassification | Resolve intent from the utterance and recent dialogue; do not invent a missing-evidence topic |
| Introduction starts with PoC/security disclaimers | Response construction | Explain capability first; qualify the claim when the limit affects it |
| “Sounds negative” becomes a factual contradiction | Conversational feedback handling | Recognise tone feedback and repair the explanation |
| “Atlas” becomes a secure offline notebook | Referent resolution and unsupported generalisation | Maintain product aliases/referents and route product claims through evidence |
| Upload method said to be unestablished | Missing approved technical coverage | Distinguish unavailable evidence from absent implementation; review a technical capability pack |
| Processing question triggers deployment interrogation | Relevance and excessive qualification | Answer the requested mechanism; ask scope only when necessary |
| Retrieval question gets ingestion answer repeatedly | Current-question tracking and repetition detection | Track the requested dimension (input, processing, use, model identity); reject a response that adds no relevant information |
| “My local memory” represents uploaded documents | System boundary confusion | Explain document retrieval separately from conversation memory and curated product cards |
| Exact model request receives another definition | Detail-level tracking | Use trusted runtime model metadata, not a guessed model name or functional paraphrase |
| Unclear fragment triggers an unrelated answer | Turn interpretation | Offer the floor or ask a narrow clarification |

These are diagnoses from observed behaviour and code inspection, not proven attribution to one model component. The [regression specifications](evidence/2026-09-24/tiberius-answer-regressions.json) preserve eleven scenarios with expected and forbidden behaviour. They are not yet an automated semantic evaluator or a passed evaluation of a new dialogue model.

## Verified technical boundaries and better answer targets

The isolated Atlas app configures `qwen3.5:4b` for local language generation, as does the companion. The core provider's default embedding model is `nomic-embed-text`; an environment override is possible, so this default must not be presented as a verified live deployment identity without checking configuration.

`src/assistant/ingestion/service.py` extracts text, builds sections, persists them and updates ingestion state. Plain extraction/sectioning does not itself require an LLM. `src/assistant/retrieval/service.py` builds a corpus from approved sources and supports BM25 lexical retrieval plus configured embedding similarity/fusion, with lexical fallback; optional rewrite/rerank settings are separate. The sales app disables rewrite and rerank. Tibi's current product path uses curated approved product cards; it is not yet an arbitrary uploaded-document search interface. See `services/opsatlas_sales/app.py`, `services/sme_interviewer/layered_companion.py` and `src/assistant/models/provider.py`.

Example targets for a reviewed capability pack:

- **What happens to documents?** “OpsAtlas extracts their text and organises it into stored sections. Approved material can then support retrieval. The language model uses selected evidence when constructing an answer.” Validate which indexing stages are enabled before claiming every document is embedded immediately.
- **How do I get information out?** “In OpsAtlas, you ask a question through its query interface and it retrieves relevant approved material. This Tibi demo currently answers from the curated product records; connecting it to the broader document search is still a separate step.”
- **Which model?** “This Tibi instance uses Qwen3.5 4B for language generation. The language model, embedding model and retrieval algorithm do different jobs. Let me distinguish those.” Only name the embedding deployment after trusted configuration lookup.
- **That sounds negative.** “Fair point. Let me explain what it helps you do first.” Then answer positively and accurately, without unrelated disclaimers.

These targets are code-informed review material, not silent additions to product truth. Prioritise an approved technical capability pack and trusted runtime identity tool, then a contextual intent/answer-quality evaluation. Avoid accumulating more keyword-triggered stock replies.

## Can we train the voice and sentence construction?

Yes, but they require different data and different models.

**Voice delivery:** first try native style instructions, a suitable reference performance and pronunciation guidance supported by the selected engine. A written correction alone cannot teach the acoustics of a pause, smile or sympathetic tone. Voice fine-tuning needs clean recordings of a consenting target speaker, accurate transcripts and varied desired performances. Qwen publishes [single-speaker fine-tuning instructions](https://github.com/QwenLM/Qwen3-TTS/blob/main/finetuning/README.md) for its Base models using audio, text and reference audio. That workflow is distinct from the CustomVoice auditions here. The official example uses CUDA: local Mac inference does not establish that its official training path runs on this Mac. Hardware, conversion and training support need a separate feasibility test.

**Sentence construction:** capture the conversation context, actual reply, preferred reply, failure tags and supporting evidence/revisions. Start with a reviewed style guide and a few representative examples in the local reasoning prompt. If evaluation shows persistent gaps, test supervised adapter fine-tuning or preference optimisation on reviewed pairs. Product facts remain in governed retrieval rather than being embedded as unreviewed permanent model knowledge.

**Improvement loop:** capture → human review → curated examples → candidate prompt/model → held-out evaluation → blind listening/live test → explicit promotion with rollback. Store model/prompt version, source fingerprints, voice settings and clip hash. Keep rejected answers as negative examples or evaluation cases, never accidental positive training samples. Split by conversation/scenario so paraphrases cannot leak between training and testing. Do not use the supplied regression scenarios to tune a candidate and then claim an independent held-out score on those same scenarios.

The delivered feedback capture is the first stage of that loop. No trainer, automatic weight update, dataset approval workflow or model promotion has been implemented in this iteration. Raw interview microphone recordings are not newly retained; collecting training audio requires a separate explicit opt-in. No source approval changes result from ratings.

## Suggested owner participation and next delivery gates

1. Spend about ten minutes comparing greeting, correction, numbers and one longer explanation. Keep names hidden initially; rate the same passages on each voice. Note specific awkward words and timestamps.
2. Suggest preferred wording for five failed answers. We will review context and factual support before using them as teaching examples.
3. Select a voice shortlist, not a deployment winner. Test the shortlist live with ASR/reasoning load, interruptions, long turns, sentence joins and repeated corrections. Check first audible response and underruns as well as timbre and pace.
4. Implement the dialogue evaluation and reviewed technical coverage before further model tuning. Acceptance requires direct relevant answers, no unsupported product claims, no repeated non-answer, preserved amounts/negation and natural correction handling.

The live opener now includes “Hi.” The rest of the supplied reasoning failures remain explicit backlog, not claimed fixed by this voice audition.

## Measurements and reproduction

Forty clips generated: five configurations × eight passages. Seed 41, MLX Audio 0.5.4. Models ran sequentially on this Mac. One run per passage; warm summaries exclude each model’s first generation. No post-generation tempo, gain or pause manipulation. Turbo emits complete sentences; other audition adapters emit complete utterances. Consequently first adapter output is **not comparable first audible live latency**. No concurrent ASR/LLM stress test or subjective quality conclusion is implied.

| Configuration | Warm median synthesis | Warm median RTF | Peak MLX memory | Clipped samples |
|---|---:|---:|---:|---:|
| Current Chatterbox Turbo 4-bit · British reference | 1.63 s | 0.199 | 2.03 GB | 0 |
| Chatterbox Multilingual V3 · same British reference | 3.58 s | 0.408 | 5.45 GB | 0 |
| Qwen CustomVoice 1.7B 4-bit · Aiden, directed | 2.73 s | 0.236 | 6.62 GB | 0 |
| Qwen CustomVoice 1.7B 8-bit · Aiden, directed | 2.22 s | 0.236 | 7.56 GB | 0 |
| VibeVoice Realtime 0.5B FP16 · Frank (accent to assess) | 5.40 s | 0.554 | 4.89 GB | 0 |

RTF is synthesis time divided by audio duration; lower values indicate faster synthesis, not better quality. Load/preparation is reported separately in [measurements, artifact hashes and pinned revisions](evidence/2026-09-24/tiberius-voice-benchmark.json). Peak MLX allocation is not total system memory. See the experience README for provisioning and offline generation commands. The live selected voice is unchanged.

A separate local Whisper small.en check decoded the numbers and technical passages from all five configurations. All five retained the two amounts, negation and approval-before-activation ordering in recognition output. Proper names were transcribed inconsistently (for example Qwen/QUEN/Q1 and Tibi/tibi, and V3’s “step” was decoded as “state”), so those remain a listening check; ASR cannot establish the actual pronunciation or naturalness. All 40 generated waveforms were finite and recorded zero samples at or above full scale. This does not establish freedom from audible clicks, poor prosody or streaming glitches.

Validation: 352 Python tests and 60 JavaScript tests passed; Ruff, JavaScript syntax and whitespace checks passed. Deployed page inspected in the browser without playback or microphone access. HTTP checks verified all prepared audio routes, CSS/JavaScript, and both app-level and audition request-token handling. An intentionally invalid authenticated request returned 422 without storing fake feedback. Both isolated services are healthy. Human voice preference and live-flow acceptance remain open.
