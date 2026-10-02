# First local avatar specification

The first avatar will animate one person speaking English in a fixed scene on the Mac Studio. We will learn a small speech to face motion model, then decide how to render that motion convincingly. This specification freezes the initial experiment so that quality and device performance can be compared fairly.

These are initial engineering choices within the requested local avatar work. They can be revised explicitly after the first measurements. No performance target below is an observed result.

## Visible behavior

| Property | First experiment |
|---|---|
| Identity | One user supplied portrait, local asset identifier `avatar_a` |
| View | Frontal head and shoulders; fixed camera and background |
| Language | English; no commitment to other languages yet |
| Motion | Mouth, jaw, blink and restrained head movement |
| Rotation | Initially within approximately 10 degrees of neutral yaw and pitch |
| Body | Static shoulders; no generated arms or hand gestures |
| States | Listening, speaking, waiting and yielding |
| Deployment | One session on the Mac; avatar inference works without a hosted avatar API |
| First visual milestone | Inspectable head with explicit controls; identity realism is a later renderer milestone |
| Audio | Fixed locally generated or recorded audio during evaluation; a cloned voice is a separate project |

The supplied 1122 by 1402 PNG has a clear, mostly frontal face and a stable background. It is suitable for an identity reference. Its smile and visible teeth can bias portrait animation toward an open mouth; the beard obscures some lip boundaries. Those are risks to inspect, not evidence that the photo is unusable. A second, neutral portrait with relaxed closed lips would be helpful later. The initial setup uses the supplied image unchanged.

## Components we train and components we reuse

| Component | Plan and provenance |
|---|---|
| Speech to facial motion | Our first model, initialized with random weights; tentative size 1 to 5 million parameters |
| Audio features | Log mel features, computed locally; frozen extraction settings |
| Face representation | Explicit mouth and jaw controls, then additional controls if labels justify them |
| Face tracking and label extraction | An existing tool may be used; record its weights, licence and limitations before adoption |
| Head geometry and initial renderer | Authored or appropriately licensed controls and browser rendering; no claim that we trained geometry from a photo |
| Listening behavior | Rules first; a learned action controller only after measured failures |
| Identity renderer | A later restricted experiment; explicitly distinguish our weights from pretrained rendering components |
| Recognition, speech and answer engine | Existing components may be reused later; their training is not part of the first avatar model |

A causal temporal model will consume audio features and predict a compact vector of face controls. An initial candidate is temporal convolutions followed by a small recurrent layer. The renderer turns those controls into visible frames. This separates the learning problem from the expensive task of generating every video pixel.

Step 3 defines the initial twelve-control vector in `experiments/local_avatar/web/rig-schema.json`, with [documented ranges, coordinates and mechanical constraints](04-step-3-face-controls.md). Jaw opening and lip closure are separate so that “p”, “b” and “m” are not represented by jaw movement alone. Step 4 must validate recovery of these controls from video and freeze feature settings before long capture or training. Any change to control meaning, order or units requires a new contract version.

## Data and evaluation rules

Step 4 begins with approximately 20 to 30 minutes of aligned pilot speech video, then asks whether the coverage and labels are adequate. That quantity is a pilot plan, not a claim that it guarantees realistic motion. A still photo alone is insufficient supervision for this model.

Split by recording session or contiguous segments with a buffer between splits. Never randomly distribute adjacent frames into training and evaluation. Compute normalization from training data only. For this one identity experiment, hold out recording sessions; any future model claiming identity generalization must also hold out identities.

`evaluation-cases.json` contains 20 speech prompts and additional behavior scenarios. It is a frozen evaluation specification, not measured video or generated audio. Produce the audio once in Step 2 or Step 4, record its hash, voice and sample rate privately, and use exactly the same waveform across candidates. Do not train on these prompts or adjacent recording material. Pauses are annotated events; punctuation alone does not prescribe a measured pause duration.

Evaluate both silent mouth and a simple rule based speech motion baseline. Inspect short synchronized clips as well as numerical face control error. A lower numerical loss is insufficient if the visible mouth, teeth or identity becomes less stable.

## Initial performance targets

| Measurement | Proposed first gate | How to measure |
|---|---|---|
| Render output | 30 frames per second at a 1280 by 720 canvas; a lower face resolution is allowed | Frame times and dropped frames for a 10 minute run |
| Motion cadence | 50 predictions per second | Timestamp spacing; resample against the playback clock |
| Incremental audio to visible motion | p95 at most 200 ms after the required audio is available | Audio availability timestamp to presentation of the corresponding frame; report any lookahead and buffering |
| Synchronization | p95 absolute audio/video skew at most 80 ms; maximum 150 ms | Playback timestamps and manually inspected plosive events |
| Interruption | p95 at most 200 ms from accepted cancel event to stopping obsolete audio and motion | Same generation identifier for audio and animation; report microphone decision delay separately |
| Stable playback | Fewer than 1 percent dropped frames and no growing queue over 10 minutes | Queue depth, frame counters and time series |
| Device memory | Initial lab budget 24 GB peak process footprint; report GPU allocations separately | Peak process memory, framework allocation and system memory pressure |
| Concurrent use | Measure with Tibi's normal models loaded before integration | Separate idle, avatar only and concurrent results; no unmeasured concurrency promise |

The audio to motion target excludes answer reasoning and speech synthesis. The interruption target begins after the controller accepts a cancellation; it is not a claim about microphone end-to-end latency. Neither target is directly comparable to vendor figures with different boundaries.

Record cold start separately from steady state. Passing a tiny MPS operation shows GPU access, not sustainable rendering speed or training throughput. The 24 GB budget is provisional and does not reserve the remaining memory from other services.

## Visual and behavioral review

For each fixed speech case, record lip closure, audio alignment, face and teeth stability, background stability and motion plausibility as pass, fail or uncertain. Keep the reviewer and evidence reference with the result. For listening scenarios, score false interruptions and missed interruptions separately.

An acceptable first motion model should beat both baselines on held out controls without introducing repeated visible jitter, and should keep the mouth still during silence. Identity realism is judged only after a renderer exists. There is no present claim of Anam or Tavus equivalence.

## Completion of Step 1

The local deliverables are the scoped specification, fixed cases, portrait inventory, isolated empty environment and machine preflight. Remaining completion work follows the repository delivery process: review, scoped commit/merge, verification evidence and handover. No runtime model package is necessary for this step. Step 2 supplies the first actual model and renderer smoke benchmarks.
