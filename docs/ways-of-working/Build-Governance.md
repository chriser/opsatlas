# Build Governance

The way we build matters as much as the next feature. This project is a **modular monolith** with clear internal boundaries (source governance, ingestion, knowledge & index, RAG orchestration, model runtime, validation, voice, analytics, build/test, delivery governance, observability) — those boundaries are what keep iterative delivery safe.

## Module-scoped stages
- Every stage specifies its **target module(s)**.
- Every stage lists files/dirs that may be edited and those that **must not** be.
- Every stage defines success output and test commands.
- Every stage updates module status and known limitations.

## Commit discipline
- Commit only after focused + full regression tests pass.
- Keep module-focused changes separate from unrelated fixes.
- Clear, `#id`-scoped messages (e.g. `slice-1-ingestion-section-builder`).
- Keep `ARCHITECTURE_STATUS` and the relevant Wiki pages updated in the same change.

## Work tracking
- **Epics = delivery slices**, Features = capability increments, User Stories = small testable outcomes, Tasks = implementation work; acceptance criteria define "done".
- Status moves **New → Active → Resolved → Closed**; progress + outcomes captured in the work-item discussion (see [Definition of Done](/Ways-of-Working/Definition-of-Done)).

## Governance docs (Slice 0)
Create in the repo and mirror into this Wiki: `ARCHITECTURE_STATUS.md`, `BUILD_GOVERNANCE.md`, the High-Level Architecture Artefact, and the AI-assisted-development / agent operating model. Each AI-assisted task must be tied to a backlog item, scoped to a module, reviewed through source control and evidenced through tests.

_Linked: [Agent Collaboration](/Ways-of-Working/Agent-Collaboration) · [Definition of Done](/Ways-of-Working/Definition-of-Done)_
