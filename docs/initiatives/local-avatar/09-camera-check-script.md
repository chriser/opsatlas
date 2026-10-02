# First camera check: exact recording script

Record one continuous clip of roughly 90 seconds. This is a setup and alignment check before a larger training corpus. It gives us relaxed silence, clear lip shapes and ordinary connected speech. After checking focus, audio/video timing and landmark stability, we can plan the longer separate training, validation and test sessions.

Use a fixed camera, head-and-shoulders framing, soft light from the front and a quiet room. Prefer 1080p at 30 fps with microphone audio. Keep your whole mouth visible and the script close to the lens so you do not keep looking down. Use your usual accent and comfortable speaking volume. Let the mouth relax between phrases; avoid holding a smile, exaggerating articulation or moving the head repeatedly. Keep the original recording with audio, without filters or editing.

## 1. Quiet neutral face — about 10 seconds

Look towards the camera with relaxed, gently closed lips. Breathe normally and blink naturally. Do not speak.

## 2. Separate words and vowels — about 20 seconds

Read the words below, leaving a brief pause and letting your lips rest between words:

> Mum. Paper. Baby. Map. Blue. Please. Five. Very. Six. She. Today. Later.

Then say each vowel sound for about one second, with a short pause between sounds:

> Ahh. Eee. Ooo. Oh. Ay.

Use clear ordinary speech. These examples sample closed, open, wide and rounded mouth positions; they are not calibrated muscle controls.

## 3. Natural passage — about 40–50 seconds

Read this at your normal conversational pace. Pause at punctuation and let the question sound like a question:

> Hello, this is a short recording for my local avatar. I am speaking at a comfortable pace. I bought a blue paper bag, while Mum made coffee by the window. Five very fresh apples were sitting beside six small boxes. She chose the yellow one and said, “Please put it on the table.” I can speak softly, ask a question, and pause before I continue. What would you like to work on today? We can make a clear plan, take one step at a time, and check the result together.

## 4. Quiet finish — about 10 seconds

Return to relaxed closed lips and look towards the camera. Blink naturally and remain quiet. Then stop recording.

Save the original as `camera-check-01.mov` or `.mp4` in the private folder:

```text
.runtime/local-avatar/recordings/camera-pilot/
```

Tell Codex the filename when it is there. A few seconds more or less is fine. This first sample is calibration material, not a final held-out test or proof that the training corpus is sufficient. All media and facial coordinates remain private and ignored by git; only this generic script is published.
