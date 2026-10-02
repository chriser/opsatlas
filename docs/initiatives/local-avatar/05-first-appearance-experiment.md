# First local appearance experiment — #2113

The lab now produces changing mouth and eye regions on the supplied portrait. This is a restricted frontal appearance model, with a static head and background. It is not yet driven by audio and does not reproduce Anam's full system.

## What was learned and reused

The user supplied one short synthetic avatar recording and confirmed Anam as its source. It is used locally as identity-specific synthetic supervision, not natural camera motion. No contract-level rights beyond the user's supplied provenance are asserted. Private media, source integrity records, facial coordinates and trained weights remain in ignored runtime storage; none are published in git or ADO.

Apple Vision's built-in pretrained face landmark detector is reused. No pretrained avatar generator is downloaded. The renderer learns its appearance from these samples:

1. Decode timestamped frames approximately every 0.2 seconds, preserving the source video clock. Exclude the opening and visible screen overlay.
2. Align each face by eye centers into a canonical 256 × 256 crop. Convert Vision's bottom-left coordinates correctly. Extract a 96 × 64 mouth patch and a 128 × 48 combined eye patch.
3. Freeze contiguous, separated source sections: training 2–80 seconds, validation 94–110, test 118–130. Intervals are half-open; there are temporal buffers. The accepted counts are 353 / 73 / 54. All selected frames have one detected face. The masks are suitable for this restricted experiment, not a general capture protocol.
4. Fit normalization and 48 principal appearance components from training rows only. This data-learned decoder represents patch RGB values as a mean plus weighted components.
5. Compare a fixed mean image and regularized linear regression with our randomly initialized MLP: 64 inputs → 128 → 128 → 48, SiLU activations, 31,024 trainable parameters. AdamW trains 500 epochs; validation RGB MSE selects epoch 280. No test pixels enter the fitted basis, normalization, regression or checkpoint selection.
6. Evaluate the final checkpoint once on test landmark inputs. Render patches into the unchanged portrait with feathered masks. The final test locks out refitting this experiment directory.

The 64 inputs are tracked mouth/eye coordinates, not the twelve rig controls from Step 3. Landmarks contain more information than audio; this experiment does not prove audio can predict them. Three training-only landmark templates also provide an authored mouth cycle and independent blink schedule. Their interpolated geometry drives freshly predicted patches; no source frame retrieval or playback is used for generated previews.

## Observed results on the Mac

| Predictor | Test patch MSE, RGB in [0,1] | PSNR | Mouth MSE | Eye MSE |
|---|---:|---:|---:|---:|
| Fixed training mean | 0.003009 | 25.22 dB | 0.004120 | 0.001899 |
| Linear baseline | **0.001496** | **28.25 dB** | 0.002056 | **0.000935** |
| Neural MLP | 0.001733 | 27.61 dB | **0.001957** | 0.001510 |

The neural model reduces overall test MSE by 42.4% versus the mean, but its error is 15.9% higher than the linear baseline. Its validation error was better than the linear predictor; the final test exposes weaker eye generalization. These pixel metrics compare aligned source patches and do not establish perceived realism or audio synchronization. The test is a different time section of the same synthetic recording, not an independent session or identity.

Training took 5.94 seconds on Metal. The checkpoint occupies 7,367,797 bytes, mostly the learned RGB basis. Fit-process RSS reached 671 MB; MPS driver allocation was a 1.10 GB end-of-run snapshot, not a peak or a separate sum with unified RAM. Preparation and other services are excluded. No additional GPU service is needed for this experiment.

Warm CPU prediction for **both** neural and linear RGB patches: p50 0.228 ms, p95 0.377 ms over 200 batch-one observations. CPU portrait compositing at 560 × 700: p50 2.74 ms, p95 3.23 ms. Tracking, encoding, browser transport and audio processing are excluded; this is not an end-to-end real-time avatar benchmark.

Visual inspection of authored and held-out output confirms changing lips and eyelids, sealed and open mouth states, retained overall identity and stable background. Teeth are soft, mouth texture can look dark against the reference, and eyelid closure/lighting vary. Head motion is absent by design. The source-patch comparison also reveals appearance mismatch introduced by compositing the synthetic recording onto the original photo.

## Feasibility decision and next work

Small identity appearance models can be trained and rendered locally on this machine. Keep the linear model as a strong baseline; the nonlinear model has not earned preference overall. This result supports another bounded experiment, not a production or Anam-equivalent quality claim.

Before an audio-driven avatar, finish Step 4's independent mouth/eye control calibration and perceived timing check using the useful audio channel with its original offset. Capture a separate camera session with closed lips, clear vowel shapes, full blinks and limited head turns for stronger data and an independent test. A later experiment should improve mouth/eye detail and blending, measure temporal stability, and compare a convolutional decoder against these baselines. Do not tune this checkpoint using its now-inspected test section.

The local lab at `http://127.0.0.1:8790/` opens the portrait previews when artifacts exist. `/rig` retains the control experiment. The authored and held-out neural clips are silent. The comparison is fixed mean / linear / neural / source patches, with the final column explicitly labelled as source reconstruction. Only these named private media routes are exposed on loopback; datasets, checkpoints, coordinates and manifests are not served.

Source: `experiments/local_avatar/appearance.py`, `appearance_evaluate.py`, `track_faces.swift`. Reproduction commands and data boundaries are in the lab README. Step 4 remains Active because speech alignment, calibrated controls and a sufficient motion corpus are outstanding. Step 9's restricted experiment can be reviewed independently.
