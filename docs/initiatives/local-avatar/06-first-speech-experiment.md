# First local speech to mouth experiment

The local pipeline now predicts mouth geometry from audio and generates facial patches on the supplied portrait, with the original speech attached. No test video or test mouth coordinates enter generation. Quality is still limited: the neural model under-expresses motion, and a trained linear baseline performs better. This is a diagnostic Step 5 experiment, not a completed speech avatar.

## Audio and target calibration

The source is the same user-confirmed Anam synthetic recording used for appearance learning. Decoded audio begins at source time 0.176062 seconds; the normalized mono waveform begins at that audio origin, not video time zero. An audit of decoded timestamps found sample-clock residuals no larger than 1 microsecond. Audio selection and gain correction reuse the privately assessed useful channel; no voice model is trained.

2,046 timestamped thumbnails were tracked locally with built-in pretrained Apple Vision, producing 2,031 accepted faces. The 15 failures occur in the opening or screen-overlay region, outside all fitted sections. Landmark intervals are 66.7 ms at the median and 83.3 ms at p95. No label interpolation across more than 150 ms is allowed. Interpolation onto the audio clock adds target samples, not independent observations.

Training-only picture inspection compared six samples, including minimum/maximum aperture and width. Closed lips, open mouth, narrower rounded lips and a wide smile agree with the geometric measures. Targets are canonical outer/inner lip positions; aperture is inner-lip height divided by outer-lip width. Width uses the 256-pixel canonical crop. These are geometric proxies, not calibrated jaw angles, independent lip closure muscles or the complete twelve-control rig.

Training audio energy and aperture correlate at about 0.53, with the largest observed correlation at a mouth lag of −60 ms. This broad diagnostic cannot establish phoneme alignment or justify a global correction. The original container offset is retained, with no timing selection on test. Human perceived lip-sync acceptance remains outstanding.

## Models and frozen evaluation

Intervals remain training 2–80 seconds, validation 94–110 and test 118–130, with temporal buffers and the opening/overlay excluded. At a 20 ms audio step, there are 3,900 / 800 / 600 target rows. These sections were previously inspected for appearance learning; they are not a fresh recording or independent session test. Within this speech experiment, test targets are excluded from fitted statistics and checkpoint selection.

1. Compute 80 log-mel bands with a 25 ms causal window, 20 ms hop, 512-point FFT and 16 kHz mono input. Each window ends at its output timestamp and reads no future samples.
2. Learn six principal mouth-shape components from training lip geometry, plus training-only feature and coefficient normalization.
3. Train an own random-initialized causal temporal network: 80 inputs, three 64-channel kernel-5 convolutions at dilation 1/2/4, SiLU activations and six outputs. It has 67,142 parameters and 28 past feature frames of history. The raw-audio span also includes the 25 ms analysis window.
4. Fit closed-mouth, training-mean, amplitude-rule and regularized linear spectral baselines. The linear model reads current and 100/200/400 ms past features. Predicted coefficients are bounded to training ranges.
5. Train 500 epochs with position loss and a small velocity term. Validation selects neural epoch 10 and linear regularization 1,000. Validation chooses the linear predictor for the primary preview; the final test is evaluated once and locked.
6. Decode predicted mouth components into landmarks, add an authored blink schedule from training eye templates, and use the unchanged Step 9 appearance checkpoint. Video uses the latest available 50 Hz mouth prediction at 30 fps, without future interpolation. Waveform seek equals source preview time minus the verified audio offset.

Both the linear and neural predictors are trained locally. The Apple tracker is reused; no pretrained speech-to-face or avatar generator is downloaded. No microphone input, live streaming, interruption handling, text-to-speech or cloned voice integration is added. Playback of generated clips is distinct from interactive inference.

## Measured results

| Predictor | Mouth landmark RMSE in canonical pixels | Aperture ratio MAE | Width MAE in canonical pixels |
|---|---:|---:|---:|
| Closed mouth | 7.199 | 0.0953 | 6.232 |
| Fixed mean | 4.303 | 0.0655 | 4.643 |
| Amplitude rule | 4.106 | 0.0589 | 4.619 |
| Linear spectral model | **3.938** | **0.0455** | **3.103** |
| Neural temporal model | 4.183 | 0.0532 | 3.907 |

Linear prediction reduces landmark RMSE by 8.5% versus the fixed mean and 4.1% versus the amplitude rule. The neural model improves on the fixed mean by only 2.8% and does not beat the amplitude rule on landmark RMSE. These are errors against tracked synthetic geometry, not scores for perceived realism or lip sync.

Target landmark velocity RMS is 38.17 canonical pixels/second, versus 29.19 for linear prediction and only 3.69 for neural prediction. The neural output is overly static; low jitter must not be reported as successful temporal quality. Velocity error also includes tracker noise. Visual samples show a changing mouth in the linear preview, but precise closures, vowels, teeth and blending remain weak. Blink timing is authored.

Training took 3.21 seconds on Metal. The speech checkpoint is 1,376,705 bytes. Fit-process peak RSS was 488 MB; end-of-run MPS driver allocation was 66 MB, a snapshot rather than a peak. Warm CPU evaluation of all five motion predictors and mouth decoding on a 29-frame context took p50 0.301 ms and p95 0.475 ms across 200 measurements. Feature extraction, appearance, compositing, encoding, transport and playback are excluded. This is not an end-to-end live-avatar benchmark.

Generated previews contain 360 video frames and corrected mono AAC speech, both starting at output time zero and lasting 12 seconds. Waveform seek is 117.84 seconds for source time 118.016062. Only audio features enter the predicted mouth branch. The comparison's last column uses measured test mouth geometry with the same learned appearance renderer and is labelled as a reference reconstruction.

## Decision and remaining gates

Keep the linear predictor as the diagnostic baseline. Do not prefer or enlarge the neural model on the strength of this result. A sufficient motion corpus and cleaner targets matter before model size. A hypothesis for the next run is to emphasize aperture/width or dominant geometric components instead of treating all six standardized components equally; this has not been tested.

Step 4 and Step 5 remain Active. A sufficient capture corpus, independent-session evidence, stronger motion quality and Human perceived timing acceptance are outstanding. The [revised camera capture protocol](07-camera-capture-protocol.md) specifies the next collection. Keep these checkpoints and inspected test results immutable; a subsequent candidate needs a fresh evaluation session.

The loopback lab opens speech previews when artifacts exist; `/speech`, `/appearance` and `/rig` remain explicit entry points. Personal recordings, coordinates, detailed traces, waveforms, datasets, weights and screenshots stay under ignored runtime. Only named preview media are served. No personal media or trained weights are attached to ADO/Wiki or committed to git.
