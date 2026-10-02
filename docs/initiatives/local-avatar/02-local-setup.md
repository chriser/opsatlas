# Local avatar setup and next actions

Initial Step 1 setup on 2 October 2026 for the Mac Studio M4 Max with 64 GB memory. The lab has a private portrait reference and an isolated Python environment. Step 2 subsequently installed the pinned stack and ran synthetic training and renderer probes; see the [Step 2 measurements](03-step-2-runtime-and-benchmarks.md). No pretrained avatar model, voice cloning or live Tibi integration has been added.

## What is ready

| Check | Result |
|---|---|
| Existing Python | 3.12.12 |
| Existing PyTorch | 2.14.0 in the repository's existing environment |
| Metal GPU access | Verified outside the sandbox: four MPS tensor values sum to 4.0 |
| FFmpeg | 8.0.1 already installed |
| uv | 0.9.28 already installed |
| New isolated environment | `.runtime/local-avatar/.venv`, Python 3.12.12; created empty in Step 1 and populated from hash-pinned locks in Step 2 |
| Reference asset | Original PNG copied unchanged to `.runtime/local-avatar/reference/avatar_a.png`; dimensions and SHA256 checked privately |
| Private setup report | `.runtime/local-avatar/preflight.json` |

The initial existing PyTorch GPU check was an environment check, not a benchmark for the new environment. The isolated environment does not inherit existing packages. Step 2 installed and verified its own dependencies independently. `preflight.json` is the original Step 1 snapshot; the later model measurements are in `device-benchmark.json`.

In this tool sandbox, PyTorch first reported MPS unavailable. A tiny calculation succeeded outside the sandbox. uv also failed inside the sandbox during environment creation; the standard library created the environment successfully. Neither observation indicates that the Mac needs a driver repair.

## Inspect the prepared files

From the repository root:

```sh
.runtime/local-avatar/.venv/bin/python --version
.runtime/local-avatar/.venv/bin/python -m json.tool .runtime/local-avatar/preflight.json
open .runtime/local-avatar/reference/avatar_a.png
```

These commands inspect local files. Step 1 itself required no server. Step 2 now provides the separate lab at <http://127.0.0.1:8790/>; its startup instructions are in `experiments/local_avatar/README.md`.

## What you need to do

There is no software installation required from you for Step 1. Keep the original portrait available. A neutral portrait with relaxed closed lips would improve the next identity experiment, but the supplied smiling photo is sufficient to start.

Before Step 4, prepare a quiet recording location and camera with stable framing and lighting. We will first finalize a capture script and control representation, then record a pilot session. Do not spend time recording a long dataset before those choices and synchronization checks are ready. If accurate lip controls cannot be recovered from the video, change the capture method before collecting more.

## Next implementation slice

Step 2 has pinned the independent stack and measured a synthetic training probe and a simple head renderer. Step 3 should now define and refine a controllable face representation. Select larger pretrained components only after checking their licences, required operators and local speed.

The personal image, dataset, checkpoints, manifests and environment stay in `.runtime/local-avatar/`, which is ignored by git. The ADO hierarchy contains specifications and criteria only. Tracked setup documents contain no embedded portrait or personal recording.
