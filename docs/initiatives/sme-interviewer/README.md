# OpsAtlas SME Interviewer

**Discovery baseline: 19 September 2026. G0 design accepted by the Human in the follow-up conversation; isolated E1 implementation is authorised. The standalone synthetic interview is implemented with selected Voice B, saved revisions and unpublished drafts; acoustic and later acceptance gates remain pending.**

Build a locally operated voice interviewer that helps subject matter experts describe processes, clarifies gaps and apparent contradictions, and prepares traceable knowledge for human approval in OpsAtlas. It should feel attentive and useful to the contributor. Atlas remains the authority for approved organisational knowledge.

The recommended first increment is a single English-speaking SME using a browser and headset, with a separate interview service and a new Atlas page. Start with synthetic process content and a pinned, read-only Atlas evidence pack. Produce a reviewable interview packet before enabling knowledge publication. The Human accepted this initial scope and confirmed a Mac Studio M4 Max (16-core CPU, 40-core GPU, 64 GB unified memory). The initial synthetic fixture is sufficient; a real pilot process/owner is a later decision. Voice preference: British English female.

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
