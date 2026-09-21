# Attentive listener prototype — 21 September 2026

The user approved a small social layer ahead of further factual-reasoning work.
This increment supplies a conservative, stateful listener policy, integrates it
into the continuous conversation controller, and provides an isolated practice
without loading the large interview model.

## Try it

Open http://127.0.0.1:8771/conversation?listener=1. The existing experience lab on
8769 links to this practice. Ports 8767, 8769 and the connected 8770 candidate were
not restarted. Use a headset and fictional examples; microphone access remains
an explicit browser/user action. If endpoint detection leaves a request open,
use **I've finished this answer**.

Examples: “Give me a second”, “Sorry, I'm rambling”, “That's not what I meant”,
“Please let me think in silence”, “A little encouragement would help”, and
“Thank you for waiting”. Wording variants are supported within a narrow explicit
request vocabulary. The practice displays when a reply needs the content
reasoner; it does not answer process questions or claim to understand the facts.

The local service can be started using:

```sh
services/sme_interviewer/.venv/bin/python -c 'import uvicorn; from services.sme_interviewer.expressive_preview import candidate_app; uvicorn.run(candidate_app("listener-preview"), host="127.0.0.1", port=8771, ws_max_size=8000000)'
```

## Behaviour and boundaries

- The CPU policy selects an action before wording: wait, reassure, invite a
  correction, change the quiet preference, or acknowledge thanks. Silence is
  valid. A five-second pause no longer automatically triggers reassurance.
- Repeated social requests within 30 seconds receive no repeated verbal cue.
  Phrases vary on later occasions. The quiet preference and phrase-use counts
  survive reopening; the short cooldown is connection-local.
- Complete explicit requests bypass content inference. Partial requests never
  commit social actions. Mixed factual replies remain intact for the reasoner;
  “Does that answer your question?” also requires that reasoner.
- Each action has a generation and a two-second deadline. It is rechecked after
  obtaining the audio floor; stale actions are dropped. A committed cue finishes
  before a queued question, while participant interruption cancels playback.
- Nine short same-voice phrases are prepared before listening. The existing
  native Charles pace, sentence spacing, packet buffering and audio controller
  are retained. The audio bank is bounded to 8 MB of base64 payload.
- Social actions and preferences are recorded separately from process evidence.
  They cannot create or confirm factual claims, change a pending amount check,
  or discard an interrupted answer. Practice does not retain spoken process
  answers; its on-screen transcript is transient.

This is a deterministic policy prototype, **not general social comprehension**.
It does not infer emotion from voice, produce free-form humour, or provide
millisecond reactions before recognition finishes. It adds no model or vector
database. Unrecognised social wording still needs the content reasoner in the
full interview. Full interview resource contention remains unresolved; this
practice deliberately avoids the two large-model workload. It does not pause
or unload the separate model service.

## Verification

- 295 Python tests and 50 JavaScript tests passed before the final explanatory
  copy update. Focused checks were rerun after that update.
- Tests cover explicit vs quoted, negated, conditional and mixed requests;
  preference restoration; repetition; stale generations and expired actions;
  audio serialization and interruption; failed-reasoner bypass; unfinished
  answer preservation; and a practice mode that cannot call the content model.
- [Local policy and voice-bank evidence](evidence/2026-09-21/listener-policy.json):
  1,225,992 bytes of base64 audio, decision p95 below 0.01 ms over 1,000 iterations.
  This measures policy only, after recognised text; it excludes ASR and playback.
- [Real recogniser/voice check](evidence/2026-09-21/listener-live.json): synthetic
  Charles speech “Sorry, I'm rambling.” was recognised exactly and produced the
  reassurance action; 36 cached packets sent, 83.77 ms from final recognition
  invocation through audio dispatch. Automatic acknowledgements, no microphone,
  endpoint or browser/headset delay. No content model called.
- The local practice page loaded in the in-app browser. Human naturalness and
  real headset end-to-end latency remain acceptance work.

## Next development gates

1. Evaluate indirect social language using a labelled corpus before choosing a
   small local intent model. Compare it with this deterministic baseline for
   missed intent, incorrect social agreement and preservation of factual text.
2. Add streaming semantic/acoustic signals only with measured false interruption
   rates. Do not equate a pause with confusion, anxiety or permission to speak.
3. Measure headset end-of-speech to first audible response separately from
   decision time; keep the audio quality regression checks.
4. Resolve the existing full interview memory budget before combining semantic
   social inference with the foreground reasoner. No extra GPU model has been
   added in this increment.
