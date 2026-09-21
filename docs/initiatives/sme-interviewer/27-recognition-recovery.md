# Recognition and visible recovery — 21 September 2026

The user reported a stuck experience and worsening word recognition. Inspection
found the full-conversation session on 8770 had closed, while the recent 8771
practice recorded five completed text-only turns and no listener actions. There
were no inference exceptions in those preview logs. Practice does not retain
spoken answers, so the exact misrecognised phrases could not be recovered; an
example of intended versus recognised wording was requested. These findings do
not establish the cause of the user's recognition errors.

Two concrete reliability issues were addressed:

1. Final wording could reuse an early partial decode once VAD considered the
   last speech frame covered. It now always decodes the complete captured answer.
   Live partials retain greedy decoding; the final decode uses beam search with
   five candidates and disables temperature escalation. No prior transcript or
   suggested process facts are inserted into recognition.
2. Unsupported practice replies produced only a transient notice. The first
   unsupported reply now gets an audible explanation, with a persistent on-screen
   explanation for each unsupported reply. Repeated unsupported replies do not
   repeat the spoken explanation. If smart endpoint detection has not accepted
   an ending after three seconds of silence, the UI shows how to finish the
   answer explicitly, without automatically cutting off a thinking participant.

The page also shows the active capture track's microphone name after permission,
so selecting the browser default does not hide which input is actually in use.
The final recognition pass is visibly labelled “Checking wording”.

## Verification and activation

- 297 Python tests and 51 JavaScript tests passed. Regression cases cover fresh
  final wording replacing a wrong partial, use of the final decoder, visible
  endpoint guidance and bounded spoken practice help.
- [Synthetic comparison](evidence/2026-09-21/final-recognition.json): five Charles
  clips, including £15,000 vs £50,000, negation, Finance and activation sequence.
  Final decoding took 71.7–137.9 ms on warm inference. Both strategies preserved
  the words on these clean generated samples; this is not evidence of improved
  real-headset word error rate. The first partial measurement includes model load.
- The native adapter was compiled against the existing pinned whisper.cpp build
  into `.runtime/recognition-check`. Only the 8770/8771 runtime symlinks were
  updated, then both previews were gracefully restarted. Existing saved sessions
  remain in their databases. Refresh the relevant page to load the UI changes.
- The recognizer uses whisper.cpp's default compute backend, which can use Metal;
  previous descriptions calling the entire ASR check “CPU” were too broad. The
  deterministic listener decision itself runs on the CPU. No larger recognition
  model was added, and no separate model service was changed.

Remaining: compare an actual recognition error with intended wording; check the
selected headset input; assess real-speaker capture/recognition before claiming
recognition quality is solved. Full interview model memory contention is a
separate known limitation. The small listener vocabulary is also still a bounded
prototype, not general social comprehension.
