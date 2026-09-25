# OpsAtlas SME Interviewer

**Discovery baseline: 19 September 2026. G0 design accepted by the Human in the follow-up conversation; isolated E1 implementation is authorised. The standalone synthetic interview is implemented with selected Voice B, saved revisions and unpublished drafts; acoustic and later acceptance gates remain pending.**

Build a locally operated voice interviewer that helps subject matter experts describe processes, clarifies gaps and apparent contradictions, and prepares traceable knowledge for human approval in OpsAtlas. It should feel attentive and useful to the contributor. Atlas remains the authority for approved organisational knowledge.

The recommended first increment is a single English-speaking SME using a browser and headset, with a separate interview service and a new Atlas page. Start with synthetic process content and a pinned, read-only Atlas evidence pack. Produce a reviewable interview packet before enabling knowledge publication. The Human accepted this initial scope and confirmed a Mac Studio M4 Max (16-core CPU, 40-core GPU, 64 GB unified memory). The initial synthetic fixture is sufficient; a real pilot process/owner is a later decision. Voice: the Human selected Higgs TTS 3 with a British male reference on 24 September 2026 (female alternative available); the earlier interim choice was Kokoro Voice B (British female).

The important design distinction is between **what someone said**, **what evidence supports**, and **what an accountable owner approves**. A conversation cannot establish absolute truth merely by reaching agreement. Accepted knowledge must specify its scope, conditions, effective dates, provenance and owner; unresolved claims remain unresolved.

## Read the proposal

| Document | Purpose |
|---|---|
| [Structured brief](01-brief.md) | User requirements, boundaries and traceability |
| [Atlas and ADO baseline](02-baseline-audit.md) | What exists, what is historical, and what integration needs |
| [Research and technology options](03-research.md) | Primary sources, model shortlist, psychology, channels and hardware |
| [Service architecture](04-architecture.md) | Service boundaries, live/deferred validation, contracts and knowledge lifecycle |
| [Interview experience](05-interview-experience.md) | Conversation behaviour, interruptions, challenge and contributor control |
| [Evaluation and delivery](06-evaluation-and-delivery.md) | Measurable gates, experiments, sequence and non-regression rules |
| [Decisions and open questions](07-decisions.md) | Established requirements, proposed ADRs, owner decisions and risks |
| [Backlog](08-backlog.md) | Epics, Features, Stories, Tasks, ownership and dependencies |
| [Publication and handover](09-publication.md) | Verified ADO links, source-control evidence and remaining actions |
| [G0 acceptance and supplied reading](10-readiness-and-reading.md) | Confirmed hardware, book editions, policy refinements and readiness |
| [Initial prototype and measurements](11-prototype.md) | Running audition, Voice B decision, benchmark evidence and remaining acoustic tests |
| [Complete synthetic interview](12-synthetic-interview.md) | Saved sessions, checked local questions, correction history, draft export and remaining work |
| [Conversation checkpoint history](13-conversation-checkpoint.md) | Rejected earlier trial and local-only recovery audit |
| [Local conversational iteration v4](14-local-conversation-iteration.md) | Current synthetic prototype, continuity fixes, local generated questions and remaining quality limits |
| [Thinking and comprehension iteration v5](15-thinking-and-comprehension-iteration.md) | Explicit-outcome continuity, visible/spoken thinking cues, measured local latency and pipeline recovery |
| [Low-latency conversation architecture v6](17-low-latency-conversation-architecture.md) | Two-stage local planning, delayed filler, storage/retrieval decision and measured warm latency |
| [Independent review of plan and iterations](16-independent-review.md) | Conversational-core findings, ADR-013 to ADR-017, published backlog additions and order of work |
| [Instruction to Codex](18-codex-instruction.md) | What to build next, in what order, and what to stop doing |
| [Conversational core: accepted plan and timing foundation](19-conversational-core-delivery.md) | Delivery record |
| [Combined conversation-core increment](20-conversation-core-increment.md) | Delivery record |
| [Continuous voice and recap](21-continuous-voice-increment.md) | Delivery record |
| [Conversation pace candidate](22-conversation-pace-candidate.md) | Delivery record |
| [Expressive local conversation research](23-expressive-conversation-research.md) | Delivery record |
| [Experience lab: voice comparisons and listening policy](24-experience-lab.md) | Delivery record |
| [Charles (Pocket TTS) conversation candidate](25-charles-conversation-candidate.md) | Delivery record |
| [Attentive listener prototype](26-attentive-listener.md) | Delivery record |
| [Recognition and visible recovery](27-recognition-recovery.md) | Delivery record |
| [Contextual small talk and expressive delivery](28-social-conversation.md) | Delivery record |
| [Chatterbox selection and live audio continuity](29-chatterbox-audio-continuity.md) | Delivery record |
| [Knowledge architecture comparison](30-knowledge-architecture-comparison.md) | Delivery record |
| [Tiberius sales workspace and product recall](31-tiberius-sales-workspace.md) | Delivery record |
| [Tiberius attributed product interviews](32-tiberius-product-interviews.md) | Delivery record |
| [Tiberius conversational repair](33-tiberius-conversational-repair.md) | Delivery record |
| [Tiberius conversational layers](34-tiberius-reasoning-layers.md) | Delivery record |
| [Voice audition and reviewed improvement loop](35-voice-benchmark-and-learning.md) | Delivery record |
| [Voice selection reset](36-voice-research-reset.md) | Delivery record |
| [Private evaluation: Breeze, Fish and Higgs](37-private-three-model-evaluation.md) | Delivery record |
| [Higgs female/male comparison](38-higgs-female-male-comparison.md) | Delivery record |
| [Higgs selected for local sales rehearsal](39-higgs-sales-voice.md) | Delivery record |
| [Natural answers and earlier Higgs speech](40-natural-sales-delivery.md) | Delivery record |
| [Independent review 2: speed, grounding and retrieval (24 September)](41-independent-review-2.md) | Current |
| [Review 2 delivery: streamed, grounded Tibi and measured latency](42-review-2-delivery.md) | Current |

## Current delivery priority

On 24 September 2026 the Human accepted [independent review 2](41-independent-review-2.md) and assigned its remediation (Feature #1695, Stories #1696–#1718) to Claude, keeping Higgs as the live voice and deferring the voice-licence decision (#1717) while Tiberius remains an evaluation. [Review 2 delivery](42-review-2-delivery.md) records what changed and the measured latency. The G1.5 gate (#1590) remains the Human's decision. Earlier priorities, including the conversational-core order in [19](19-conversational-core-delivery.md), are history.

## Accepted direction for the isolated trial

1. Keep the Atlas core intact; introduce a separately deployable local service behind an Atlas UI feature flag.
2. Use a controllable ASR → interview policy/LLM → checked text → TTS pipeline. Evaluate voice naturalness separately from factual and conversational correctness.
3. Separate bounded live clarification from asynchronous evidence review. A delay changes the review state, never the standard for approval.
4. Keep the interview ledger outside Atlas's rebuildable graph. Publish only approved, durable source material through Atlas-owned commands.
5. Evaluate Kokoro and one expressive challenger on the target hardware before selecting the voice. No hosted voice or LLM service is required.
6. Preserve the DT603 delivery record. This initiative has its own backlog; no new Azure Test Plans, Test Suites or Test Case work items are required.

## Delivery boundary

The initial research publication created the design and backlog. The follow-up [speech prototype](11-prototype.md) now provisions local models and provides an isolated voice audition with microphone transcription. The [standalone synthetic interview](12-synthetic-interview.md) adds a revisioned ledger, checked local question planning and unpublished draft export. Real Atlas evidence, Atlas navigation integration and approved-knowledge publication remain later work. It does not change existing Atlas application code, dependencies or Anam behaviour, book meetings or approve knowledge. G0 acceptance authorises the isolated trial. Benchmark outcomes, production suitability, approved-corpus publication and real-participant deployment are not accepted by implication.

The user's explicit request authorises Codex to perform this initiative's research, documentation and backlog creation despite the older role table assigning those activities to other agents. Human ownership of scope, architecture agreement, data decisions and final acceptance remains intact.

- [Continuous voice, recap and measured limitations](21-continuous-voice-increment.md)
- [Expressive conversation research and approved lab direction](23-expressive-conversation-research.md)
- [Experience lab: voice comparisons, listening policy and PersonaPlex spike](24-experience-lab.md)

The current priority is acoustic experience and conversation flow. The user has
reopened voice selection, including male British candidates, and approved an
isolated experience lab before further feature expansion. Human naturalness and
end-to-end acceptance gates remain open.

- [Charles conversation candidate and resource findings](25-charles-conversation-candidate.md)
- [Attentive listener: social actions, memory and isolated practice](26-attentive-listener.md)
- [Recognition final pass and visible recovery](27-recognition-recovery.md)
- [Contextual small talk and expressive delivery](28-social-conversation.md)
- [Chatterbox selection and live audio continuity](29-chatterbox-audio-continuity.md)
- [Knowledge architecture comparison and recommended backlog changes](30-knowledge-architecture-comparison.md)

- [Tiberius sales workspace and initial product recall](31-tiberius-sales-workspace.md)

- [Tiberius iteration 3: product interviews and review](32-tiberius-product-interviews.md)
