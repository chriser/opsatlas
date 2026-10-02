# Closed-lip portrait refinement

The Human reported exaggerated creases around the generated mouth and supplied a more relaxed, closed-lip portrait. The first compositor replaced a broad ellipse containing the mouth, cheeks and beard. Its generated neutral patch carried expression and texture from the synthetic training clip into the portrait.

The new presentation uses the replacement image unchanged as its base. A training-only closed-mouth prediction anchors the animation: unchanged predictions preserve the photograph rather than replacing it with a softer generated neutral face. A narrow mouth mask protects the cheeks, nose and nasolabial folds; small eyelid masks protect the surrounding eye detail. Mouth alignment uses the reference lip position and width. When the mouth opens, the generated lip region replaces the original closed lip line, with local lighting correction. Blinks geometrically compress the reference eye texture according to the existing eye geometry; they no longer blend the soft learned eye patch against an open reference iris. This is a presentation rule, not newly learned eye behavior.

This is a presentation refinement, not new model training or a new test evaluation. Appearance and speech checkpoints, input datasets, splits and quantitative test reports remain byte-identical. The previously inspected test intervals can be rendered for comparison, but their earlier scores and timings do not evaluate the new compositor. No claim of independent-session generalization, improved perceived lip synchronization or parity with a hosted avatar is made.

## Private artifacts and activation

The original experiment and portrait remain intact. The replacement and all regenerated media live under ignored `.runtime/local-avatar/presentation-v2/`:

- `portrait/reference.png`: unchanged local copy of the supplied replacement.
- `portrait-landmarks.json`: locally extracted Apple Vision alignment points.
- `appearance/`: authored, held-out landmark and four-column appearance clips.
- `speech/`: selected, neural and four-column audio-driven clips.
- `manifest.json`: local reference and frozen-artifact integrity record, written after rendering completes.

The loopback server selects this revision only when its completion marker, reference and all six preview files exist. Until then it serves the previous experiment. The source-reference route continues to serve the original Anam excerpt. Fixed routes do not expose landmarks, checkpoints, manifests or arbitrary runtime files. Neither the reference nor generated media is committed or uploaded to ADO/Wiki.

For an already prepared private revision, run from the repository using the isolated avatar Python environment:

```sh
python -m experiments.local_avatar.portrait_revision \
  --runtime .runtime/local-avatar \
  --output .runtime/local-avatar/presentation-v2 \
  --audio .runtime/local-avatar/recordings/pilot-01/assessment/speech-channel0-normalized-16k.wav
```

The command loads frozen predictors and produces the same motion intervals with the new base and compositor. It performs no fitting or metric computation, checks the original artifacts before/after and refuses to overwrite a published revision. Further experiments must use a fresh private revision directory. The server chooses a complete `presentation-v3` first, then a complete `presentation-v2`; it accepts no arbitrary manifest-provided directory.

## Mouth proportion calibration

After reviewing the closed-lip refinement, the Human found the animated mouth slightly small for the head. Presentation revision 3 enlarges the animated region by 12% horizontally and 8% vertically around the reference lip center. The patch warp, generated lip support and replacement of the closed lip line use the same two scale factors. Neutral anchoring still preserves the supplied photo; scaling does not change the speech predictor's original geometry or its earlier measured errors. Cheek and eye animation remain protected. The factors are a subjective presentation calibration, not learned anatomical measurements or quantitative evidence of better realism.

The rendering CLI defaults to a fresh `presentation-v3` directory and the above scale factors. After copying the unchanged portrait and its existing local landmarks into that private directory, run:

```sh
python -m experiments.local_avatar.portrait_revision \
  --output .runtime/local-avatar/presentation-v3 \
  --mouth-width-scale 1.12 --mouth-height-scale 1.08 \
  --audio .runtime/local-avatar/recordings/pilot-01/assessment/speech-channel0-normalized-16k.wav
```

Finite scale factors between 0.85 and 1.30 are accepted. Tests check that mouth motion becomes wider while the neutral face, eyes and protected cheeks stay unchanged. Previous published revisions remain intact.

## Review and limits

Matched authored-motion frames show a more natural neutral face and less transferred cheek creasing. Visual review includes an opening mouth, return to closed lips, blink, the selected speech preview and all comparison clips. Mouth texture remains soft; eyelid rendering and lip synchronization remain imperfect. The head and background stay fixed. This change addresses the reported facial-line problem without solving those broader model limitations.

Automated checks verify neutral identity, protected facial regions, opening-mouth replacement, refusal to overwrite published revisions, complete-revision activation and privacy of runtime files. Delivery verification and the main commit are recorded on ADO Step 9 #2113; Human acceptance remains pending. Speech/data Steps 4 and 5 retain their existing open quality gates.
