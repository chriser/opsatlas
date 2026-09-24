# Higgs selected for local sales rehearsal

24 September 2026. Owner selected the Higgs male reference voice, retaining female as the close second, and authorised switching back to sales-pitch testing.

## Delivered

- Sales rehearsal defaults to `higgs`, with a visible `higgs_female` alternative before starting.
- Fixed p254 male / p228 female reference encoding loaded once per worker. Pinned model and FP32 codec match the accepted comparison.
- Same seed 41, temperature 1, native full-stop pause cues, no emotion switching, pitch shift or tempo adjustment. Maximum generation frames increased to 1800 for live answers up to the existing 600-character bound.
- Complete responses decoded once to preserve cross-sentence prosody; finished audio delivered through the existing bounded 80 ms PCM packets and playback acknowledgement flow. This is full-utterance synthesis, not native streaming.
- Both streaming protocol and file synthesis supported. Cancellation/recovery uses the existing bounded worker lifecycle.
- Older saved sales sessions and stale Chatterbox clients resolve to the selected Higgs family; newly selected female voice is accepted. Session voice labels identify the active Higgs reference.
- Existing sales reasoning, approved evidence, speech recognition and governance are unchanged. Prior auditions remain available.

## Validation and limits

58 relevant Python tests and 19 browser tests passed, plus Ruff and JavaScript syntax checks. New tests cover legacy sales engine migration, female selection, fixed conditioning, full-response generation and invalid waveform rejection.

Actual offline GPU worker checks: greeting first audio 2.81 s, short answer 3.11 s, numbers 3.39 s. All delivered 24 kHz packets. Cancellation followed by a new request passed. [Worker evidence](evidence/2026-09-24/higgs-live-worker.json). These timings exclude conversation reasoning and headset playback. Cold model preparation measured 2.16 s in this run; long answers take longer.

Sales page checked in browser: male selected, female available, eight product records enabled. No microphone or synthetic conversation was started in the user's sales workspace during validation. Real headset flow and perceived voice consistency remain owner acceptance; switching engines does not establish sub-1.5-second conversational latency.

Test at `/conversation?social=1&sales=1` with a fresh session. All execution remains local private rehearsal; this change is not commercial deployment clearance.

A separate actual female-worker file-synthesis probe also passed (24 kHz, 2.8 seconds of generated audio).
