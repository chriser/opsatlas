# Local avatar device and renderer lab

An independent local lab for ADO Stories #2106, #2107 and #2113. The original motion probe consumes synthetic tensors and predicts arbitrary numerical controls. The practice head has twelve authored face controls. The new restricted appearance experiment learns mouth/eye RGB patches from a user-supplied synthetic recording and composites predictions onto the supplied portrait. Speech-to-motion training remains outstanding.

## Install and run

Use native Apple Silicon Python 3.12. From the repository root:

```sh
python3.12 -m venv --without-pip .runtime/local-avatar/.venv
UV_CACHE_DIR="$PWD/.runtime/local-avatar/uv-cache" uv pip sync \
  --python .runtime/local-avatar/.venv/bin/python --require-hashes \
  experiments/local_avatar/requirements-dev.lock
.runtime/local-avatar/.venv/bin/python -m experiments.local_avatar.benchmark
.runtime/local-avatar/.venv/bin/python -m experiments.local_avatar.server --port 8790
```

Open <http://127.0.0.1:8790/>. The server is loopback only and is separate from the existing services. It serves named lab files rather than a directory. The optional identity reference comes from `.runtime/local-avatar/reference/avatar_a.png`; the lab still works when the portrait is absent. Stop the foreground server with Ctrl+C. No launchd job is installed.

The runtime lock pins PyTorch 2.14.0, NumPy 2.4.6 and their transitive dependencies with hashes. The development lock also pins pytest 9.1.1 and ruff 0.15.18. These packages are installed only in the lab environment. No pretrained weights are downloaded. Package licence expressions are recorded in the delivery evidence; bundled notices remain in the installed distributions.

## Measurements

The seeded 745,612-parameter probe has a causal convolution, two GRU layers and twelve arbitrary output controls. Inputs are 80-dimensional random vectors. Synthetic targets verify gradient updates; they are not extracted audio or human facial motion. CPU is explicitly tested as an alternative to MPS. PyTorch's [MPS backend](https://docs.pytorch.org/docs/2.14/notes/mps.html) provides native Apple GPU execution.

The benchmark synchronizes device work before timing it. It records first use separately, samples warmed inference, tests finite gradients and weight changes, and records process peak RSS plus current MPS allocations. RSS is a process lifetime high-water mark, not a per-model memory sum. MPS allocation values are snapshots, not allocator peak measurements. Feature extraction, transport, audio playback and the renderer are excluded from model timings.

The browser uses a 1280 by 720 WebGL canvas and a target cadence of 30 fps. Draw timing calls `gl.finish()` to include submitted GPU completion. Frame intervals include browser scheduling. The tool records tab visibility changes and estimated missed frames. Run it in a visible foreground tab. Browser reports are observations supplied by the browser, not a server attestation of hardware performance.

For a bounded overlap probe, start the browser's 30-second measurement and run:

```sh
.runtime/local-avatar/.venv/bin/python -m experiments.local_avatar.benchmark \
  --devices mps --iterations 200 --train-steps 300 --contention-proxy \
  --output .runtime/local-avatar/device-overlap.json
```

This adds queued matrix work and overlaps the training probe with the renderer. It is not a controlled Higgs/LLM conversation benchmark. A real concurrent Tibi conversation remains a later integration gate.

## Verify

```sh
.runtime/local-avatar/.venv/bin/python -m pytest experiments/local_avatar/tests
.runtime/local-avatar/.venv/bin/ruff check experiments/local_avatar
node --test experiments/local_avatar/tests/test_rig.mjs
node --check experiments/local_avatar/web/renderer.js
```

Tests verify causality, actual gradient updates, CPU/MPS prediction agreement where Metal is available, bounded report and pose validation, and restrictions on paths, foreign hosts and foreign-origin writes. Node's built-in test runner verifies geometry, jaw/closure independence, rotation signs, surface normals and pose round trips; it needs no npm packages. Run MPS and loopback checks on the Mac outside a tool sandbox that hides GPU access or blocks local sockets. CPU fallback is not silently enabled.

## Inspect and save a face pose

The versioned contract is `web/rig-schema.json`; geometry and validation are in `web/rig.mjs`. Choose Neutral, Open mouth, P B M closure, Rounded lips, Wide lips, Smile, Blink or Small head turn. Adjust the twelve sliders independently and enable the eight mouth, eye, nose and chin guide points. Preview cycles through the authored poses; it does not follow audio.

Expand **Control vector and coordinates** to inspect the exact ordered numbers. Head sliders display degrees but the pose uses radians. **Save pose locally** freezes any preview and atomically replaces `avatar-rig-pose-v1.json` under the server's runtime folder. The same-origin endpoint rejects incompatible schemas, inconsistent vectors and invalid values. This is a single manual pose record, without capture timestamps; it is not a motion dataset. The browser does not upload it to an external service. Subsequent control changes clear the save confirmation.

Reports, environments, poses, media and screenshots remain under ignored `.runtime/local-avatar/`. The server does not serve saved poses, manifests, credentials or arbitrary files. The neural probe and renderer are independent tests; there is no learned motion connection between them yet. [Step 3 definitions and measurements](../../docs/initiatives/local-avatar/04-step-3-face-controls.md) describe the initial training target and the label calibration needed before Step 4 capture.

## Restricted appearance learning

Use the existing isolated environment, system ffmpeg and Apple's built-in Vision framework. No additional Python package or pretrained avatar download is required. For a new experiment, create an **empty** private output directory, copy `appearance-split.example.json` into it as `split.json`, and customize/freeze its contiguous intervals and exclusion mask before preparation. Set actual source provenance privately. The example intervals assume a 130-second or longer recording; a shorter input requires different intervals.

```sh
.runtime/local-avatar/.venv/bin/python -m experiments.local_avatar.appearance prepare \
  --source /absolute/path/to/local-recording.mov \
  --reference /absolute/path/to/portrait.png \
  --output .runtime/local-avatar/appearance
.runtime/local-avatar/.venv/bin/python -m experiments.local_avatar.appearance fit \
  --epochs 500 --output .runtime/local-avatar/appearance
.runtime/local-avatar/.venv/bin/python -m experiments.local_avatar.appearance_evaluate \
  --output .runtime/local-avatar/appearance
```

Preparation verifies extraction order and freezes source/data/split digests. Fitting learns input normalization, a PCA RGB decoder and ridge regression from training rows alone. A randomly initialized MLP predicts the 48 decoder coefficients. Validation selects regularization and the neural checkpoint; the final test is a separate command. Refitting or repeated evaluation after the final test is rejected. A new experiment needs fresh held-out evidence, not iteration on the previous test labels.

The prototype's source extraction is 792 × 594, and its supplied portrait input is 1122 × 1402; the current evaluation compositor expects those portrait dimensions. It deliberately supports a single frontal identity. It does not automatically process arbitrary capture shapes or the full twelve-control rig. Output previews use 560 × 700. Model evaluation, patches, weights and videos remain private. The browser's appearance page is the recorded first experiment, with its measured aggregate results; update it when a later experiment is delivered.

The root page shows appearance previews when `appearance/authored.mp4` exists; otherwise it opens the practice head. `/appearance` and `/rig` are explicit routes. The generated previews predict RGB patches from landmarks; only the fourth comparison column reads held-out RGB targets and is labelled as source reconstruction. Clips are silent; authored movement is not audio synchronization. [First experiment evidence](../../docs/initiatives/local-avatar/05-first-appearance-experiment.md) records the architecture, baselines, measured limits and next gates.
