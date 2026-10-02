# Local avatar model and research lab

This is a separate initiative requested on 2 October 2026. Its goal is to understand, train and run a small avatar system on a Mac Studio M4 Max with 64 GB memory. The first experiment uses one identity and a fixed scene. OpsAtlas and Tibi continue independently.

The first appearance component reconstructs mouth and eye patches from landmarks. A diagnostic speech-to-mouth model now predicts geometry from audio, but its neural candidate is weak and a linear baseline performs better. A still portrait supplies appearance, not examples of speech movement. Training a general video foundation model is outside this initial programme.

## Current delivery

Steps 1–3 establish the [specification](01-avatar-specification.md), [evaluation set](evaluation-cases.json), [setup](02-local-setup.md), [device probes](03-step-2-runtime-and-benchmarks.md) and [twelve-control practice head](04-step-3-face-controls.md). The [appearance experiment](05-first-appearance-experiment.md) learns mouth/eye patches on the supplied portrait. The [first speech experiment](06-first-speech-experiment.md) adds sound and audio-driven mouth predictions with baseline comparisons; quality gates remain open. A [revised camera protocol](07-camera-capture-protocol.md) specifies the next corpus. The [closed-lip portrait refinement](08-portrait-refinement.md) preserves cheek detail and reduces transferred smile creases, while keeping the original models and test scores frozen.

ADO is the source of truth for status. [The separate Epic](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/2099) has five Features and ten Stories. [The item map](ado-links.json) contains all links. Steps 1–3 have implemented deliverables; Step 4 remains in calibration. The user authorized bringing the restricted Step 9 appearance experiment forward using the short synthetic pilot. Completion follows repository delivery checks and Human acceptance. Current status is recorded in ADO rather than inferred from local preparation.

The [ADO Wiki specification and setup](https://dev.azure.com/chriser/015f63d3-2999-40cd-b296-d91830fd0950/_wiki/wikis/da01b6ff-ea03-4f38-9732-334fc2613632?pagePath=%2FLocal-Avatar) are published and linked from the Epic and Step 1 Story. The existing Wiki handover log has an entry for this initiative.

## Sequence and gates

The [natural camera corpus assessment](11-natural-camera-corpus.md) records the three independent sessions, frozen file roles and dense preparation path. Test session C remains sealed during calibration and selection.

| Step | Deliverable | Gate before continuing |
|---|---|---|
| 1 | Scope, portrait inventory and fixed evaluation | Know what we train, reuse and measure |
| 2 | Isolated dependencies and tiny device benchmark | Forward/backward, rendering and memory measured locally |
| 3 | Simple head with explicit face controls | Inspect neutral, closed lips, open jaw and small head rotation |
| 4 | Aligned pilot speech and motion data | Timing and labels pass inspection; session splits frozen |
| 5 | Small speech to motion model from random weights | Improvement over simple baselines on held out sessions |
| 6 | Streaming motion and coordinated interruption | Audio clock alignment and cancellation pass replay |
| 7 | Rule based listening behavior | Wait, continue and yield behave appropriately |
| 8 | Learned controller experiment if rules fail | Improvement justifies the additional model |
| 9 | Restricted renderer for one identity | Quality, provenance and device cost justify further work |
| 10 | Optional Tibi adapter and concurrent benchmark | Same-input comparison and stable sustained conversation |

Each ADO Story represents a bounded first experiment, not the entire production capability. Estimates are provisional relative effort. They do not predict data sufficiency, GPU training time or parity with Anam or Tavus. Expand successful experiments into smaller delivery stories as evidence emerges.

## Boundaries

The lab uses `.runtime/local-avatar/` for personal assets, recordings, local manifests, environments and checkpoints. That directory is ignored by git. The photo and any recordings are not attached to ADO or the Wiki. Tracked documents and evaluation texts use generic asset identifiers.

Tibi's speech, knowledge engine, ports, launchd jobs and dependencies are unchanged. An integration must be optional and tested later. Any external GPU use, paid service or upload of identity material requires a separate decision; none is needed for the initial scope and tiny local experiments.

The underlying research is in `docs/context/anam-local-avatar-research-2026-09-26.md` and `docs/context/tavus-deep-research-2026-10-02.md`. Those documents are research inputs, not instructions to deploy their listed models.
