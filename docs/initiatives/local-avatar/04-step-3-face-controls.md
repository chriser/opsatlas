# Step 3: explicit face controls and an authored head

On 2 October 2026, Story #2107 adds a deformable practice head to the independent local lab. It has twelve named controls, eight inspection presets, guide points and a validated local pose export. This defines what a future speech motion model will predict. No speech motion weights or portrait renderer have been trained.

The initial contract is `local-avatar-head-controls`, version `1`, asset `authored-head-v1`, stored in `experiments/local_avatar/web/rig-schema.json`. The reference photo remains unchanged and private. The practice head is generic authored geometry; it is not reconstructed from that photo.

## Control contract

All controls have neutral value zero. The first nine use normalized values in `[0, 1]`; the final three use radians in `[-π/18, +π/18]`, approximately ±0.174533. Head sliders display degrees in the range ±10°. Exports always use radians. Vector order is the table order and is included explicitly in every saved pose.

| Index, zero based | Control | Meaning of increasing the value |
|---|---|---|
| 0 | `jawOpen` | Rotate weighted lower-head vertices down and backward around the jaw pivot; increase aperture unless lips are sealed |
| 1 | `lipClosure` | Reduce the lip aperture to its minimum, independently of jaw rotation |
| 2 | `lipRound` | Narrow the mouth and move the lip ring toward the camera |
| 3 | `lipSpread` | Widen the mouth |
| 4 | `upperLipRaise` | Raise the upper lip when closure permits |
| 5 | `lowerLipDepress` | Lower the lower lip when closure permits |
| 6 | `smile` | Raise the mouth corners and slightly widen the lips |
| 7 | `blinkLeft` | Close the avatar's anatomical left eye, on the viewer's right |
| 8 | `blinkRight` | Close the avatar's anatomical right eye, on the viewer's left |
| 9 | `headYaw` | Turn the nose toward the viewer's right |
| 10 | `headPitch` | Point the nose down |
| 11 | `headRoll` | Move the top of the head toward the viewer's left |

Coordinates are right handed: X points to the viewer's right, Y up and Z toward the camera. Rotations apply yaw around Y, then pitch around X, then roll around Z. These definitions concern the rendered frontal view, not an imported camera coordinate frame. An adapter must preserve these signs and convert units explicitly.

The contract is our own initial representation. Its names do not establish compatibility with ARKit, FACS or any tracker's blendshapes. Step 4 must validate an explicit mapping if a tracker is adopted. Changing control order, meaning or units requires a schema version change and deliberate conversion of existing labels.

## How the mechanics work

The head begins as a 32 by 48 segment sphere scaled into an ellipsoid. Jaw opening rotates lower vertices around an authored pivot at `(0, -0.15, -0.10)`. The rotation grows with distance below the pivot; upper face vertices stay fixed. The maximum authored jaw angle is 0.28 radians, about 16°. Surface normals are recomputed when the jaw changes.

The lips are a separate 64-segment ring. Mouth width, height, projection and corner elevation come from explicit control equations. A fragment shader removes the corresponding mouth aperture from the front skin surface. A dark cavity, simple upper tooth bar and tongue sit behind it. These are inspection aids, not anatomical reconstruction or a watertight mouth mesh.

Lip closure multiplies upper and lower opening by `1 - lipClosure`. A small 0.003-unit half-height remains to avoid degenerate geometry; visually this is a closed lip line. The jaw can remain lowered while that line is closed. Rounding changes width and projection; spreading changes width independently. Smile curves the corners upward. Eyes have independently scaled lids and a closed-lid line. Head rotation applies to the whole face assembly; the shoulders and neck remain static.

This is a deliberately small rig. It has no cheek deformation, tongue articulation, lip contact simulation or learned appearance. Conflicting controls such as maximal rounding and spreading are numerically valid but may look artificial. P B M closure and the other poses are illustrative mechanical examples, not phoneme recognition or synchronized speech output.

## Inspect and export locally

Open <http://127.0.0.1:8790/>. No additional package or weights installation is needed after Step 2.

1. Inspect Neutral, Open mouth, P B M closure, Rounded lips, Wide lips, Smile, Blink and Small head turn.
2. Adjust the controls independently. Open the jaw, then increase lip closure: the chin remains lowered while the lip line closes.
3. Enable the eight guide points for the mouth corners, upper/lower lips, chin, two eyes and nose. They are generated from the rig, not detected from the portrait.
4. Expand **Control vector and coordinates** to inspect the ordered vector and named pose. Displayed numbers are rounded; the JSON preserves full precision.
5. Use **Save pose locally**. This freezes preview animation and atomically writes `avatar-rig-pose-v1.json` in the server's private runtime folder. Saving again replaces this one file. Moving a control clears the save confirmation.

The server accepts only the complete versioned contract, known manual/preset source labels, twelve finite in-range values and agreement between named values and the vector. It rejects foreign hosts and foreign-origin writes. The saved record is not served as a public asset and contains no portrait, recording, personal annotation or file path.

This export contains a single pose without audio or capture timestamps. It is not yet a dataset format. `AvatarRig.import()` supports a validated programmatic round trip; this delivery does not add a browser file-import control. Preview interpolation updates the displayed vector with the currently rendered pose.

## Measurements and verification

Measured in the visible in-app browser on the Mac Studio M4 Max, 64 GB, with pose preview and guide points enabled. The preview changes head vertices, recomputes normals and updates lips. Repository verification also ran on the workstation; this is an ambient-load observation, not a controlled idle benchmark.

| Measurement | Observed |
|---|---:|
| Canvas | 1280 × 720 |
| Duration | 30.0012 seconds |
| Drawn frames | 896 |
| Achieved cadence | 29.87 fps |
| Frame interval p50 / p95 | 33.3 / 34.1 ms |
| Render/update completion p95 | 0.9 ms |
| Estimated missed frames | 2 |
| Tab visibility interruptions | 0 |
| WebGL errors | 0 |

Timing includes synchronous rig, UI and WebGL updates plus `gl.finish()`. Interval timing also includes browser scheduling. Missed frames are estimated from interval gaps, rather than obtained from a display presentation counter. The private stable report is `.runtime/local-avatar/step-3-renderer-benchmark.json`.

Verification passed: 23 Python lab checks in the pinned environment, including native CPU/MPS agreement; 688 Python checks across the clean main-based delivery checkout; seven Node rig tests; full repository Ruff; and JavaScript syntax. Browser inspection checked neutral/open/closed/rounded/wide poses, head rotation, guide points and independent anatomical-left blinking. Saving during preview froze the pose, and the file matched the exact displayed JSON. No browser warnings or errors were observed. This plain HTML/WebGL lab has no npm package build step.

The Node tests check export/import compatibility, invalid values, independent closure/jaw movement, lip-shape distinctions, rotation signs, stable upper-face vertices, finite preset geometry and outward unit surface normals. Python tests check stale contracts, inconsistent vectors, bounds, same-origin pose saves and the server's restricted paths.

This completes the bounded Step 3 implementation and self-verification. Human acceptance remains separate. Ten-minute stability, actual lip synchronization, learned motion quality, photorealistic identity and concurrent Tibi conversation remain unmeasured.

## Source and licences

The mesh, deformation equations, shaders and control schema are authored in this repository. No external head asset, tracking model or pretrained renderer was imported. The browser uses native WebGL and ordinary JavaScript; it adds no third-party browser package. No repository-wide `LICENSE` file was found, so this delivery does not assign a new open-source licence to project code.

The isolated Python dependency licences and pinned versions remain those recorded in the [Step 2 evidence](03-step-2-runtime-and-benchmarks.md). The unchanged supplied portrait remains private identity material, outside the code and asset distribution. No ADO or Wiki upload includes that image or screenshots containing it.

## Step 4 gate

Before recording 20–30 minutes, capture a short calibration sample and verify that a selected local tracking or fitting method can recover these controls. Check relaxed lips, jaw opening, closure, rounding, spreading, blinks and small rotations. A tracker may be a reused pretrained component; record its licence and provenance separately from our future motion model.

Some controls may not be identifiable independently from a single frontal video. Measure that ambiguity instead of assuming twelve clean labels. Simplify or revise the contract before long capture if necessary. Only then freeze extraction settings, audio/video timestamps, quality masks and session-based splits. Keep evaluation prompts excluded from training. Step 4 remains a separate Story; this delivery starts no microphone or camera capture.
