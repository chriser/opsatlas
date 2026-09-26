# OpsAtlas Classic and OpsAtlas Sales

**26 September 2026.** On this date OpsAtlas was split into two independent versions:
- **OpsAtlas Classic** is the OpsAtlas submitted for DT603. It is preserved exactly and never developed further, so it can always be shown to someone working as it did.
- **OpsAtlas Sales** is the new version. It is built only on the data set derived from the DT603 document, and it is where all redesign and cleanup now happens.

## At a glance

| | OpsAtlas Classic | OpsAtlas Sales |
|---|---|---|
| **What it is** | The DT603 proof of concept as finalised on 9 August 2026 | Sales-focused OpsAtlas with Tibi, the voice companion |
| **Folder** | `~/Dev/opsatlas-classic` | `~/Dev/ai-knowledge-analytics-assistant` (this folder) |
| **Code** | Branch `opsatlas-classic`, at tag `opsatlas-v1-dt603-final` (`c7e6ff7`). It is never changed | Branch `claude/tiberius-speed-safety` |
| **Data** | `data/` in its folder: the 21 anonymised learning packs, their ontology, process registry and analytics | `.runtime/opsatlas-sales`: the 27 records derived from DT603 and the DT603 sections they cite. No `data/` folder exists here |
| **Start** | `./scripts/dev.sh` in its folder | `scripts/start-tiberius-sales.sh` (`stop` / `status` / `restart`); **Restart services** under the control panel's Status |
| **Open** | http://localhost:5200 | http://127.0.0.1:8780 |
| **Ports** | 5200 control panel, 8010 core API, 5310 compliance reasoning, 5300 process diagrams (started from System Overview) | 8780 workspace and control panel, 8773 Tibi voice; frontend development server on 5280 |
| **Sign in** | Operator password from `KP_OPERATOR_PASSWORD`, or the documented default in its README | The workspace key, `.runtime/opsatlas-sales/local-access.key` |
| **Environments** | Its own `.venv`, built from the packages pinned on 26 September, and its own `frontend/node_modules` | This folder's `.venv`, `services/sme_interviewer/.venv` and `frontend/node_modules` |
| **Settings** | Its own `.env`, holding only the Anam settings for the Digital SME | This folder's `.env` |

The two use different ports, so both can run at the same time; for example, Classic for a demo while Sales is being worked on.

## How the separation is kept

- **Code.** Classic runs from its own checkout of a fixed tag. Nothing developed here can change it, so pages and features can be removed from Sales freely.
- **Data.**
  - The old knowledge base moved into Classic's folder, and this folder has no `data/`.
  - The sales workspace refuses to open the old knowledge base (`services/opsatlas_sales/workspace.py`).
  - The test suite points `KP_DATA_DIR` at a throwaway folder (`tests/conftest.py`), so running the tests never creates `data/` here.
- **Ports.** The frontend development server here uses 5280 and forwards only to this version's backend (8780). Before the split it used 5200 and forwarded to 8010, which are now Classic's. `scripts/dev.sh` here no longer starts the old stack; it points to Classic instead.
- **Environments.** Classic has its own Python and Node packages. A dependency change here cannot break it.

## Starting from scratch (Sales)

The sales workspace was re-seeded on 26 September 2026. It holds:
- the 27 records from `services/opsatlas_sales/corpus/foundation.json`;
- the DT603 sections they cite, from `.runtime/opsatlas-sales-foundation`;
- no answers, usage history or interviews.

Every record starts **pending**. The Human enables each one in **Tibi Knowledge**, and nothing is approved automatically.

## If something needs recreating

- **Classic's folder:**
  ```bash
  git worktree add ~/Dev/opsatlas-classic opsatlas-classic
  ```
  Then restore its data from `~/OpsAtlas-archive/2026-09-26-pre-redesign/data.tar.gz` and follow the `RESTORE.md` there.
- **Earlier versions:** tags `opsatlas-v1-dt603-final`, `opsatlas-v2-sme-interviewer` and `opsatlas-v3-pre-redesign`, with `~/OpsAtlas-archive/2026-09-26-pre-redesign/RESTORE.md`.
- **The sales workspace as it was before the fresh start** (with the review of 26 September, your answers and the approval history): `~/OpsAtlas-archive/2026-09-26-sales-before-fresh-start/`.

## Checked on 26 September 2026

- **Classic**, from its own folder, environment and data:
  - its test suite passes (450 tests) and the control panel builds;
  - `./scripts/dev.sh` starts it, with its history intact (810 questions, 71% grounded);
  - a question about supplier onboarding was answered from the ontology, grounded (OAG).
- **Sales:**
  - the fresh workspace opens with 27 records, 42 sources, no answers and no usage history;
  - the full test suite passes (1,015 tests) without creating `data/`;
  - the frontend development server on 5280 signs in and reaches Tibi's WebSocket through its own backend.
