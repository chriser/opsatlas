# The Documents component (REF S60, design of 4 October 2026)

S60 is step 1 of the retrospective's migration path (REF F11 #2170). It follows S59's guard rails.

One component owns a space's documents:

- the register;
- the text;
- the passages;
- the content history;
- approval.

Everything else reads and commands through it.

Behaviour does not change. What changes is that the rules S57 put in place have one owner: the door, the register's
decide and the staged publish. An agent changing how documents behave then needs only this component and its contract
in view, not 41 importers.

Status: **design, before its design red team.** Nothing is built.

## What clients use today (measured at `3e51749`)

- **Reads:**
  - `get` (41 call sites), `list` (40), `read_content` (17), `read_record_text` (3);
  - the passages' `list_for_source` (11).
- **Writes:**
  - `update` (7), `decide` (4), `add` (2), `remove` (2);
  - staging and moves inside the content workflow, and the space moves.
- **The register as a folder locator.**
  - `register.base_dir` (with `registry.base_dir` and `core.state.register.base_dir`) is used 51 times in 14 modules:
    19 of them in `api/app.py` and 9 in the Sales knowledge module.
  - These uses place other stores beside the documents: analytics, governance, the Sales records, receipts.
- **Importers of the store modules:** 41 (S59's allow-list). There are three store modules:
  - `sources.register`;
  - `ingestion.store` (the passages);
  - `content.store`.
- **The raw stores in the app's state:** `state.register`, `state.content` and `state.section_store`.
  - Production code reads them 17 times, in 6 modules: the core app, and the Sales app and four of its route modules.
  - Tests read them 184 times, in 30 files.
  - Tibi's engine never does.
- **S59's other lists that S60 shrinks:**
  - `content.db`'s exception for the space moves (`STORE_ALSO`);
  - the two marked private calls into the content workflow: `_approve` and `_reject`, in the Sales content step.

## Promises

- **D1, behaviour unchanged.**
  - Every existing test passes unchanged, except a test whose set-up moves onto the public interface; each such test
    says so.
  - S57's S1–S8 hold.
- **D2, one owner.**
  - Only `assistant.documents` imports the three store modules.
  - S59's rule for them becomes "imported only by the Documents component". Its allow-list shrinks to the benchmark
    fixture of Tibi's engine, which is untouched because it is under the engine's fingerprint.
- **D3, the contract.**
  - S1–S8 are stated as properties of the component's interface.
  - They run as a contract suite in process, without FastAPI, so a future change to the component is checked against
    them directly.
- **D4, no new path.** The component adds no way to change a document that goes around the door, the register's decide
  or the staged publish. The proof has three parts:
  - **S59's import and store rules** prove the forms they see.
  - **A new AST check** covers the forms they do not see (S59's stated limits: a store reached through an object's
    attribute, or through an imported constant). It fails when production code outside the component reads a raw store
    from an app's state (`state.register`, `state.content`, `state.section_store`) or a store's path through an
    attribute. Today's 17 uses move onto the component.
  - **Tests keep their access.** They may look inside what they test.
- **D5, the folder.**
  - A space's folder comes from the workspace, not from the register.
  - No client derives a path from `register.base_dir`.

## Design

`assistant/documents/` holds one class per space, `Documents`. The core app builds it (`app.state.documents`), and the
workspace's lock governs it, like the stores inside it.

- **Reading:** `get(id)`, `list()`, `text(id, sha=None)`, `record_text(id)`, `passages(id, sha=None)`.
  - Each is today's method, unchanged and delegated.
  - Readers still never wait.
- **Commands:** each is a governed write, under the door.
  - The commands: `upload`, `ingest`, `decide(id, status, sha)`, `update_details`, `rename`, `save_draft`, `submit`,
    `return_to_draft(draft_sha)`, `publish(draft_sha)`, `restore(n)`, `delete(id)`, and
    `move(id, to=<other Documents>, keep_approval, folder)`.
  - Each delegates to today's code first. The code moves inside the component as its clients move.
- **Family view:** `FamilyDocuments` replaces `FamilyRegister`/`FamilySections`.
  - It is a view over the Sales layer's three spaces' `Documents`, routing by document.
- **The folder:** the workspace gives each core a `SpaceFolder`, which replaces `register.base_dir`.
  - Clients take it from the app's state, not from the register.

Not in S60:

- the commit number and the event per commit (phase 3, with the derived views);
- the hooks dictionary as a typed policy (S58);
- one transactional store (optional, later).

## Stories

| Story | What | Size |
|---|---|---|
| S60a | `assistant/documents/`: the `Documents` interface delegating to today's code; wiring; the contract suite (S1–S8 through the interface); the space folder | L |
| S60b | The core's clients onto it: the routes (sources, ingestion, content, governance), retrieval, answering, governance, regulatory, analytics, process; the approve and reject handlers move inside | L |
| S60c | The Sales layer onto it: the knowledge store, the governance desk, Tibi's routes, the Sales API; `FamilyDocuments`; the space moves and the library inside, without raw access to the content database | L |
| S60d | The folder: `register.base_dir` replaced by the space folder in the 14 modules; S59's document-store rule narrowed to the component; D4's check on the app's state | M |

Each story carries its promises and its impact map on its ADO item, then goes through these steps:

1. The gate.
2. A red team on the code. For a refactor, its target is D1 and D4: anything that behaves differently, or a path that
   goes around the component.
3. The independent review.
4. A merge into `main`.

One design red team, on this page, comes before S60a starts.

## Impact map (all stories)

- **New:**
  - `src/assistant/documents/`: the interface, the family view, the folder;
  - `tests/documents/`: the contract suite.
- **Changed:**
  - `src/assistant/api/app.py` (the wiring);
  - the routes and services that import the store modules (41 importers);
  - `services/opsatlas_sales/{app,spaces,knowledge,governance,content,tibi_api,routes_sales_api,routes_spaces,routes_conversations}.py`;
  - the 14 modules using `base_dir`;
  - `tests/boundary_rules.py`: the document-store rule and its allow-list, `STORE_ALSO`'s `content.db`, and D4's check;
  - the two `# noqa: SLF001` marks in `services/opsatlas_sales/content.py`;
  - tests whose set-up writes stores, moved onto `tests/builders.py` as they break.
- **Unchanged:**
  - Tibi's engine (`services/sme_interviewer/`, under its fingerprint);
  - the stores' file formats: no migration, so no new way-back step.
