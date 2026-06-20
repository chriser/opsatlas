# Risk Log

This page records key delivery, technical, ethical, security and evidence risks for the AI Knowledge and Analytics Assistant project.

## Purpose

The risk log supports controlled delivery. It helps show that risks are identified early, reviewed regularly and linked to mitigation actions.

## Risk rating

| Rating | Meaning |
|---|---|
| Low | Manageable through normal delivery controls |
| Medium | Needs active mitigation and review |
| High | Could affect delivery quality, ethics, security or submission evidence if not managed |

## Risk log

| ID | Risk | Category | Likelihood | Impact | Rating | Mitigation | Owner | Status |
|---|---|---|---|---|---|---|---|---|
| R-001 | Confidential or sensitive data could be exposed if real process material is used incorrectly | Data / Ethics | Medium | High | High | Use anonymised or synthetic material unless approved controls exist; maintain source register and sanitisation rules | Project owner | Open |
| R-002 | Assistant may hallucinate or produce unsupported process claims | AI quality | Medium | High | High | Use RAG, evidence packs, citation checks, validation rules and refusal handling | Project owner | Open |
| R-003 | MVP may be delayed if too much is built before the first end-to-end flow | Delivery | Medium | Medium | Medium | Use vertical slices; prove MVP grounded Q&A by Sprint 3 | Project owner | Open |
| R-004 | Azure DevOps planning may become over-engineered and delay actual build work | Delivery | Medium | Medium | Medium | Limit planning enhancements after governance pages, test links and pipeline placeholder | Project owner | Open |
| R-005 | Voice interaction could bypass validation if implemented as a separate answer path | AI safety | Low | High | Medium | Voice must reuse canonical validated text response | Project owner | Open |
| R-006 | Analytics may overstate business impact if based on limited synthetic data | Analytics / Ethics | Medium | Medium | Medium | Clearly label analytics as proof-of-concept; avoid unsupported commercial claims | Project owner | Open |
| R-007 | AI coding assistance could create unreviewed or broad changes across the repository | Delivery governance | Medium | Medium | Medium | Link AI-assisted work to backlog items, restrict scope and review diffs/tests | Project owner | Open |
| R-008 | Test evidence may be incomplete if not captured progressively | Evidence | Medium | Medium | Medium | Maintain Evidence Index and capture screenshots after each slice | Project owner | Open |
| R-009 | Model/provider choice may change during build and affect architecture assumptions | Technical | Medium | Low | Low | Use provider abstraction and document model decisions in the decision log | Project owner | Open |
| R-010 | Retrieval quality may be weak if source sections are poorly structured | Technical / Quality | Medium | Medium | Medium | Use section builder, metadata tagging, golden questions and retrieval hardening in Sprint 4 | Project owner | Open |

## Review cadence

Risks should be reviewed at the end of each sprint and updated when new evidence, constraints or build issues appear.
