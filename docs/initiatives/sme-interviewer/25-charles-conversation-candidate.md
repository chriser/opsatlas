# Charles conversation integration — 21 September 2026

Status: experimental integrated candidate; not promoted to the main interviewer.
The participant selected lab **A = Pocket TTS · Charles** for expression, except
for its “Mm-hm”. Audition letters are random per lab startup; Charles is pinned by
identity in this candidate. No non-word acknowledgements are inserted.

## Delivered

The real contextual interviewer now has an opt-in Charles backend, using the
already pinned Pocket environment and stock voice embedding. It is a resident CPU
worker under the existing network-denying sandbox. It warms synthesis before
capture. A streaming onset filter removes only leading quiet, retaining 40 ms of
pre-roll; it preserves all interior pauses. Silent and non-finite output fail
explicitly. The prepared-speech buffer now accommodates small streaming chunks
without increasing its four-megabyte byte budget.

Native Silero continues to detect speech. Smart Turn runs on a separate thread
using the last eight seconds, without blocking frame reception. Two completion
estimates of at least 0.7 and at least one second of silence are required. Resumed
speech invalidates old completion estimates. A manual **I've finished this answer**
control remains available; it does nothing on pure silence. A stalled detector
leaves that control available and displays a notice.

After five seconds of an unfinished answer, one cached “Take your time. There is
no rush” is available. It is not an inference about emotion or confidence. A single
speech lock and actual playback acknowledgements keep a committed cue ahead of a
ready question. Resumed speech cancels it, including within the same answer. Cues
do not replace the displayed question or count as meaningful response latency.
The worklet identifies the actual first rendered response chunk separately.

The existing source-bound local planner receives a compact history of what earlier
questions sought, alongside the authoritative account and contribution kinds. It
is told not to recycle an unanswered question under another focus label when the
participant supplies a correction or a related detail. The immediate duplicate
check now catches padding such as “actually” added to an earlier question. These
are bounded improvements, not a claim of general semantic repetition detection.

## Scheduling discovery

The first paced end-to-end replay exposed repeated swaps between the 35B foreground
planner and the 7B question reviewer. The candidate now warms the foreground model
before listening and queues semantic reviews for the recap. Reviews run serially;
confirmation awaits them. Resume cancels the drain and warms the foreground model
again. Closing early records queued checks as unavailable, never as passed.
Review notices update during recap without replacing the participant's edits.

A separate, actively used Ollama instance at port 11435 also has `qwen3.6:35b`
resident with a 262,144-token context and approximately 24 GB of GPU allocation.
The interviewer uses port 11434 and an 8,192-token context. Actual Metal out-of-memory
errors occurred during the comparison. The other service was left running. The
candidate also tested a prefill batch of 128. It did not resolve the failures
and was slower in the small replay, so it is not enabled by the preview launcher.
The optional `SME_BOUNDED_PREFILL=1` switch remains for reproducing that experiment.

Deferred checks here are **question-quality reviews**, not a new production Atlas
retrieval or deep evidence research integration. The synthetic evidence fixture,
provisional wording, recap confirmation and owner-approval boundaries remain.

## Operation

```sh
services/sme_interviewer/.venv/bin/python -m services.sme_interviewer.expressive_preview
```

Open <http://127.0.0.1:8770/conversation>. Its database is in
`services/sme_interviewer/.runtime/expressive-preview`; model files are shared via
symlinks. The main interviewer on 8767 and audition on 8769 are not restarted.
The preview module explicitly selects Charles, Smart Turn, deferred reviews; existing startup commands retain their defaults.

Reproduce the fictional five-answer websocket exercise:

```sh
services/sme_interviewer/.venv/bin/python -m services.sme_interviewer.evaluate_expressive
```

This uses actual local recognition, VAD, completion, planning and synthesis, with
synthetic PCM arriving in real time and simulated playback acknowledgements paced
to each chunk's duration. It never opens the microphone. Its timings are not
browser/headset measurements or a ten-minute human naturalness score.

## Validation boundary

Two isolated warm Charles probes returned first trimmed audio in 72 and 89 ms;
whole-utterance synthesis took 274 and 763 ms respectively. These are synthesis
measurements, not answer-to-response timings. Contextual delay and resource
contention must be reported separately. The concurrent replay evidence is retained
alongside failures; do not call this a latency or naturalness acceptance pass.


255 isolated-service Python tests and 47 JavaScript tests pass; Ruff and whitespace
checks pass. Tests cover onset preservation, stale endpoint estimates, manual
completion on silence, committed cues, interruptions, deferred review scheduling,
recap concerns and repetition guards. The browser setup page was inspected; no
physical microphone permission or acoustic acceptance was performed.

The paced runs below are small unpaired development trials with a changing external
GPU workload. All gaps are detected speech end to the simulated playback consumer
starting the response, including recoveries; these are not five successful
contextual questions in every run.

| Run | Five gaps (ms) | Outcome |
| --- | --- | --- |
| Before scheduling | 27,909; 12,044; 12,270; 12,228; 3,699 | Repeated foreground/reviewer model loads |
| Foreground priority | 3,275; 7,060; 2,465; 2,590; 15,894 | One interpretation recovery; GPU errors remained |
| 128-token prefill, rejected as default | 6,272; 7,546; 8,177; 11,503; 4,297 | Repetition blocked but follow-up repair failed; recap reviews completed |

The final run handled the unrelated football answer with a connection clarification
and the unknown exception owner with a possible-source invitation. It did not
re-ask whether the supplier was activated. A correction triggered a repeated
initiator question; the strengthened guard blocked it, but the model exhausted its
repair and used an explicit recovery. Better semantic question selection is still
required. The concurrent GPU failure and sub-1.5-second response target are not
resolved. The user has been asked whether interviews must coexist with the other
35B workload or have dedicated capacity; that service has not been stopped.

Raw results: [before scheduling](evidence/2026-09-21/charles-before-scheduling.json),
[foreground priority](evidence/2026-09-21/charles-foreground-priority.json), and
[rejected smaller batch](evidence/2026-09-21/charles-bounded-prefill-rejected.json).
