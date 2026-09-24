# Higgs female/male comparison

24 September 2026. Owner preferred Higgs but reported a female-sounding greeting and male-sounding subsequent passages. Requested a quick Higgs-only comparison.

## Finding and correction

The previous Higgs manifest and generator identify the same VCTK **p254 male reference** for every passage. Files and hashes match the manifest; no cross-model audio substitution was found. The greeting had `<|emotion:contentment|>` while introduction, correction and numbers did not. A fixed reference did not establish perceptual voice consistency. The earlier response describing the liked greeting as a female reference voice was incorrect. The user's perception is retained as evidence; the emotion tag is a possible influence, not a proven cause.

VCTK speaker p228 is female and p254 male; see [speaker study](https://www.isca-archive.org/interspeech_2023/ogun23_interspeech.pdf). Recordings are the existing Kyutai enhanced VCTK references, CC BY 4.0; [source and attribution](https://huggingface.co/kyutai/tts-voices/blob/main/README.md), pinned revision `323332d33f997de8394f24a193e1a76df720e01a`.

## Controlled comparison

New `/higgs-voices` page; separate aliases, audio, ratings and export. Original model audition and feedback remain intact.

- Female reference: p228; male reference: p254.
- Same four texts: greeting, original introduction, accepting a correction, numbers.
- One reference encoding reused across all four passages in each column; waveform and encoded-reference hashes recorded.
- Same model revision, FP32 codec, temperature 1.0, seed 41, native full-stop pause cues and no emotion tags for either voice.
- No pitch shifting, time stretching, level normalisation or retraining.
- Generated fully locally under network-denying inference sandbox.

Labels describe the reference speaker, not a guarantee of generated gender or identity. Listen to all four passages for consistency. The newly generated female greeting need not reproduce the old, female-sounding male-conditioned greeting. That earlier clip remains available on `/voice-evaluation`.

Generation command:

```sh
/usr/bin/sandbox-exec -f services/sme_interviewer/offline.sb services/sme_interviewer/.venv/bin/python -m services.sme_interviewer.experience.higgs_comparison
```

Measurements: [eight-clip evidence](evidence/2026-09-24/higgs-female-male-comparison.json). Prior user ratings: [owner export](evidence/2026-09-24/tibi-evaluation-feedback.json). These are unreviewed preferences, not training approval or product knowledge. Live Tibi remains unchanged pending listening and live-flow acceptance.

## Validation

All eight files have finite audio, verified hashes and zero clipped samples. Both sets have identical per-voice reference-code hashes, with different female and male references. Local HTTP checks passed for all eight new and sixteen previous clips, including authenticated feedback validation without storing synthetic ratings. Fourteen relevant Python tests, Ruff and JavaScript syntax checks passed. Local Whisper recovered the requested words and number/negation distinctions; male correction punctuation differed, so prosody still needs listening review. These checks do not certify accent or speaker consistency.
