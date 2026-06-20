# Module Status

This page tracks the maturity of each architecture module across the delivery slices.

## Purpose

The module status page prevents the project from becoming unclear as the build grows. It shows what exists, what is planned, what is blocked and what evidence is available.

## Status scale

| Status | Meaning |
|---|---|
| Not started | No implementation or evidence yet |
| Planned | Backlog item exists but no build evidence yet |
| In progress | Work has started |
| MVP | Basic working version exists |
| Hardened | Tested and improved version exists |
| Evidence captured | Screenshots, logs or tests are available |
| Deferred | Out of scope for current submission |

## Module status table

| Module | Related slice | Current status | Target outcome | Evidence location |
|---|---|---|---|---|
| Source and Data Governance | Slice 0 / Slice 1 | Planned | Source register, data rules, anonymised/synthetic data controls | Evidence Index |
| Ingestion and Preparation | Slice 1 | Planned | Source loading, section builder and metadata tagging | Evidence Index |
| Knowledge and Indexing | Slice 1 / Slice 2 | Planned | Basic retrieval index, then retrieval quality improvement | Evidence Index |
| Assistant API and UI | Slice 1 | Planned | User can ask a process question and receive structured answer | Evidence Index |
| RAG Orchestration | Slice 1 / Slice 2 | Planned | Evidence pack, constrained prompt and grounded answer | Evidence Index |
| Model Runtime | Slice 1 / Slice 2 | Planned | Provider abstraction and draft answer generation | Evidence Index |
| Validation and Safety | Slice 2 | Planned | Citation support checks, confidence and refusal handling | Evidence Index |
| Observability and Audit | Slice 2 / Slice 5 | Planned | Trace logs, model/prompt version and validation outcomes | Evidence Index |
| Analytics and Insight | Slice 3 | Planned | Usage logs and knowledge-gap analysis | Evidence Index |
| Voice Services | Slice 4 | Planned | Speech-to-text and text-to-speech around canonical answer | Evidence Index |
| Build and Evaluation | Slice 0 / Slice 5 | Planned | Test cases, golden questions, regression checks | Evidence Index |
| Delivery Governance | Slice 0 | Evidence captured | Azure DevOps backlog, Wiki, repo, Delivery Plan and first pipeline run are available | Evidence Index |

## Slice 0 evidence note

The initial Azure DevOps governance baseline has been created. This includes the project, repository, Wiki, architecture pages, Evidence Index, Decision Log, Risk Log, AI-Assisted Development Log, Module Status page, Test Cases, Delivery Plan, dependency chain and first successful placeholder pipeline run.

## Review notes

Update this page after each sprint review. The status should reflect actual evidence, not optimistic intent.
