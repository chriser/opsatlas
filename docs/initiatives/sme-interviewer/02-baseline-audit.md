# Atlas and Azure DevOps baseline audit

**Observed 19 September 2026. Baseline commit: `c7e6ff7` — Merge rollback of Ask ontology regressions.** An authenticated fetch confirmed local `HEAD` and `origin/main` were identical before this documentation work. This is a code/documentation audit with offline regression checks, not a fresh acceptance of deployed runtime data or a new real-model benchmark.

## Evidence examined

The audit used the current repository and its working agreement/handover; all 823 live project work-item records including fields and relationships; all 53 live wiki pages downloaded for review, with detailed reading of relevant architecture, governance, evidence and working-agreement pages; and the user's final **DT603 Part A** PDF and **DT603 Part B** DOCX. Earlier DT602 papers and local research notes supplied historical context.

The DT603 documents confirm local-first operation, a 21-document approved corpus, disabled Anam input audio, human-controlled knowledge approval and a 210-pair internal review taking more than 35 hours. Those are reported historical results. They do not prove that a future interview system is real-time or production-ready. The papers remain local reference files and are not uploaded to ADO or committed as part of this initiative.

The checked-in [README](../../../README.md), [architecture status](../../../ARCHITECTURE_STATUS.md), source code and accepted [benchmark record](../../benchmark/oag/README.md) describe the current implementation more accurately than several early wiki pages. Untracked architecture notes, analytics notes and August benchmark files present when this task began remain untouched and uncommitted.

## Implemented capabilities and reuse boundary

| Capability | Code evidence | Implication for interviewer |
|---|---|---|
| Source registration, ingestion and approval | `sources/`, `ingestion/`, `api/routes_sources.py`, `api/routes_governance.py` | Reuse durable source lifecycle; do not bypass approval |
| Document retrieval | `api/routes_query.py`, `retrieval/service.py` | `POST /api/query` can retrieve bounded evidence; lacks an immutable session snapshot contract |
| Written answers and refusal | `api/routes_ask.py`, `answer/` | Preserve existing `POST /api/ask` behaviour; it is a synchronous answer endpoint, not an interview engine |
| Ontology objects, links and traversal | `ontology/store.py`, `ontology/query.py`, `api/routes_ontology.py` | Read structured facts with provenance; resolve approval eligibility explicitly |
| Governed actions and proposals | `ontology/actions.py`, `ontology/proposals.py` | Useful pattern, but current proposals are action-specific and not an interview adjudication ledger |
| Process Registry and diagrams | `process/`, `services/process_diagram/` | Approved source content drives process projections; structured interview export must match parser expectations |
| Enterprise Activity Model | `eam/`, `frontend/src/EnterpriseActivityModelPage.tsx` | Preserve all five implemented views; use approved process changes to enrich them |
| Quick Scan and Full Governance Review | `governance/`, `services/compliance_reasoning/` | Quick Scan is source hygiene, not semantic contradiction detection; Full Review belongs outside conversational timing |
| External evidence | `external/`, `regulatory/`, `api/routes_external.py` | Bounded registered public snapshots; neither all legislation nor a live authoritative legal feed |
| Analytics and improvement actions | `analytics/`, `value/` | Reuse vocabulary and approved actions; keep interview events distinct from established answer metrics |
| Digital SME | `api/routes_avatar.py`, `frontend/src/AvatarLabPage.tsx` | Anam renders Atlas answers; not local speech recognition or an autonomous conversational interviewer |
| Simulator and Process Stress Lab | `simulator/`, `process/stress.py` | Synthetic diagnostics; not evidence of live operational facts |
| Identity | `api/auth.py` | One operator password and in-memory tokens; no user roles, source ACLs or verified SME authority |
| Delivery | `azure-pipelines.yml`, `tests/` | Existing automated quality gates and GitHub mirroring remain in place |

## Integration findings requiring explicit treatment

**B01 — Rebuildable graph.** `ontology/sync.py::rebuild_ontology` clears the graph before reconstructing it. Direct interview object writes would be lost unless their durable inputs and projection are also implemented. Keep session claims in the new service and publish approved source records; test replay after rebuild.

**B02 — Graph presence is not approval.** `_sync_sources` stores metadata for every registered source, while process derivation filters approved sources. Compliance findings and evidence claims also enter the graph through review synchronisation. The adapter must distinguish source metadata, proposed findings and approved facts, follow their provenance, and fail closed when eligibility cannot be established. Do not treat raw `/objects` output as a trusted fact pack.

**B03 — No interview publication contract.** Existing ontology actions include source approval/rejection/editing, rebuild, snapshots and improvement actions. There is no `publish_interview`, claim-level approval, idempotent interview import or general signed assertion action. These require an additive core-owned integration slice; reusing the proposal UI alone is insufficient.

**B04 — No version-consistent read pack.** Existing routes can supply relevant data, but do not guarantee one atomic approved-source snapshot across multiple calls. The first spike may use a manually prepared immutable synthetic pack. Before live integration, add a bounded read-pack adapter with source versions/hashes, approval eligibility and invalidation rules. A repeated manifest read is a detection aid, not a transactional guarantee.

**B05 — Synchronous model boundary.** `models/provider.py` exposes `generate(prompt) -> str`, and `/api/ask` returns a completed result. Streaming audio, cancellation, partial transcripts and interview state are new capabilities. Put them in the separate service rather than changing Ask's contract.

**B06 — Identity is a PoC boundary.** The auth implementation stores tokens in a set without implemented time-based expiry, despite its introductory wording describing short-lived tokens. It cannot substantiate named reviewer signatures or per-person permissions. Use a clearly labelled single-operator approval in the synthetic PoC; identity/roles and expiry are prerequisites for real multi-user use.

**B07 — Source metadata is limited.** `SourceRecord` tracks version/hash, approval and processing state, with synthetic/anonymised sensitivity values. It has no claim-level effective date, applicability, revocation lineage or accountable reviewer identity. Avoid adding all interview state to that model. Prove a minimum immutable approval manifest and durable source mapping first; extend schema only under an agreed migration contract.

**B08 — Review runtime is material.** DT603 reports 210 pair comparisons over more than 35 hours. Recent handovers document precision/recall corrections and capped false positives. Reusing this review synchronously, or promising completion during a five-minute break, is unsupported. Compare new/changed claims with a bounded candidate set and report remaining coverage honestly.

**B09 — Rolled-back work is not current capability.** The latest Git history explicitly reverts two Ask/ontology investigation fixes. No current live work-item title clearly records that rollback in the audited project set. A follow-up completed-PR query returned only the earlier platform-foundation PR #1, with no matching rollback PR. Preserve `c7e6ff7`; retain traceability Task #1514 for Human disposition and do not silently reinstate reverted code.

## Live ADO state before new initiative

| Work-item type | State counts |
|---|---|
| Epic | 10 Closed; 1 Removed |
| Feature | 64 Closed; 5 Removed |
| User Story | 258 Closed; 16 Removed |
| Task | 280 Closed; 28 Removed |
| Bug / Issue | 56 / 2 Closed |
| Test Case | 92 Closed |
| Test Plan | 3 Inactive; 1 Active |
| Test Suite | 6 Completed; 1 In Progress |

All non-test delivery records are Closed or Removed. The legacy Active plan #1262 and In Progress suite #1263 do not establish unfinished product development. Leave them as historical records; no Test Plans APIs or new test artifacts are needed.

Voice Epic #116, Feature #119 and Stories #124/#128 are Removed. Local-avatar Feature #1016 and OpenVoice/MuseTalk Story #1021 are also Removed. Delivered Digital SME Stories #874 and #951 concern Anam presentation. The new interviewer is a new initiative, not a reactivation or claim that old voice scope was delivered.

The live project has only its root area, with Post-build and Future Roadmap iterations already available. New discovery goes under Post-build; proposed build and future work use the undated Future Roadmap iteration. Existing four-sprint delivery dates are not changed.

## Documentation reconciliation

| ID | Observed discrepancy | Treatment |
|---|---|---|
| D01 | `/Project-Overview` still describes DT603 as future work | Add dated pointer to current baseline; retain historical text |
| D02 | `/Delivery-Management/Module-Status` still marks delivered modules Planned | Point to current implementation map and this audit; separate interviewer status |
| D03 | Early voice/design pages describe prospective STT/cloud options | Label as historical; current Atlas voice input is absent and interviewer inference must be local |
| D04 | `/Final-Evidence/Evidence-Index` still promotes July OAG 67/72 vs 47/72 | Point to accepted repo final result: 68/72 OAG-first, 53/72 RAG-only, 48/72 OAG-only; preserve old evidence as history |
| D05 | Some wiki file references were removed during repository cleanup | Use current canonical links; record stale references rather than recreating obsolete artifacts |
| D06 | Old DoD and Testing pages require ADO Test Cases | Record 19 September instruction: no new ADO UAT test cases; acceptance evidence remains required |
| D07 | Four-sprint page refers to future Epic #1289, absent from WIQL; a direct GET also returned 404 (“does not exist, or you do not have permissions”) | Record unresolved historical reference in #1514; absence does not establish deletion. Do not recreate, delete or infer its disposition |

The initial research audit is complete to the scope above. Historical ticket discussions were not exhaustively re-read; no claim is made to audit every former test run, pipeline execution or runtime source file. Work-item fields/relations and the most relevant live wiki material support this reconciliation.

## Baseline verification

On `c7e6ff7`, `KP_DATA_DIR` was redirected to a temporary isolated directory for the full backend regression suite: **450 passed**, with one existing Starlette/httpx deprecation warning. Repository-wide Ruff passed. No new tests were written for these documentation changes. No frontend or runtime code changed, so a new browser acceptance run and frontend rebuild were not needed for this planning delivery.

The accepted 621-execution RAG/OAG benchmark is historical evidence, not rerun here. Preserve its bounded domain and holdout interpretation. Real-model interviews, speech latency, listening preferences and concurrent Atlas load remain unmeasured.
