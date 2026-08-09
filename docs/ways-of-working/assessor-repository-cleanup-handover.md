# Assessor Repository Cleanup Handover

## Scope

This branch curates the visible repository into a concise representation of the
delivered OpsAtlas proof of concept. Git history remains the audit trail for
removed development artefacts. Application behaviour, source data, Azure DevOps
history and accepted benchmark results are outside the cleanup scope.

## Pre-change inventory

### Proposed removals

- Generated ADO Wiki export under `exports/wiki/`.
- Generated ADO diagnostics and the PoC delivery-plan schema under
  `automation/azure_devops/`.
- Historical ADO scripts tied only to the removed avatar PoC or generated
  diagnostics.
- Abandoned avatar implementations under `poc/`.
- Superseded DT602 context and duplicate architecture artefacts.
- Historical OAG and compliance benchmark run collections.
- Superseded June benchmark presentation files that are not runtime fixtures.
- Assessment-specific traceability and submission evidence under
  `docs/evidence/`.
- Dated architecture-status documentation superseded by the root status file.

### Proposed relocations

- Analytics validation protocol to `docs/validation/analytics-validation-protocol.md`.
- Grounding evidence to `docs/validation/answer-grounding-validation.md`.
- Value hypothesis to `docs/validation/business-value-model.md`.
- Process Stress Lab method and operator guide to
  `docs/validation/process-stress-lab.md`.
- Industry rationale to `docs/architecture/industry-context-and-decisions.md`.
- Accepted August RAG/OAG output to the final benchmark JSON and Markdown files.

### Proposed rewrites

- `README.md` for the final local-first hybrid RAG/OAG platform.
- `ARCHITECTURE_STATUS.md` for implemented module status and boundaries.
- OAG benchmark method/decision documentation using the accepted August run.
- RAG/OAG architecture notes and stale core-module benchmark references.
- A concise knowledge-governance validation record for the accepted
  21-document, 210-pair review.

### Dependencies identified

- `tests/test_industry_decision_rationale.py` reads the old evidence document
  and exported ADO Decision Log; it will target the professional architecture
  decision document instead.
- `src/assistant/evidence/validation.py` and
  `src/assistant/value/default_assumptions.json` reference evidence paths that
  will move to `docs/validation/`.
- Current tests and evaluation scripts retain their fixtures under `tests/`;
  these are not part of the benchmark-history deletion.
- Process Stress Lab remains a visible delivered capability, so its method is
  consolidated rather than removed.

## Safety notes

- The branch was created with unrelated untracked operator files present. They
  are preserved and are not part of cleanup commits unless explicitly listed as
  accepted final evidence.
- The accepted August OAG result was found locally and reconciles to 69
  questions, 3 configurations, 3 runs and 621 executions. No benchmark rerun is
  required.
- The local `.env` is ignored and is not read, staged or reported.

## Completion record

### Repository curation

Completed on branch `chore/assessor-repository-cleanup` in four core commits:

| Commit | Purpose |
|---|---|
| `9d571b5` | Remove superseded generated exports, avatar experiments, duplicate context files and benchmark history. |
| `9c2ceda` | Consolidate the accepted RAG/OAG benchmark and professional validation records. |
| `b3bd988` | Rewrite the repository overview and architecture documents for final OpsAtlas. |
| `ddbd950` | Repair references, remove one-off ADO construction scripts and finish product branding cleanup. |

The visible tracked repository now retains:

- product code under `src/`, `frontend/` and `services/`;
- runtime, import and reproducible evaluation tools under `scripts/`;
- automated tests and labelled evaluation fixtures under `tests/`;
- six reusable, read-only ADO inspection/export utilities;
- final architecture, benchmark, data-governance, validation and authentic
  ways-of-working documentation.

Git history retains removed intermediate material. No application data reset,
governance review, ontology rebuild or benchmark rerun was performed.

### Final benchmark confirmation

The accepted local result generated on 5 August 2026 was reused from:

`docs/benchmark/oag/rag-vs-oag-rag_only-oag_first-oag_only-2026-08-05T16-10-27+00-00.json`

The source filename above is an untracked operator artefact. Its verified content
was retained as `docs/benchmark/oag/rag-vs-oag-final-benchmark.json` with a
concise Markdown interpretation. The run contains 69 questions, three
configurations, three repetitions and 621 executions.

Holdout results:

| Configuration | Passed | Accuracy | Route accuracy | Stable | Mean latency |
|---|---:|---:|---:|---:|---:|
| RAG-only | 53/72 | 73.61% | 50.00% | 22/24 | 3.84s |
| OAG-first | 68/72 | 94.44% | 100.00% | 23/24 | 1.32s |
| OAG-only | 48/72 | 66.67% | 83.33% | 24/24 | 0.03s |

The benchmark was not rerun. The accepted evidence supports OAG-first as the
preferred hybrid route for the proof of concept, with document RAG retained for
narrative and mixed questions.

### Security and privacy checks

- No tracked `.env`, PEM, key, credential, secret or private-key filename was found.
- The repository-root `.env` is ignored and was not read or staged.
- High-risk GitHub, AWS, OpenAI and private-key token-pattern scans returned no match.
- Keyword hits were reviewed as expected environment-variable names, login code,
  pipeline secret references, test fixtures or authentic historical handover text.
- No current product document contains a local absolute path.
- `gitleaks` was not installed, so no additional gitleaks scan was run.
- `npm audit --omit=dev` reported zero production dependency vulnerabilities.
- The full npm audit reported four development-tool findings in the existing
  Vite 5 toolchain: one moderate and three high. The Vite fix is a major-version
  upgrade and remains a separate dependency-maintenance decision.

### Verification

| Check | Result |
|---|---|
| `ruff check .` | PASS |
| Full backend suite | PASS: 449 tests; one existing Starlette/httpx deprecation warning |
| Focused report/validation regressions | PASS: 6 tests |
| `npm ci` | PASS |
| Frontend production build | PASS: 625 modules, 0.874s Vite build |
| Repository-local Markdown links | PASS; ADO Wiki-root links in authentic ways-of-working documents are intentionally external |
| `git diff --check` | PASS |

The frontend build retains a non-failing warning for an 819 kB minified main
chunk. Cleanup changed no retrieval, ontology, governance, source, benchmark or
model-routing algorithm, so no expensive runtime performance or model benchmark
was repeated.

### Preserved operator files

Unrelated untracked local files present before cleanup remain untouched. They
include alternate benchmark exports, ADO exports, local research notes, value
ledger outputs and a comprehensive architecture draft. They are not part of the
cleanup commits and must not be included accidentally during merge preparation.

### Human review boundary

- The delivered Analytics validation API/UI retains its existing KSB-named
  compatibility schema. Removing or renaming that runtime contract would be an
  application change rather than repository curation and requires a separate
  product decision.
- No local browser smoke test or live Anam call was required; API behaviour is
  covered by the complete backend suite and the Control Panel compiled cleanly.
- Do not merge or push to `main` until the cleanup branch has completed human UAT.
