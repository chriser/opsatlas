# Chatterbox selection and live audio continuity

The user selected Chatterbox and reported crackles in live conversation, rather
than the prepared comparison clips. Chatterbox remains the selected voice in the
isolated social preview at http://127.0.0.1:8772/conversation?social=1.

## Findings and correction

Three fictional utterances captured directly from the installed MLX Chatterbox
stream showed abrupt waveform steps at some synthesis chunk joins. The decoder
regenerates a growing waveform and slices off previously emitted samples. These
measurements support a join-discontinuity diagnosis, but do not establish that
every audible crackle has that cause.

The Chatterbox adapter now retains a 2 ms tail and repairs only joins whose step
is anomalous relative to nearby waveform slopes. A raised-cosine correction spans
at most 2 ms on either side of the join, with a clipping guard. Sample count,
sample rate and pacing are preserved. This operates at synthesis boundaries,
not the arbitrary 80 ms transport packet boundaries. Installed model code and
voice settings are unchanged.

The browser also applies a 5 ms transition when playback is interrupted, runs
out of buffered audio or resumes from a gap. Continuous buffered playback remains
unchanged. This softens a hard transition to silence; it does not eliminate stalls.

## Evidence

[Same-PCM comparison](evidence/2026-09-21/chatterbox-seams.json): the largest
join step in the first two samples fell from 0.2231 to 0.0319 and from 0.2150 to
0.0145 of full scale. All three sample counts and peak levels were unchanged.
The third sample's largest step remained 0.0939 because it was not anomalous
relative to its local waveform. Interior transients are intentionally untouched.

[Live socket smoke test](evidence/2026-09-21/chatterbox-live-after-seams.json):
the restarted preview generated a contextual gentle reply and 43 audio packets;
typed input to first audio packet took 910 ms, including 745.8 ms of reasoning.
This is one warm local measurement, excluding microphone recognition, endpoint
detection and headset playback. It is not an end-to-end latency guarantee.

Validation: 308 Python tests and 53 JavaScript tests passed; focused Ruff and
diff checks passed. Regression coverage includes clean joins, discontinuities,
short chunks, non-finite audio, sample preservation, underruns and interruption.

Prepared comparison clips were not regenerated. Human headset listening remains
necessary to assess the improvement. Crackles inside a generated chunk or caused
by the audio device are outside this correction's scope. Conversational reasoning
and final naturalness acceptance remain open.
