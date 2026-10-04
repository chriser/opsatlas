# Deep audit of OpsAtlas Sales: code, strategy, technology and clean-up (30 September 2026)

**Asked by the Human on 30 September 2026:** a very deep audit of everything delivered so far, covering code
quality, strategic direction, technology use and clean-up, including redundant code, slow processes and models that
are not used.

**Method.** Six reviews, all read-only:
- backend;
- services;
- frontend;
- models and runtime;
- repository and process;
- strategy.

The frontend, repository and strategy reviews were run by review agents. The backend, services, models and runtime
reviews were done directly with measurement scripts, after the usage limit stopped their agents. Every agent finding
used below was spot-checked, and three were corrected (listed in section 9).

**Evidence base:**
- the code at `claude/arch-h2` (d2aa229);
- the live workspace, read-only: sizes, counts, and the activity log of 26–30 September, counted by page only;
- Ollama's model list;
- git history;
- the benchmark runs of the day.

Nothing was deleted, and nothing was changed except one regression fix (section 2).

## 1. Summary

**The code is in better shape than the process around it.**
- **Function-level dead code is negligible:** 9 definitions and 46 lines in 30,800 lines of backend.
- **The frontend is clean:** it type-checks in strict mode in 3 seconds.
- **There are over 1,100 Python tests,** which run in under a minute.
- **Security is sound:** it has a real identity and access layer, and every route is classified.
- **Decisions rest on measurement:** changes go through pre-registered benchmarks.

**The fat is in three places.**
- **Whole features the Sales product no longer uses** are still wired in, tested and shipped. The biggest is the
  compliance-reasoning sidecar: 5,368 lines, switched off in Sales and still polled every 30 seconds. With it come the
  Classic-era diagnostics, the models behind them, and the alternate voice engines.
- **Evidence and history pile up.** `main` is 139 commits behind what runs. `docs/` has become half documentation, half
  raw evidence, and part configuration. The README's quick start exits with an error.
- **One configuration gap makes the product slow.** Every Product Guide answer takes 40–60 seconds, with a maximum of
  164 seconds. The likely main cause is one missing flag: the core's model call does not switch off `qwen3.5:4b`'s
  hidden reasoning, which Tibi already does for the same model.

**What changes if the backlog below is done:**

| Area | Today | After | Effort |
|---|---|---|---|
| Guide answer time | 40–60 s mean, 164 s maximum | Expected a few seconds; to be proven as hypothesis H3 | S to change, one benchmark to prove |
| Unused Ollama models | 62 GB installed | 25 GB removable: `deepseek-r1:32b` and `deepseek-r1:8b` | S, once the sidecar is removed |
| Voice runtime assets | 14 GB | About 4.4 GB of alternate engines removable; the live Higgs voice stays | M, needs an engine version and the replay gate |
| Code serving no live feature | about 10,000 lines | Removed, or parked in the frozen Classic version | M, needs the Human's decisions in section 4 |
| Initial download of the control panel | 985 kB JavaScript and an 811 kB logo | About 270 kB of JavaScript and a small logo | S–M |
| `main` against what runs | 139 commits and 531 files behind | Equal, and tagged | M |

**Recommendation: a consolidation fortnight, not new features.**
1. Make the guide fast (H3) and adopt H2.
2. Bring `main` level with what runs and tag it.
3. Remove what Sales does not use, after the decisions in section 4.
4. Fix the documentation's claims.
5. Only then take on knowledge-spaces phase 3, starting with its leak suite.

## 2. Defects found

| # | Defect | Severity | Status |
|---|---|---|---|
| D1 | The System page showed "Backend offline" and hid the models and the diagram-service controls. Since IAM, the public `/api/health` reports liveness only, and this page read it | High (introduced by IAM, today) | **Fixed**, d2aa229; live at the next restart |
| D2 | The core never sends `"think": false` to Ollama, so the model reasons silently before every answer. See section 5 | High (product speed) | Proposed as H3 (section 8) |
| D3 | Reloading or bookmarking an Analytics tab opens the Dashboard. The page writes `#analytics-<tab>`, which the router does not recognise | Medium | Backlog N2 |
| D4 | An anchorless `#document` or `#process-review` link crashes the whole console: `PlaceholderView` reads an undefined nav item, and there is no error boundary | Medium | Backlog N2 |
| D5 | Importing `assistant.api.app` builds a second Product Guide core (0.56 s). It leaves a stray, empty `core/iam.db` in the live guide partition, and a `data/` folder in worktrees, because of the module-level `app = create_app()` | Medium | Backlog N3 |
| D6 | 64 of the panel's 132 request functions replace the server's error with a generic "could not load…". Since IAM, a missing permission therefore looks like an outage | Medium | Backlog C2 |
| D7 | `tests/sme_experience_floor.test.mjs` never runs: CI's patterns miss it | Low | Backlog N5 |
| D8 | One parametrised test puts raw WAV bytes into its name: 23 million characters. That makes a 33.8 MB `.pytest_cache` | Low | Backlog N5 |
| D9 | `httpx` and `websockets` are used by the live code but not declared in `requirements.txt`. They arrive only through the development and uvicorn extras | Medium | Backlog N6 |
| D10 | An untracked file `:memory:.ses` in the live folder holds a token-like string. Its writer is unknown | Medium (possible credential) | **The Human's action:** identify, delete, rotate if needed |

## 3. Strategic direction

**What OpsAtlas is now.**
- A single-operator, loopback-only product on one Mac Studio.
- A 19-source Product Guide with 27 curated records, a facts map per space, and local Ollama models.
- Tibi, the most developed part: engine 1.7.1, each version gated on a 100-turn latency replay.
- A complete first release of identity and access.
- Knowledge spaces, phases 1–2.

**Where the effort went.** Of the last 150 commits (20–30 September), 61% were on Tibi and voice, 15% on governance and
content, 9% on knowledge, OAG and spaces, 5% on IAM and 3% on benchmarks and documentation. The answer path itself
(retrieval, answer, sources, ingestion, guardrails) is 2,075 lines. The analytics, EAM, value and simulator block is
8,083. The core value of the product is a minority of its code.

**What the product guide claims against what runs.** The corpus (`services/opsatlas_sales/corpus/foundation.json`)
still describes the Classic proof of concept:

| The guide claims | The live Sales deployment |
|---|---|
| A compliance-reasoning service on two 8–14B models | Switched off |
| External GOV.UK and legislation.gov.uk review | Dropped |
| 94.44% holdout accuracy | That figure is from the Classic corpus with a 7B model. Sales answers with a 4B model and scored 87% on its own 36-question set, at 42 seconds an answer |
| No identity or role-based permissions | Now false: IAM E1 provides them |

**The bets.**

| Bet | Evidence | State |
|---|---|---|
| Facts map first (OAG) | Classic holdout 68/72 against 53/72 for documents only, at 1.3 s against 3.8 s. H1b removed the out-of-scope failure class | **Paying on Classic; neutral on the guide.** The guide's facts map produces no plans: 94/108 in both configurations, and 5 s slower |
| Tibi as the differentiator | Fastest-moving, best-instrumented part; latency gate at p50 1,950 ms and p95 3,100 ms | **Thin evidence of value.** One user's sessions and one real interview. The Higgs licence covers evaluation only (#1717 deferred) |
| Knowledge spaces | Partitions, family, transfer and organisations are built | **Never held two organisations with data.** Phase 3 (the leak suite) is design only |
| IAM | 167 permissions, 11 roles, audit chain, every route classified | **Complete first release, one user.** Family projection for guide readers is deferred item 4 |
| Benchmark first | Pre-registered marks; H1 rejected, H1b adopted | **The strongest asset.** Its cost is now the limit: a Sales run takes 2.5 hours on a quiet machine |
| Local-first, small models | Search at 6 ms for 5,000 sections (F7) | **Answers are too slow** (D2): a configuration fault, not a failure of the principle |

**Risks.**
- **Branch debt:** see section 7.
- **One author:** 150 of 150 recent commits come from one person, and the working rules live in memory notes and 118
  documents.
- **Real data:** phase 5 of knowledge spaces is unbuilt.
- **One machine:** the GPU is shared with another project's model server. It holds a 30 GB model resident (a separate
  Ollama on port 11435), which is why the latency gate needs a quiet machine.
- **Licensing:** the Higgs voice is on evaluation terms; eSpeak NG is GPL-3.0; Anam is paid.

## 4. What to remove or park (decisions for the Human)

**Usage evidence.** Non-poll requests per page, 26–30 September, from the live activity log:

| Pages | Requests |
|---|---|
| Talk with Tibi | 3,583 |
| Process review | 666 |
| Governance | 373 |
| Tibi knowledge | 244 |
| Dashboard | 168 |
| My account | 77 |
| Digital SME | 75 |
| Document | 44 |
| EAM | 26 |
| Conversation log, Citation Check, Knowledge Sources | 14, 14, 12 |
| **Analytics** | **7** |
| **External Sources, Stress Lab** | **3 each** |
| **System, Processes, Simulator, Written Query** | **2 each** |

The compliance API received **0** requests beyond the status poll. This covers one week and one user, but it describes
the Sales product.

| Candidate | Size | Evidence | Proposal | What is lost |
|---|---|---|---|---|
| Compliance-reasoning sidecar | 5,368 lines, plus 10 core routes, `assistant.eval.compliance_*` (1,238 lines), 98 tests, 5 scripts; `deepseek-r1:8b` (5.2 GB) is used only here | Switched off in Sales; superseded by statement governance (GOV E1, own benchmark); 0 requests | **Remove from Sales**; Classic keeps it | The 35-hour pair review, already retired |
| `deepseek-r1:32b` | 19.9 GB | Referenced only by `assistant/eval/compliance_model_comparison.py` | **Remove the model** | A past model comparison, which stays recorded |
| Simulator, Process Stress Lab | 776 + 459 lines and 213 + 248 lines | 2–3 requests in 5 days; Sales has no processes to stress | **Park in Classic** | The "600 synthetic interactions" figure, a Classic claim |
| External sources, regulatory review | 636 + 300 lines and 606 lines | The review was dropped (88be685); 3 requests | **Remove from Sales** and fix the guide's claim | A regulatory angle with no benchmark |
| Value analytics | 366 lines and a tab | Assumption-led; no observed value is claimed | **Park** | Nothing observed |
| Analytics and EAM block | About 7,000 lines, 16 test files | 7 and 26 requests; strong for DT603, holds no Sales data | **Keep, lazy-load and freeze**; revisit when an organisation space holds real process data | — |
| Alternate voice engines (Kokoro, Kokoro-MLX, Pocket, Qwen custom, Chatterbox) and their assets | About 4.4 GB (Qwen voice design 2.2 GB, experience-env 0.8, s3tokenizer 0.5, Chatterbox 0.4, Kokoro-MLX 0.3, Pocket 0.2) plus about 2,500 lines | The live voice is Higgs (`SME_VOICE_BACKEND=higgs`) | **Remove**, as an engine version with the replay gate (the voice modules are fingerprinted) | Audition options already decided |
| Classic-corpus rules | "Learning Pack" parsing, VAT and packaging rules | Tuned to the DT603 corpus | **Keep Classic behaviour** behind configuration (H2 made this possible); no new Sales code on them | — |
| Frontend code for removed features | About 2,100 lines: 28 dead `api.ts` functions and 36 types, a 448-line unimported component, about 300 lines of dead CSS | Checked by the type checker, calls and grep | **Delete** | Nothing: it is already tree-shaken |
| Two `assert True` test files | 2 files | — | **Delete** | Nothing |

**Keep.** The rest of the Tibi evaluation tooling (about 25 `evaluate_`, `replay_` and benchmark modules) sits outside
the engine fingerprint and is how the gate is measured. Move it into `services/sme_interviewer/tools/`; do not delete
it.

## 5. Speed

### 5.1 Answer latency on the Product Guide

**Measured:** 41.8 s mean, 33.3 s median, 95 s p95, 139 s maximum (baseline); 57 s mean and 164 s maximum on a busier
machine. The prompts were byte-identical, so the difference between the two runs is the machine and the model's variable
output, not the code.

**Causes, in likely order of effect:**
1. **Hidden reasoning is on.** `OllamaGenerator` sends `{"num_ctx", "temperature"}` only. Tibi calls the same
   `qwen3.5:4b` with `"think": false` (`companion.py:62`, `answer_check.py:45`). A reasoning model left free to think
   explains both the long times and their spread, and the 120 s timeout that killed one benchmark run.
2. **The whole guide goes into every prompt.** The guide (10,561 characters) is below the 24,000-character full-context
   limit, so every question sends all 19 sections.
3. **Output length is unbounded:** no `num_predict` is set.
4. **A second model call per answer:** the grounding check (`KP_VALIDATE_GROUNDING` defaults to on).

**Proposal (H3a):** `think: false` and a `num_predict` bound for the core generator. See section 8 for the marks.
Retrieval mode for the guide (H3b) and dropping or deferring the grounding call (H3c) follow only if needed.

### 5.2 The control panel

- **One 985 kB JavaScript chunk.** About 400 kB of it is the charting library, used only by Analytics. Lazy-loading
  Analytics alone halves the initial load; lazy-loading the other pages brings it to about 270 kB.
- **An 811 kB logo** loads on every screen. A resized image is about 270 kB; WebP or SVG is far smaller.
- **The status poll** sends five sequential requests every 30 seconds, including while the tab is hidden, and one of them
  is the dead compliance status. Use `Promise.all`, pause when hidden, and drop the compliance row.

### 5.3 Start-up

The module-level app (D5) costs 0.56 s and a second copy of the guide's stores at every start. The in-memory search
index (F7) already removed the per-question corpus rebuild.

## 6. Code quality

### 6.1 Backend (`src/assistant`, 30,829 lines)

- **Largest packages:** analytics 4,155 lines, api 3,749, iam 3,133, ontology 2,850, eam 2,786, eval 2,607. Largest file:
  `iam/service.py`, 1,804 lines.
- **Dead code is negligible.** 9 top-level definitions (46 lines) are referenced by nothing, for example
  `ontology/router.py:matching_process_evidence`, two unused protocols, `api/auth.py:bearer_token`, and
  `iam/catalogue.py:platform_keys`/`space_keys`. Three more are used only by tests.
- **Routes without a live caller: about 40 of 224 API paths.** 12 are reached only by tests (the ontology explorer ×6,
  analytics history and timeseries ×3, password forgot, Tibi's service contract). About 28 more are reachable only
  through panel functions nobody calls (compliance ×9, regulatory ×3, governance ×11, and a few in process, EAM and
  avatar). Most go with section 4's removals.
- **One real god-function:** `create_sales_app` (mccabe complexity 92, about 430 lines) defines every workspace route
  inline. Split it into routers (spaces, conversations, services, the sales contract, the frontend), as the core does.
  The `build_*_router` scores are inflated by nested handlers, which is the usual FastAPI pattern.
- **Error handling is healthy:** 23 broad `except Exception` clauses, none of them silent.
- **Hard-coded values:**
  - Ollama's address appears in 32 lines across 27 files; only 8 read `KP_OLLAMA_URL`.
  - Model names are hard-coded in more than 30 places.
  - 80 environment variables are read; 38 are documented nowhere, and there is no `.env.example`.
  - The Sales app overrides README-documented settings outright: model, rewrite, rerank and the compliance URL.

### 6.2 Services

- **Tibi (`services/sme_interviewer`, 15,355 lines).** 36 modules (10,014 lines) are reached from the live entry point,
  plus the worker's dynamically loaded Higgs voice. 38 modules (4,154 lines) are tooling, alternates or leftovers:
  `evaluate_*` ×15, `replay_*`, the benchmarks, the `provision*` scripts, `pocket_voice`, `mlx_voice`, and two
  superseded previews.
- **Worktrees reach into live state.** Each worktree's `.runtime` and `.venv` are symlinks into the live Tibi runtime
  and environments, so replays in a worktree write to live databases and a `pip install` changes live packages. Give
  each worktree its own writable runtime.
- **Logs** are about 1 MB a day of daily activity files, with no retention rule.

### 6.3 Frontend (28,225 lines)

- **Healthy overall:** strict TypeScript, no `any` sprawl, and heavy libraries already lazy (the editor, three.js,
  Anam).
- **Accretion:**
  - `api.ts` is 3,229 lines, a quarter of it dead, with six request styles.
  - `App.css` is 5,521 lines ordered by sprint, with 62 selectors defined more than once and 47 `!important`.
  - Pages hand-roll data loading; the IAM `useLoad` hook and primitives are the pattern to share.
- **Navigation:** hash routing mixes `replaceState` and `hash=`, so the browser Back button leaves the app and sidebar
  navigation is missing from the activity log.
- **Accessibility:** 11 inputs have only a placeholder; hidden sub-menus stay tabbable.
- **Defence in depth:** process-diagram SVG, whose labels come from documents, is injected as raw HTML. Sanitise it or
  render it as an image.

### 6.4 Tests

- **Python:** 145 test files and 1,071 test functions; **JavaScript:** 64 tests in 8 files. Tibi has 407 tests and
  compliance 98, the latter guarding a switched-off service.
- **Frontend:** no unit tests, no linter beyond the type checker, and no bundle budget.
- **pytest:** no markers, no warnings policy, no timeout.

## 7. Process and repository

- **`main` lags badly.** It is 139 commits, 531 files and +158,990 lines behind what runs, and 63% of those lines are
  JSON evidence. PR #2 is stale: it is not on the live commit and still describes "866 tests". The live folder runs from
  the working tree of a branch named `tiberius-speed-safety`. `ARCHITECTURE_STATUS.md` records the branch order
  backwards.
- **CI** starts automatically only on `main`. Every branch build today was queued by hand, so a push that nobody queues
  (another agent, a hand edit) goes unchecked. CI uses Python 3.11 while live runs 3.12, and 24 of the 42 lock pins
  differ from the live environment, so "the exact, tested versions" is not true of what runs.
- **Branches and worktrees:** 30 local and 18 remote branches, of which 25 local and 12 remote are contained elsewhere.
  Keep `main`, `opsatlas-classic`, `arch-h2` until adopted, and `process-interview-5` until the 1.8.0 gate. Three
  worktrees are stale, two of them Codex checkouts.
- **Untracked clutter in the live folder:**
  - `:memory:.ses` (D10);
  - two benchmark files byte-identical to a tracked one;
  - the IAM specification, reviewed but kept out of the repository;
  - `UI/` design references;
  - two Classic documents;
  - ignored leftovers: `poc/` (44 MB, including a `.env` to check), `backups/` (39 MB), and root JSON dumps and zips.
- **`.gitignore` gaps:** symlinked `.venv` and `.runtime` are ignored only by a local exclude file; there are no rules
  for `*.ses`, `*.db`, `*.sqlite` or `.env.*`.
- **Documentation:**
  - The README is wrong for Sales. Its quick start (`./scripts/dev.sh`) exits with an error. It says the voice
    interviewer is not part of the runtime and that access control is not implemented, and it documents settings that
    Sales overrides.
  - Current-state pages contradict each other: sign-in with the workspace key against IAM; the ports; test counts of
    866, 1,015, 1,189 and "about 1,250", against 1,071 plus 64 actual.
  - `docs/` has 310 files and 6.7 MB, 176 of them JSON (5.4 MB). Code reads 26 `docs/` paths, including the engine
    registry and the latency budget, so a documentation clean-up could break the engine gate.
  - There is no index for a newcomer.
- **Naming rule:** two files from before the rule (June and August), a DT603 industry-context document and a test that
  asserts its wording, name a vendor the project rule says must not be named in the repository. The Sales Playbook
  corpus quotes the same passage. **The Human's decision** on rewording them.

## 8. Proposed hypotheses (register before building)

| # | Hypothesis | Marks |
|---|---|---|
| H3a | `think: false` and a `num_predict` bound in the core generator make guide answers fast without costing accuracy | Sales set, 36 questions × 3 runs, same-session baseline, quiet machine: mean ≤ 10 s and p95 ≤ 20 s; accuracy within ±2 per split; no new wrong refusals; redirect ≥ 90%. Classic holdout within ±2 |
| H3b | If H3a does not reach 10 s: retrieval mode for small corpora (top-k instead of the whole guide) | Same marks; route 100% |
| P1 | Lazy-loading pages cuts the panel's initial JavaScript without regressions | Main chunk ≤ 350 kB; a smoke test visits every page with no console error |
| P2 | Removing the compliance sidecar and the parked features changes no Sales behaviour | Full suite green minus the removed tests; route manifest shows only the removed paths gone; the Sales benchmark is unchanged (prompt identity, as in H2) |
| P3 | Removing the alternate voice engines is a pure engine clean-up | Engine version bumped; 100-turn replay within budget on a quiet machine; voice unchanged in a listening check |

## 9. Corrections to the review agents' findings

| # | The agent said | What is true |
|---|---|---|
| 1 | CI never runs on the working branches | It runs when queued, and every push today was queued by hand, green from 20260930.12 to .21. The gap is the *automatic* trigger |
| 2 | OpsAtlas relies on the trading assistant's Ollama | OpsAtlas uses the Ollama desktop app's server on 11434. The trading assistant runs its own on 11435. The coupling is shared GPU and memory, not a shared server |
| 3 | Archive the 9.8 GB voice "experience lab" | 8.7 GB of it (`experience/audition2-higgs`, misleadingly named) **is the live Higgs voice**. Only about 1.1 GB of `experience/` is lab material |

## 10. Backlog, in order

**Now (small, mostly defects):**

| # | Item | Effort | Risk |
|---|---|---|---|
| N1 | H3a: `think: false` and `num_predict`, with its benchmark | S (plus 2 runs) | Low |
| N2 | Analytics tab links (`#analytics:<tab>`); an error boundary around pages; `PlaceholderView` redirects instead of crashing | S | Low |
| N3 | Replace the module-level app with a factory; remove the stray `core/iam.db` | S | Low |
| N4 | The Human deals with `:memory:.ses`; add `.gitignore` rules | S | Low |
| N5 | `ids=` on the WAV test; CI runs all `tests/*.mjs`; delete the two `assert True` tests | S | None |
| N6 | Declare `httpx` and `websockets`; add `requirements-automation.txt` for `requests` | S | Low |
| N7 | README and current-state truth pass; a `docs/README.md` index; mark stale pages | S–M | None |

**Consolidation fortnight:**

| # | Item | Effort | Risk |
|---|---|---|---|
| C1 | Bring `main` level: a new or rewritten PR of the live line, no squash (the engine registry needs the commits); tag `live-2026-09-30` and the engine versions; deploy from `main`; CI on every branch; Python 3.12 in CI; prune branches and worktrees | M | Low |
| C2 | Panel: lazy pages, a smaller logo, delete dead TS and CSS, a better status poll, move old request functions onto `apiRequest` so permission errors read correctly | S–M | Low |
| C3 | Section 4 removals, after the Human's decisions: the compliance sidecar and its tests and models; external and regulatory; park the simulator, stress lab and value analytics in Classic; correct the guide's records | M | Medium (P2) |
| C4 | Remove `deepseek-r1:32b` (19.9 GB) and, after C3, `deepseek-r1:8b` (5.2 GB) | S | Low |

**Structural (gated):**

| # | Item | Effort | Risk |
|---|---|---|---|
| S1 | Remove the alternate voice engines: an engine version, P3 | M | Medium |
| S2 | One settings module per process; a Sales profile file; port and model constants; a generated `.env.example` | M | Low–Medium |
| S3 | Split `create_sales_app` into routers; split `api.ts` by domain; shared UI primitives | M | Low |
| S4 | Move the registries that code reads out of `docs/` into `config/`; archive raw evidence; one evaluation folder | M | Low–Medium |
| S5 | Worktrees get their own writable Tibi runtime | M | Low |
| S6 | Knowledge spaces phase 3 with a leak suite (two organisations, planted phrases, zero leaks over 200 or more requests) before any second person or real data; the Higgs licence decision before any external Tibi demo | L | — |

## Evidence

- The review agents' full reports are kept with this session's working files.
- The strategy review's figures come from the files it names.
- Usage counts come from the live activity log, read by page only.
- The scripts used for the route, definition and module-reachability checks are in the session scratchpad.
