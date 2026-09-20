# Experience lab — 20 September 2026

Status: isolated experimental delivery. The existing interviewer has not been replaced.
This implements the voice-audition and modular-listener investigation approved after
[the expressive-conversation research](23-expressive-conversation-research.md).
It does not claim the final human conversational experience is achieved.

## What is available

The lab runs at <http://127.0.0.1:8769/>. The existing interviewer remains at 8767;
the previous pace candidate remains at 8768.

- Eight male/female candidates across Kokoro, Pocket TTS, Chatterbox Turbo and Qwen
  Base, using identical fictional passages. Names are hidden until revealed. New
  A–H aliases are shuffled per server start and are unrelated to the old audition's
  A/B/C labels. Current Voice B is included as Kokoro Isabella.
- Ten passages target “recap”, “Finance”, isolated words, abbreviations, amounts/negation, questions, uncertainty,
  correction, recap pacing, patience and a brief listening sound. Human scores and
  optional notes are stored locally and exportable. No automated human scores exist.
- A listening playground combines the existing native Silero VAD with Smart Turn
  v3.2 CPU completion estimates. Patience is adjustable or can be silent. A manual
  “I've finished” control remains available.
- One audio controller owns playback: a committed encouragement clip finishes
  before a queued question; user speech cancels current and queued audio. Playback
  failures release the floor. A local WAV replay follows the same policy without
  opening the microphone.

This playground deliberately asks a **scripted** follow-up. It is not semantic
interviewing, contradiction checking, emotion recognition or deep evidence research.
Its purpose is to isolate the acoustic experience before coupling it to reasoning.
The speech detector and endpoint model can still make mistakes, especially on noise,
soft speech and unusually long pauses. Headset acoustics require human testing.

## Findings so far

All eight voices generated the main passages. Qwen female returned no audio for
“Mm-hm”, so that sample is disabled; 79 of 80 samples are available. Tiny non-word
utterances behave differently from normal sentences and need their own audition.
Whisper checks recovered the intended amounts and approval sequence for all eight
voices, and recovered “recap” and “Finance”. ASR agreement is not proof of correct
pronunciation, accent or naturalness, particularly for non-word vocalisations.

First-chunk latency is insufficient: Pocket clips can begin with approximately
650–920 ms of quiet audio in the examples inspected. The measurement records now
separate first returned chunk, first chunk containing significant audio energy and
leading quiet duration. None is claimed to be microphone-to-response latency.
Clips are approximately RMS/peak matched; pauses and wording are not edited.

Measured medians on this Mac, 13 warm ordinary utterances per engine from the primary
seven-passage run (the first utterance and non-word vocalisations excluded).
The later isolated-word and abbreviation additions are outside this timing summary:

| Engine | First chunk | First energy-bearing chunk | Leading quiet in waveform | Synthesis RTF |
| --- | ---: | ---: | ---: | ---: |
| Kokoro MLX | 178 ms | 178 ms | 30 ms | 0.033 |
| Pocket CPU | 43 ms | 110 ms | 520 ms | 0.131 |
| Chatterbox Turbo MLX 4-bit | 182 ms | 182 ms | 90 ms | 0.579 |
| Qwen Base 0.6B MLX 4-bit | 202 ms | 202 ms | 0 ms | 0.324 |

“Energy-bearing” means a 10 ms window above RMS 0.005 in the level-matched output,
not a human judgement that intelligible speech has begun. Pocket can generate past
its leading silence quickly; a streaming adapter would need to remove that quiet
prefix deliberately rather than play it at real-time speed. The audition currently
retains it. Loading and voice preparation are excluded and separately recorded.
These short isolated runs do not establish sustained performance with active planners.

The initial level-based listener interrupted a two-sentence replay at a 0.9-second
internal pause. Replacing that gate with native speech detection and requiring two
confident completion readings plus at least one second without detected speech
preserved the complete male and female replay answers. Both then received one
scripted follow-up. These are regression fixtures, not a general naturalness pass.
Observed endpoint inference in the browser was approximately 29–38 ms, after loading.

A silence replay produced one encouragement and remained listening; silence alone
did not trigger a question. Unit tests cover a ready question waiting for its cue,
interruption discarding queued speech, and rejected playback releasing the floor.

## PersonaPlex spike

Official Hugging Face access was granted and verified. The 8-bit Apple-format
weights are downloaded. The full-precision official transfer was paused with its
partial download retained, to prioritise the smaller inference test.

The pinned Swift port initially failed because Xcode's Metal compiler component was
missing. Apple's Metal Toolchain 27A266a was installed. A minimal harness and pinned
dependency lock now build successfully. The harness uses prerecorded fictional input, with
short streaming chunks, and does not open the microphone. A cache-directory fix in
the isolated checkout ensures the intended voice prompt is actually loaded.

An additional input-clock guard was necessary: the port otherwise reads zeros when
inference outruns incoming microphone frames. The isolated probe waits for the next
real input frame instead. This avoids inserting invented pauses into the input.

Two paced 16-second trials produced 200 audio frames each. First output chunks arrived
at 351 and 238 ms; median inter-chunk intervals were 79.6 and 79.9 ms for nominal
80 ms frames. Maximum queued input was 320 and 160 ms respectively. Total wall time
was 16.00 and 16.06 seconds. Separate prerecorded-input streaming trials generated
15.04 seconds of audio in 10.21 and 9.88 seconds. This establishes promising short-run
throughput on the M4 Max, not ten-minute stability or concurrency with active planners.

**Conversational control failed in this tested adaptation.** Responses introduced
unrequested names and call-centre language, and wandered into unrelated topics.
Both Whisper base and small heard “30,000” in one paced response to an input saying
“fifteen thousand pounds, not fifty thousand pounds”. The other paced response was
recognised as “15”, omitting the scale. These are recognizer observations, not human
listening scores, but they are sufficient to withhold acceptance. The generated text
also drifted; a previous preliminary run produced an unsolicited goodbye.

This does not isolate whether the cause is conversion, quantisation, the port's
conditioning, prompting or the base model. It does mean this implementation must not
be allowed to supply unchecked interview content. It remains a speech-to-speech
research comparison; the modular, text-controlled architecture remains the lead path.

The community 8-bit model card declares CC BY-NC 4.0. It is an experimental artifact,
not a product deployment choice. Any integration needs an appropriately licensed
conversion of the official checkpoint and explicit evaluation of control/grounding.
No live headset, echo, barge-in, accent, naturalness or grounded-question acceptance
is inferred from this paced-file benchmark.

## Acceptance and next decision

Validation: 248 service Python tests, three audio-controller JavaScript tests, lint
and JavaScript syntax checks pass. Browser checks verified audition playback and
completion, male/female answer replays, and patience without treating silence as an
answer. No microphone permission was granted or personal voice recorded during these
agent-run checks. The live headset and human listening scores remain outstanding.

Do not promote a model on synthesis speed alone. First select promising voices by
listening and rating pronunciation, accent, pace and naturalness. Then test the
winning voice with the controller over sustained unscripted conversation and with
the planner/evidence workloads active. Cached audition playback does not establish
live generation latency, concurrency capacity or grounded-question quality.

The expression layer must remain non-factual. The current-conversation reasoner and
background evidence worker retain the boundaries proposed in document 23. Database
changes do not solve prosody, endpointing or speech-generation delay. Hot structured
conversation memory and resource scheduling remain separate integration work.

Setup, pinned artifacts, model provenance and reproduction commands are in the
[lab README](../../../services/sme_interviewer/experience/README.md).
Raw measurements are in [the evidence file](evidence/experience-lab-2026-09-20.json).
