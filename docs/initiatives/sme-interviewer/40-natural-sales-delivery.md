# Natural answers and earlier Higgs speech

24 September 2026. Owner accepted the Higgs voice, reported repetitive “the records” phrasing and irrelevant commercial caveats, and supplied the transcript plus `interview-timings (3).json`.

## Diagnosis

Four completed microphone turns: displayed-answer-to-audio synthesis/delivery was 3.59, 4.54, 6.90 and 6.56 seconds. Browser audio arrival to playback was only 11–19 ms. Total end-of-speech-to-playback median was 10.42 seconds. The first turn also had an 8.85-second endpoint wait; the other three were about 1.11 seconds. This iteration addresses speech preparation and answer delivery, not the isolated endpoint anomaly.

The product model received every curated record and recent assistant answers, allowing earlier price caveats to dominate an unrelated overview. Prompt changes alone failed the local replay. That replay also exposed a product claim routed to general model knowledge; a brand assertion such as “OpsAtlas helps” was outside the previous narrow verb guard.

## Changes

- Shared plain spoken-language guidance with OpsAtlas Avatar natural mode. Formal mode remains exact; Avatar's separate rewrite/citation validation remains intact. Tibi uses the guidance during its existing evidence synthesis rather than adding another model pass.
- Clear overview/use questions focus on approved overview/process sources, without carrying unrelated commercial dialogue into that answer. Explicit deployment, security, pricing, retrieval and governance questions retain their relevant evidence context. Qualifications within selected sources remain available. This is a bounded rule for the current curated catalogue, not general semantic retrieval.
- Explicit product questions go directly to grounded product answering. Any conversational model response naming OpsAtlas also crosses the evidence boundary, including “helps” and spaced “Ops Atlas”. IDs and current approval hashes are still validated.
- Narrow workspace-help intent explains contributing knowledge, reviewing wording, saving a proposed claim and enabling it for internal rehearsal. No approval or publication is performed. It is labelled workspace guidance, not approved product evidence.
- Attribution-only rendering softens “the records confirm” and “the records do not establish”; it preserves the following assertion, negation or uncertainty. Sources remain in the evidence panel.
- Higgs keeps the selected male reference, seed, temperature and native speed. Responses up to 180 characters remain whole; longer answers can use two complete sentence groups, with at least 55 characters in the opening group. No overlapping-prefix decoding, time stretching or pitch adjustment. The remainder generates while the first part can play.
- Sales reply text is presented once its first audio is available. The interface reports voice preparation meanwhile. A separate `reply_preparing` event records the original reasoning-complete/TTS-start timestamps so moving the display does not hide latency in measurements.
- Pending audio preparation is cancellable. Replies interrupted before first-audio readiness are neither displayed nor committed to conversation memory; prepared audio remains bounded by the existing cache limits.

## Higgs controls

[Official model controls](https://huggingface.co/bosonai/higgs-tts-3-4b) include native pause/long-pause, slower/faster delivery, lower/higher pitch, lower/higher expressiveness, emotion and vocal effects. The installed MLX generator also exposes temperature, top-p, top-k, seed and maximum frames/tokens; the fixed reference codes determine the conditioning voice. These are generation controls, not guarantees of perceptual consistency.

Current accepted baseline: male p254 reference (female p228 alternative), seed 41, temperature 1, FP32 codec, full-stop pause cues; no emotion, pitch, speed or expressiveness override. Keep this baseline while fixing conversational delivery. Native speed tags would generate new speech rather than stretching a waveform, but still need listening evaluation. `stream=True` in this installed Higgs generator does not yield incremental audio; complete-sentence groups are an application-level latency improvement, not a claim of native streaming.

## Verification

80 relevant Python tests and 20 browser tests passed; Ruff and JavaScript syntax checks passed. Tests cover source scoping, preserving unknowns/negation, direct evidence routing, workspace help, sentence boundaries, cancellation before audio readiness and honest timing marks. Avatar formal/natural tests passed.

Actual local-model replay: overview and purpose answers now cite overview/process without prices/deployment guarantees; the missing-details question gives workflow instructions; explicit price and access-control questions preserve uncertainty/limitations. Early failing replay led to the evidence/routing correction and is not presented as successful validation.

Identical-text whole/grouped GPU comparisons and local Whisper content checks are saved in [evidence](evidence/2026-09-24/natural-sales-delivery.json). Local ASR recovered both complete sentences in both modes; this is not a perceptual voice-quality judgement. No product knowledge or governance approvals changed. Real headset latency and perceived voice consistency remain a live acceptance check; sub-1.5-second end-to-end performance is not claimed.

The repeated warm identical-text comparison measured 7.11 s to first audio for whole-response decoding versus 3.22 s for sentence-group delivery (about 55% sooner). The second group was available before the first would finish playing. This is one development passage, not a percentile or a general latency guarantee. Short answers retain whole-utterance delivery.

An actual Conversation + offline GPU SpeechWorker probe with a temporary synthetic ledger measured 3.41 s to first audio readiness. The visible `social_reply` and first audio packet were emitted 0.05 ms apart on the server; this excludes browser/device buffering. All 172 audio packets completed. No synthetic conversation was added to the owner's sales workspace.
