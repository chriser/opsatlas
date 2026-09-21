# Contextual small talk and expressive delivery — 21 September 2026

The user asked for casual engagement, greetings, thanks, excitement, sympathy and
laughter. They approved a short conversational prototype plus expressive voice
comparisons. The previous listener policy only recognised a few explicit requests;
this increment adds a local generative conversation model and voice style selection.

## Try the result

- [Spoken conversation](http://127.0.0.1:8772/conversation?social=1)
- [Type replies and hear the voice](http://127.0.0.1:8772/conversation?social=1&text=1)
- [Compare fifteen prepared samples](http://127.0.0.1:8772/social-voices)

Select the voice before starting: Chatterbox Turbo with the existing British male
reference, Qwen CustomVoice Aiden with British-English delivery instructions, or
Charles as the accepted baseline. The Qwen instruction is not a guarantee of a
British accent. Voice identity remains fixed within a session and is restored on
reopening. Raw microphone audio is transient. The last six social exchanges are
saved locally as conversational memory, separately from process evidence.

The conversation can greet, respond to news about the day, acknowledge corrections,
handle light humour, thank the participant and signal readiness to enter the process
interview. The last step exposes a link to the separate full interview; automatic
handoff and shared factual reasoning are not implemented here. This is a social
prototype, not the finished interviewer. The existing previews remain available.

## Architecture

`Companion` calls local Ollama on 11434 using `qwen3.5:4b`, thinking disabled, a
4096-token context, bounded JSON and a 280-character reply. It returns reply text,
style (neutral/warm/bright/gentle/amused) and phase (social/ready/closed). It sees
only the bounded social history. It has no tools, knowledge-base access or factual
approval authority. Invalid responses and timeouts produce visible errors.

The first 7B experiment repeatedly selected the interview transition for ordinary
greetings. It was rejected. The installed 4B model plus clearer transition examples
handled the tested phases correctly. It is still imperfect: occasional unnecessary
follow-ups and over-formal phrasing remain in the evaluation. The prompt does not
constitute a proof that every generated response respects every semantic constraint.

Cold inference is warmed before listening begins. Typed-only mode does not request
a microphone, start the recogniser/VAD, or send synthetic capture frames. Spoken
mode uses the existing final recognition pass, turn detection and interruption path.
Generation checks discard a reply if the participant has interrupted before it is
committed. Social history never enters the process-evidence segments. Committed
assistant text can remain in history if its subsequent playback is interrupted;
word-level spoken-history tracking remains future work.

One audio controller owns output. New voice workers use the existing 80 ms packets,
120 ms browser prebuffer and bounded acknowledgements. The workers deny network
access during inference. They do not use cloud TTS or a cloud conversation model.

- **Charles:** unchanged accepted voice, no claimed emotion control.
- **Chatterbox Turbo:** native expressive synthesis and a `[chuckle]` event when
  the semantic layer selects amused. The installed Turbo implementation ignores
  exaggeration controls, so no such slider is exposed. Other emotional nuance is
  driven by wording/native prosody, not a claimed explicit sadness/excitement dial.
- **Qwen CustomVoice 1.7B, MLX 4-bit:** same Aiden speaker across turns, explicit
  instructions for warm, bright, gentle or amused delivery. The CustomVoice model
  differs from the 0.6B Base model used in the earlier audition.

Neither mode claims to hear the participant's emotional state. Styles respond to
recognised wording and context. Human judgement of appropriateness remains necessary.

## Evidence and limits

- [Eleven semantic turns](evidence/2026-09-21/social-dialogue.json): warm reasoning
  approximately 0.33–0.85 seconds across greetings, tiredness, good news, correction,
  humour, a request not to laugh, explicit interview transition and goodbye. A cold
  warm-up took roughly 17.5 seconds in the earlier run; this is not a sub-second
  cold-start claim.
- [Actual socket and offline voice workers](evidence/2026-09-21/social-live.json):
  synthetic typed reply to first audio packet was 873.0 ms for Chatterbox and
  849.9 ms for Qwen, with 706.3/718.6 ms reasoning respectively. Automatic audio
  acknowledgements. These numbers exclude microphone, ASR, endpoint delay and
  headset playback and are two observations, not a latency percentile or SLA.
- [Fifteen voice samples and hashes](evidence/2026-09-21/social-voices.json): same
  five exchanges per engine; includes cold synthesis and warm first-chunk timings.
- [Independent local recognition of those samples](evidence/2026-09-21/social-voice-recognition.json):
  fourteen exact normalised word matches; Chatterbox's humour clip adds recognised
  “Heh” corresponding to the requested chuckle. This checks wording, not emotion,
  accent or pleasantness. No human listening score is inferred.
- 304 Python tests and 52 JavaScript tests passed; lint and whitespace checks passed.
- A typed browser conversation played a contextual response to an exhausting day.
  Tests cover schema validation, bounded history, cancellation before commitment,
  separation from process evidence, and typed mode without capture.

The remaining decision is which delivery sounds natural over a conversation,
including whether Qwen maintains the desired accent. The prototype does not claim
emotional realism merely because a style parameter exists.

## Reproduce

Provision the optional CustomVoice artifact with the speech virtualenv:

```sh
services/sme_interviewer/.venv/bin/python -m services.sme_interviewer.experience.provision --social
services/sme_interviewer/.venv/bin/python -m services.sme_interviewer.social_preview
```

Generate each comparison sequentially to avoid model contention and manifest races:

```sh
services/sme_interviewer/.venv/bin/python -m services.sme_interviewer.experience.social_audition 'Charles baseline'
services/sme_interviewer/.venv/bin/python -m services.sme_interviewer.experience.social_audition 'Chatterbox Turbo'
services/sme_interviewer/.venv/bin/python -m services.sme_interviewer.experience.social_audition 'Qwen CustomVoice'
```

CustomVoice artifact: `mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-4bit`, revision
`f35faf19b0cc2160865af64ecf0f22f83d335135`. Existing voice/model reference pins are
retained in the experience provisioner. The separate 11435 workload was untouched.
