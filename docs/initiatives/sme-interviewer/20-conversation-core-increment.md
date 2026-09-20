# Combined conversation-core increment

20 September 2026. User-authorised combined delivery, following the accepted independent review and subsequent listening/playback observations. Local inference and British Voice B retained.

## Delivered behaviour

- A fallible local answer check asks for clarification on unrelated, unclear or inconsistent wording. Explicit unknowns are valid. Capture warnings ask for a better recording; semantic text alone is not evidence of microphone noise. The original question and editable wording remain until clarified or explicitly kept. No challenged answer contributes to confirmed coverage unless the participant overrides it.
- The smaller 7B checker misclassified three valid answers in the development probe. The existing Qwen 3.5 35B-A3B writer model is used for this check instead, without thinking tokens. No additional model download or cloud planner.
- Filler has a separate player and completion promise. Question synthesis proceeds concurrently, but playback waits for committed filler to end. A 12-second watchdog handles stalled media. Stop, Pause, Record, navigation and disconnect cancel immediately; they do not silently turn off future automatic speech.
- Failed planning now speaks an explicit recovery message when automatic speech is enabled. Browser playback rejection remains visible with a manual replay option. We cannot promise autoplay against browser policy.
- The interview uses authenticated same-origin WebSocket commands and pushed session/audio completion instead of status polling. Requests carry session, turn, revision and generation identifiers; mutations still use the existing revision/idempotency boundary. Controls can overtake slow checks. One live controller per session, bounded queue/request count, disconnect cancellation and paused snapshot recovery prevent stale work from being replayed. Complete WAV capture and HTTP audio delivery remain: this is control/event transport, not continuous audio streaming.
- A multi-sentence uncertainty bug found in browser testing is fixed: an open point now anchors the sentence that actually expresses uncertainty, instead of blindly selecting the last sentence. No new supplier-specific wording guard.

## Evidence

Structural checks: 650 repository Python tests; 200 service-environment tests; 30 browser-state/playback/transport tests. Ruff and frontend production build pass. Browser tests now run in the ADO pipeline. Existing dependency deprecation warnings and frontend bundle-size warning remain.

Synthetic semantic development probe: 7B matched 9/12 expected clarification decisions; 35B matched 12/12. The 35B check took 0.327–0.535 seconds across those 12 calls (including first observed call); this measures only classification, not end-to-end turn latency. The probe is checked into the service for reproduction. Both results are retained: [7B](evidence/2026-09-20/answer-check-7b-development.json), [35B](evidence/2026-09-20/answer-check-35b-development.json). These scenarios informed model selection and are not holdout evidence.

Disposable real-browser trial: nonsense was challenged without a saved contribution; a replacement account progressed; sequence confirmation produced “What evidence, if any, showed that the manager had approved the activation?” with automatic playback. A mixed unknown/known answer first exposed the uncertainty exception. The failed attempt remains in timings. After fixing and restarting, saved wording reopened paused; explicit resume/retry produced the source-finding guide with playback. No user's interview was used for this trial.

[Browser timings](evidence/2026-09-20/conversation-core-timings.json): 8 attempts, 6 completed playback attempts, 1 clarification (original typed attempt marked text-only; clarification speech is a separate replay), 1 failed planning attempt. Successful typed answer-to-playback n=2: nearest-rank p50 1,185.6 ms, p95 3,000.9 ms. Four opening/recovery/replay attempts are kept separate. Residency is unknown in browser diagnostics. Acoustic end-of-speech gap n=0; naturalness/usefulness/pace rubric n=0. No threshold or Human gate pass is claimed.

## Remaining combined work

S109 stays Active: continuous audio frames and unavailable-streaming fallback are not delivered. S114 stays Active until acoustic and streamed milestones exist. S115 and S119 are not completed by advisory clarification or this small development probe. Continuous listening/endpointing, clause synthesis, talker/thinker overlap, acoustic barge-in, recap confirmation and a separated development/holdout persona harness remain in the accepted order. No vector database is introduced: this increment addresses control flow and interpretation, not evidence-search scale. Full local residency/concurrency measurements remain required.

Deliver subsequent work in larger integrated batches with automated checks, not a request for Human testing after every internal change. G1.5 remains the later ten-minute unscripted trial.
