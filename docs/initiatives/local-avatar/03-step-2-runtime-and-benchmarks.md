# Step 2 runtime and device benchmark

On 2 October 2026, the isolated lab was installed and tested on the Mac Studio M4 Max with 64 GB memory. A small model completed forward and backward operations on CPU and MPS. A procedural WebGL head ran locally with the supplied unchanged portrait displayed as a separate reference.

This establishes a usable experiment environment. It does not demonstrate a learned talking portrait, photorealistic reconstruction, real speech features, lip synchronization or Anam/Tavus parity.

## Installed stack

The environment at `.runtime/local-avatar/.venv` uses Python 3.12.12 and does not inherit system packages. The runtime dependency lock independently pins PyTorch 2.14.0, NumPy 2.4.6 and nine transitive packages. The development lock also pins pytest 9.1.1, ruff 0.15.18 and their dependencies. Installation uses package hashes.

PyTorch's installed licence expression is `Apache-2.0 AND Apache-2.0 WITH LLVM-exception AND BSD-2-Clause AND BSD-3-Clause AND BSL-1.0 AND MIT`. NumPy's is `BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0`. This records the package notices rather than reducing a bundled distribution to one licence. No model weights, face asset library or external tracking tool was downloaded. The head geometry and shaders are authored in this experiment.

## Model measurements

The model has 745,612 parameters, random initialization with seed 20261002, a causal convolution, a two-layer GRU and twelve numerical outputs. Inference input shape is 1 by 16 by 80; training input shape is 8 by 32 by 80. Both use float32 and four CPU threads. The input and target tensors are synthetic.

| Measurement | CPU | MPS |
|---|---:|---:|
| Warm inference p50, 100 samples | 0.381 ms | 3.789 ms |
| Warm inference p95, 100 samples | 0.428 ms | 4.219 ms |
| First inference | 2.116 ms | 592.493 ms |
| Training step p50, 20 samples | 12.769 ms | 20.389 ms |
| Training step p95, 20 samples | 13.199 ms | 22.531 ms |
| First training step | 13.711 ms | 1188.021 ms |
| Initial synthetic loss | 0.014491 | 0.014491 |
| Final synthetic loss after 20 steps | 0.001688 | 0.001688 |

Gradients were finite and parameters changed on both devices. The loss reduction verifies optimization on an artificial target; it says nothing about facial motion quality. A separate test checks CPU/MPS prediction agreement within an explicit tolerance.

The small CPU probe was faster than MPS. My interpretation is that CPU execution is a credible option for a small motion controller, leaving GPU capacity for heavier components. This experiment does not establish the device choice for a larger model or real audio features.

The combined CPU then MPS benchmark reached a process peak RSS of 597,999,616 bytes, approximately 570.3 MiB. At the end of its MPS segment, tensor allocation was 12,078,080 bytes and driver allocation was 36,470,784 bytes. RSS includes earlier CPU work and allocations; the allocator readings are end snapshots. They are not additive estimates of whole-system unified memory use.

## Renderer and overlap measurements

The authored head has jaw opening, lip closure, blink and limited yaw controls. Preview animation is a deterministic procedural example. The neural probe does not drive it. The user portrait is displayed unchanged beside the head and is not uploaded or animated.

| Measurement | Renderer baseline | Renderer with a bounded GPU probe during the run |
|---|---:|---:|
| Canvas | 1280 by 720 | 1280 by 720 |
| Duration | 30.018 seconds | 30.001 seconds |
| Drawn frames | 900 | 899 |
| Approximate achieved cadence | 29.98 fps | 29.97 fps |
| Frame interval p95 | 34.1 ms | 34.1 ms |
| Draw completion p95 | 0.2 ms | 0.2 ms |
| Estimated missed frames | 1 | 0 |
| Tab visibility interruptions | 0 | 0 |
| WebGL errors | 0 | 0 |

The second renderer run overlapped a synthetic MPS probe for approximately 7.93 seconds of its 30-second window. That probe used 200 inference samples and 300 training steps, plus queued matrix computation. Its warm inference p95 was 3.837 ms and training step p95 was 21.501 ms. Its process peak RSS was 484,458,496 bytes, approximately 462.0 MiB. The slight timing differences from the first probe are not a controlled demonstration of improvement under load.

Aggregate machine load and VM snapshots before and after both model runs are in the private JSON reports. Tibi's health endpoint identified the running service during preparation; this does not establish that Higgs and the answer model were actively computing during measurement. A controlled quiet-machine baseline and a real concurrent Tibi conversation have not been measured. The current observations are ambient-machine and lab-overlap results only.

The ten-minute button is available for later sustained checks; a ten-minute run has not been performed for this delivery. No audio playback or speech synchronization target has been tested.

A final 30.017-second check after refining the closed-lip visualization drew 897 frames, with a 34.1 ms frame interval p95, a 0.2 ms draw completion p95, three estimated missed frames, no tab visibility interruptions and no WebGL errors. The latest private `renderer-benchmark.json` and `lab-preview.jpg` record this final check; the table above records the earlier baseline and overlap observations.

## Reproduction and next step

Verification passed: 11 focused tests in the pinned lab environment; 676 tests and full lint in the clean main-based worktree; and 1,253 tests against the existing working branch. Existing deprecation warnings remain. JavaScript syntax was checked, the page was inspected in the local browser, controls were exercised, and the browser reported no console warnings or errors. The plain HTML/WebGL surface has no package build step.

An unrestricted lint run in the original working directory encountered 679 errors in existing temporary research scripts. Those files were not changed. The clean delivery worktree passed `ruff check .`, with only avatar files added to the main base.

Run the commands in `experiments/local_avatar/README.md`. The independent server is <http://127.0.0.1:8790/> and uses no existing service port or launchd job. Runtime reports and the screenshot remain private under `.runtime/local-avatar/`.

Step 3 should establish a controllable face representation, particularly separate jaw opening and lip closure, before Step 4 captures aligned recordings. Do not start long recordings or import a large pretrained portrait renderer until those choices and device requirements are checked.
