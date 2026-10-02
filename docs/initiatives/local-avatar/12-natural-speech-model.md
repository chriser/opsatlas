# Natural camera speech-to-mouth model

The next experiment trains a small model from random weights using the independent [natural camera corpus](11-natural-camera-corpus.md). A supplies training and all fitted statistics; B selects candidates. C remains sealed, so the results below are **validation**, not a final test or an Anam-quality claim.

## Mechanics

Camera A provides lip/eye coordinates through the existing local Apple Vision tracker. The new target uses the twenty outer/inner lip points and removes outer-lip translation. This keeps opening, width and relative shape while excluding head-position shifts. It does not learn head rotation, jaw angles or blink behavior.

Audio becomes eighty causal log-mel features at 50 timestamps per second, using 25 ms windows. Three causal convolutions with 64 channels, five-sample kernels and dilations 1/2/4 provide 560 ms of history. An eight-output projection predicts mouth components. The network has **67,272 parameters**, initialized randomly; no pretrained speech or avatar weights were downloaded.

Normalization and an eight-component PCA shape basis are fitted on A only. The basis retains 99.938% of A's centered shape variance. The objective combines training-scaled coordinate, opening-ratio and width error; low-aperture examples receive extra aperture weight. A small velocity term also applies. This addresses the earlier nearly static candidate's weakness without turning detector coordinates into ground-truth muscle controls.

Continuous target runs are split into 160-frame training chunks with past-only context and masked padding. No chunk crosses a missing-label gap or a session boundary. A supplies 35,617 valid labelled timestamps and B 18,036. The fixed run used 120 epochs, batch size 16, AdamW, learning rate 0.0005 and seed 47. B was checked every five epochs and selected **epoch 65**. Later epochs reduced training error while validation fluctuated, so the last epoch was not selected.

## Timing and local cost

Original container/audio clocks are preserved. Energy/aperture correlation peaks at a roughly 40 ms mouth lead on A and 60 ms on B, with correlations only about 0.30/0.21. This is a weak technical diagnostic, not phoneme alignment, and no timestamp offset was tuned from it. Precise perceived closures and vowel timing still require review of the synchronized preview.

Training ran on MPS in **15.26 seconds**. Weights changed with finite gradient checks. The checkpoint, including fitted statistics and controls, is approximately 1.43 MB. Observed process peak RSS was about 630 MB and the MPS driver snapshot about 1.12 GB; these are different memory measures, not a combined model-memory requirement.

On CPU, 200 warmed calls to the selected mouth model and geometric decoder measured 0.273 ms p50 and 0.313 ms p95 for a 29-frame context. Audio feature extraction, image rendering, transport and cold start are excluded. This is not an end-to-end real-time avatar benchmark.

## Validation comparison

Selection uses the fixed combined coordinate/opening/width score with scales from A. Linear regularization is also selected on B. Static mean, closed-mouth and amplitude controls are retained.

| Predictor | Combined score, lower better | Centered landmark RMSE, canonical pixels | Opening-ratio MAE | Width MAE, canonical pixels |
|---|---:|---:|---:|---:|
| Neural, selected | 2.308 | 2.130 | 0.0434 | 3.401 |
| Linear | 2.816 | 2.345 | 0.0500 | 3.729 |
| Amplitude rule | 3.361 | 2.515 | 0.0556 | 4.126 |
| Fixed mean | 3.472 | 2.543 | 0.0562 | 4.146 |
| Closed mouth | 7.029 | 4.593 | 0.1027 | 3.999 |

The neural candidate reduces the combined score by 18.0% relative to linear and 33.5% relative to fixed mean. Landmark RMSE improves by 9.2% relative to linear. These measures use centered mouth targets in a 256-pixel canonical face; they are **not directly comparable** with the previous synthetic experiment's uncentered target/error values.

Predicted velocity RMS is 33.51 canonical pixels/second versus 27.73 for the tracked target, while the linear baseline is 40.24. The candidate moves more than the earlier weak model, but can still show jitter. Tracker noise also contributes to target velocity; neither low nor high velocity alone establishes quality.

## Preview and limits

The fixed preview interval was declared before fitting: B, source seconds 60–72. Audio-only predictions are held at the latest available 50 Hz timestamp for 30 fps output. A training-only neutral template maps natural mouth shape into the frozen earlier appearance decoder's domain. The closed-lip portrait, protected cheeks and 1.12/1.08 mouth proportions remain. Blinks are authored.

The loopback lab now opens the natural experiment when all named media, summary and completion markers exist. It includes the selected portrait, a four-column baseline/reference comparison, native ForceSDR camera playback and a contour diagnostic. The latter compares neural predictions with tracked B targets without face texture. Only the explicitly labelled reference views consume measured B mouth coordinates or source images.

The old image renderer still limits visible mouth opening and produces soft teeth/interior detail. Better motion scores do not establish photorealistic rendering or accurate perceived lip sync. This one-speaker model has not been tested on synthesized or other-speaker audio. No natural RGB appearance model, head animation, live microphone processing, voice generation or streaming is implemented in this step. Previous models, scores and source-reference routes are preserved.

All five previews decode fully; saved predictions were independently recomputed from the frozen checkpoint and A/B inputs. Browser playback, automatic pause between clips, contour playback and no console warnings/errors were verified. Full regression: **734 Python tests**, full Ruff, JavaScript syntax and seven Node rig tests pass. The standalone lab has no npm build. Personal data, checkpoints, coordinates, traces, source files and screenshots remain ignored and local; Wiki/ADO receive aggregate evidence only.

Steps 4/5 remain Active pending perceived timing/control review and a final independent test. Next, review B's motion/rendering limitations, freeze the candidate plus complete evaluation settings and then evaluate C once. Any subsequent tuning must use A/B and fresh final evidence. Natural appearance learning is a separate remaining renderer improvement.
