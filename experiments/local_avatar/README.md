# Local avatar device and renderer lab

An independent Step 2 experiment for ADO Story #2106. The model consumes synthetic tensors and predicts arbitrary numerical controls. The browser draws an authored procedural head. Neither component recreates the supplied portrait or learns real speech articulation yet.

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
```

Tests verify causality, actual gradient updates, CPU/MPS prediction agreement where Metal is available, bounded report validation, and restrictions on paths, foreign hosts and foreign-origin writes. Run MPS and loopback checks on the Mac outside a tool sandbox that hides GPU access or blocks local sockets. CPU fallback is not silently enabled.

Reports, environments, media and screenshots remain under ignored `.runtime/local-avatar/`. The server does not serve manifests, credentials or arbitrary files. The neural probe and renderer are independent tests; there is no learned motion connection between them yet. Step 3 will define a suitable face representation before data capture and speech-to-motion training.
