# Camera recording protocol for the next local avatar experiment

The short synthetic clip established a working local pipeline, but the speech model is weak. The next collection should supply clear natural mouth movement and a separate test session. This is a revised data plan, not an already captured or validated dataset.

Use camera video of yourself speaking, with stable light and unobstructed lips. Record only someone who has agreed to this use. Keep files locally in ignored runtime storage. We will record provenance and intended use privately; no external avatar upload is needed.

## Setup

- Frame head and shoulders, mostly straight on. Use a fixed camera.
- Use stable soft frontal light, clear focus and a quiet room. Avoid screen capture, filters, motion blur and covered lips.
- Aim for 1080p at 30 fps with microphone audio. Actual timestamp continuity and mouth visibility will be checked; settings alone do not guarantee good labels.
- Speak normally, avoid clipped audio and include pauses. Relax the mouth rather than holding a smile throughout.
- If convenient, save a still frame with closed relaxed lips. It can provide a future reference matching the recording's light; the existing portrait stays available. Adapting the current portrait compositor to a new still's dimensions is separate implementation work.

## Three separate sessions

Start with a **60–90 second camera check** before recording the full corpus: relaxed closed lips, a few “mum / paper / baby” examples, “ah / ee / oo”, and a short natural explanation with pauses. We will check the new capture's timing, tracking and mouth visibility before increasing volume.

The Human selected this camera check as the next stage. Use the [exact first recording script](09-camera-check-script.md), which takes roughly 90 seconds including silent rests and natural reading. Do not collect the larger corpus until the first recording passes inspection.

Capture approximately 24 minutes as separate files, with a new recording start between sessions. Allocate roles before fitting any model. Do not move the final test file into training later.

| Session | Approximate length | Role and content |
|---|---:|---|
| A | 12 minutes | Training: deliberate shapes, ordinary reading and spontaneous speech |
| B | 6 minutes | Validation: different sentences for model selection |
| C | 6 minutes | Test: unseen sentences and natural delivery, excluded from calibration and tuning |

In A, spend roughly two minutes on the following with two-second rests. Repeat slowly once and then at normal speed:

1. Relaxed closed lips, then “mum”, “paper”, “baby”, “map”, “blue”, “please”. Close the lips when natural.
2. Sustained “ah”, “ee”, “oo”, then “oh” and “ay”. Include open, wide and rounded shapes without exaggerated strain.
3. “five”, “very”, “fine”; “six”, “she”, “yes”; “today”, “later”. Use ordinary articulation.
4. Natural full blinks, neutral expression and a small smile. Keep the head mostly still during mouth calibration.

For the remaining ten minutes, read ordinary prose and explain familiar topics conversationally. Include short replies, questions, numbers, pauses and a small laugh. Reserve restrained head turns and nods for a labelled final minute, within about ten degrees. This does not establish a full head-pose or eye-behavior training corpus.

For B and C, use new sentences covering the same shapes, followed by different spontaneous topics. In C, include thirty seconds of silence/relaxed lips, short phrases separated by pauses and a longer passage. Do not repeat exact training sentences as the only test evidence.

These are separate recording sessions from one person and setup, not evidence for other identities, cameras or languages. Duration is a pilot target; sufficiency will be assessed from coverage and held-out behavior rather than minutes alone.

## Local handoff and validation

Put the files in `.runtime/local-avatar/recordings/camera-pilot/` and provide filenames or local paths in this chat. Keep originals unchanged. No installation or external upload is required from you.

Before training, Codex will inspect stream origins, timestamps, audio levels and sampled mouth shapes; prepare a private consent/provenance manifest; check tracking and exclusions; and freeze file-level roles. Calibrate controls that can be recovered reliably instead of forcing all twelve rig labels. Check phoneme timing on training/validation examples and keep the final test untouched until model selection finishes.

Additional coverage and sessions may still be needed. More minutes alone are not assumed to solve loss weighting, geometry or rendering limitations; the weak neural baseline remains evidence for the next experiment.
