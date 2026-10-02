# Independent natural camera corpus

The Human supplied the three sessions requested by the [capture protocol](07-camera-capture-protocol.md). They are stored privately under ignored runtime storage. File roles were frozen before any fitting: A is training, B is validation and C is final test. The original short camera check remains calibration material; the previous Anam recording retains its synthetic provenance and frozen experiment results.

## Capture and integrity

| Session | Duration | Role | Source video frames |
|---|---:|---|---:|
| A | 11 min 52 sec | Training | 21,370 |
| B | 6 min 1 sec | Validation | 10,822 |
| C | 6 min | Final test | 10,794 |

The three source files have distinct privately recorded SHA-256 digests. All primary video and AAC audio streams decode completely. Source timestamps have no duplicates; median video spacing is 33.333 ms and the largest interval is 35 ms. These checks establish technical integrity, not model quality.

The videos are portrait recordings encoded as rotated 1920 × 1080 HEVC with HLG HDR. The local extractor applies the display transform and Apple's ForceSDR conversion before Vision detection. AAC priming is accounted for using the first packet's timestamp and skip samples; the useful waveform origin is zero for each session. Additional audio and metadata streams are excluded from the experiment.

## Preparation and test boundary

The new `camera_corpus.py` freezes file roles and settings, verifies original integrity, audits full decoding and prepares A/B independently. `track_camera.swift` requests 30 images per second in bounded batches and records each returned **actual source timestamp**. Apple Vision revision 3 supplies lip and eye coordinates; it is an existing pretrained tracker, not an avatar model trained here. Only sparse A/B QC stills are retained. Personal images, audio, coordinates, digests and derivatives remain local and ignored.

Failed thumbnail requests receive at most two retries. Missing detections, incomplete landmarks and duplicate returned source frames are rejected. Targets are interpolated onto the 20 ms audio clock only between valid labels separated by at most 100 ms. A validity mask and continuous-run bounds prevent future temporal training batches from bridging missing labels or sessions. Rejected or extrapolated targets must not be used for fitting.

Audio features retain the source clock: mono 16 kHz, 80 log-mel bands, 25 ms causal windows and 20 ms hops. Audio level checks are performed on A/B. Gain is reduced only if needed to avoid over-range PCM derivatives; this does not repair source clipping or establish a noise floor.

The completed preparation produced:

| Session | Usable distinct tracked frames | Valid audio feature steps | Target coverage |
|---|---:|---:|---:|
| A | 20,954 | 35,617 / 35,620 | 99.9916% |
| B | 10,479 | 18,036 / 18,039 | 99.9834% |

All rejected requests in these sessions returned a duplicate/invalid source timestamp; no accepted frame lacked the complete required lip/eye groups. The largest accepted-label gap was 68.333 ms. These are tracking and interpolation coverage measures, not independent landmark accuracy scores. Sparse A training stills show visible lips, closed/open/rounded shapes and natural blinks. Detailed phoneme timing remains to be reviewed.

Decoded mono audio occasionally exceeds full scale: 102 samples in A and 42 in B at the chosen 16 kHz derivative rate. Working WAV gain is approximately 0.776 and 0.777 respectively. Lossy decoder/resampling overshoot can exceed full scale; these counts do not prove capture clipping or its absence. Original recordings are unchanged.

The source verification, prepared-input digest checks and C exclusion were verified locally. The full repository regression suite passes all 725 tests, including ten new corpus integrity/timing/isolation checks; full Ruff passes. The native extractor successfully processed both sessions. No browser surface changed in this delivery, and no new model fit or final-test score is claimed.

C receives predefined source-integrity, packet-timing and full-decode checks only. No C images are viewed, QC stills retained, dense motion targets prepared, normalization fitted or model score calculated. The preparation CLI and downstream training loader expose only A/B. Final test extraction requires a later evaluation path after model selection is frozen.

## Next model experiment

Use A alone to fit normalization, mouth targets, appearance statistics and calibration templates. Use B to select speech-to-mouth candidates against linear, amplitude and static baselines. Retain the current portrait while testing natural motion; the camera scene differs from its studio lighting and appearance.

Before a final test, review train/validation phoneme timing and geometric tracking around closures, rounded vowels and head movement. Container synchronization is preserved, but energy/aperture correlation alone does not establish phoneme alignment. The new speech objective should measure mouth opening and width alongside landmark error so a nearly static prediction cannot pass through a weak aggregate score.

After selection, freeze the candidate and evaluation settings, prepare C with the same extractor and evaluate once. This corpus comes from one person and setup; it does not establish generalization to other identities or capture conditions. Step 4 remains Active until timing/control calibration passes; Step 5 remains Active until a useful model beats appropriate baselines. Streaming remains the following stage.
