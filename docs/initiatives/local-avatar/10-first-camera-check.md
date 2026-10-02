# First natural camera sample: setup check

The Human chose natural camera capture as the next stage, requested an exact recording script and supplied an approximately 89-second recording. It is assigned to setup and motion calibration before any fitting. It will not later be relabelled as an untouched final test. Original source, images, audio, facial coordinates and integrity manifests remain local under ignored runtime storage.

## Inspection results

The input contains 4K HEVC video at approximately 60 fps with a portrait display rotation, HDR HLG/BT.2020 color and a primary 48 kHz stereo AAC audio track. Analysis explicitly selects that primary audio track; the additional multi-channel audio and metadata tracks are not used. The original remains unchanged.

Apple AVAssetImageGenerator applies the preferred display transform and its ForceSDR policy to produce review/tracking images. This avoids judging skin exposure from an unmanaged HDR-to-PNG conversion. No new model or software package was downloaded. The resulting images are 640 × 1137 pixels, sampled at requested half-second intervals with actual source times recorded.

- All 178 sampled images contain exactly one complete Apple Vision lip/eye landmark set. This is a sampled setup check, not a guarantee of successful tracking on every video frame.
- Reviewed canonical crops show closed lips, a clear open mouth, rounded/narrow lips, a wide smile and a partially closed eye during a blink. Two-fps inspection can miss complete blink closure and fast consonant transitions; dense labels are still required before fitting.
- Video packets have no duplicate presentation timestamps. The median interval is about 16.667 ms and the maximum is 18.334 ms. No large recording gap was found in the packet clock audit.
- The full primary video and audio decode completes without errors; all 5,315 video frames are decoded. The private source fingerprint is rechecked after processing.
- The primary stereo channels have finite decoded samples and no near-full-scale samples. Their 16 kHz mono mix peaks at approximately 0.754 full scale. This establishes absence of digital clipping, not a measured signal-to-noise ratio or perceived speech clarity.
- Initial AAC packets start 44 ms before video time zero and specify 2,112 priming samples at 48 kHz. Accounting for that priming puts useful decoded audio at video time zero. Primary AAC packet timing residuals are about 1 microsecond; decoded audio lasts 88.596 seconds. No phoneme-based timing shift has been selected.

The clip is usable for motion calibration. Front-facing framing and visible lips supply useful shape coverage. Lighting and color differ from the studio reference portrait, so this sample is first a natural speech/motion source; a matching reference still would need its own alignment and presentation experiment. No improved appearance or speech-to-mouth model is claimed yet.

## Next collection

Keep the current clip as camera setup/calibration material. Collect the separate sessions in the [camera protocol](07-camera-capture-protocol.md): approximately 12 minutes for training, six minutes for validation and six minutes for the final test. Start a new recording for each role, use new sentences for validation/test, and assign roles before fitting. The initial [short script](09-camera-check-script.md) remains available for setup checks.

For the longer collection, 1080p/30 fps with HDR disabled is sufficient as a capture target and reduces local processing/storage compared with this 4K/60 fps clip. Use stable soft frontal light, a clear mouth and restrained head movement. A quieter, visually simple background and less bright light behind the head will make later appearance work easier. The current short clip does not need to be discarded or repeated solely because of its format.

Dense motion extraction, training/validation phoneme timing review, recoverable control calibration, session-level splits and a fresh model comparison remain to be done. The current synthetic-trained predictors, datasets, evaluations and private preview media are unchanged by this camera assessment. ADO Step 4 #2108 and Step 5 #2109 remain Active.
