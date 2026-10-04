# The Documents component (REF S60, design v2 of 4 October 2026)

Step 1 of the retrospective's migration path (REF F11 #2170), after S59's guard rails.

**One component owns a space's documents.** It holds the register, the text, the passages, the content history and
approval, and everything else reads and commands through it. Behaviour does not change. What changes is that the rules
S57 put in place gain one owner: the door, decide in the store, drafts naming the draft, and the staged publish. An
agent changing how documents behave then needs only this component and its contract in view.

**Status: the stop rule applies.** Nothing is built. The decision is with the Human; see the next section. v2 below is
kept as the record.

## The stop rule (4 October 2026, after design round 2)

Round 2 on v2 found 2 Highs, 8 Mediums and 1 Low, every one in an area where round 1 also found a fault. Its report is
`research_notes/design-red-team-2026-10-04-S60-round2.md` (local), with probes in
`research_notes/design-red-team-S60-probes/`. Under rule 7, patching stops here.

**The design flaw.** v2 asked a refactor that changes no behaviour to carry three new mechanisms. Each collides with an
exception S57 made on purpose:

1. **A runtime "one way in"** over stores whose readers write by design:
   - readers settle a committed version;
   - views record under `if_free`;
   - background reviews read, and so settle.

   Set around commands only, the context refuses all of these. After a crash, every reader fails.
2. **A transfer that heals itself,** working over the two live copies a failed write leaves behind and keyed on the
   text alone:
   - the copies' approvals can differ;
   - the callers take the first space holding the document as the origin, so a retry can miss the half-done case.
3. **Moving the decision code ahead of the staged publish it is bound to:**
   - the publish handler belongs with the content workflow's staged-publish code;
   - the document rules are shared with `accept_issue` and `save_document`.

**The simpler design, for the Human's decision.**

- **Keep.** Round 2 found these sound, or sound with small corrections:
  - **One owner by construction.** Only the component imports the stores, proven by S59's import rule. A leaf takes the
    register's errors and the content workflow's two second-cycle helpers (the date reader and the phase names).
  - **The reads:** the permissive and strict reads named apart, with `names_text`.
  - **The decisions:** `review` and `decide` as two commands, `decide` taking the actor as today's callers pass it.
  - **The rest:** a corrected error table, the folder rule, one builder for the app and the suite, and
    `documents.govern`.
- **Drop from S60:**
  - **The runtime command context (D4).** The import rule and an AST check over production code are the check. Runtime
    enforcement would be designed on its own later, if wanted, with the readers' settles in scope.
  - **The self-healing transfer.** Bug #2186 is fixed narrowly, and first. A document that two spaces hold is never
    moved automatically and never blocks start-up. It is reported in its activity and in the start-up log, and a
    transfer of it is refused with a clear message until a person resolves it.
  - **Moving the publish handler.** Only the approve and reject handlers move, with their own rules. Shared rules stay
    where they are registered.

- **v1 (`d6e2034`)** went to the design red team: 4 Highs, 11 Mediums, 3 Lows. Its report is
  `research_notes/design-red-team-2026-10-04-S60.md`, with probes in `research_notes/design-red-team-S60-probes/`,
  both local.
- **v2** takes every finding. Each change below names its finding (DR1–DR18).
- **The exit rule:** a round with nothing above Low.
- **The stop rule:** faults in the same area in the second round mean stopping here and bringing the Human a simpler
  design.

## What clients use today

Measured at `3e51749` and re-counted by the red team (DR16, DR6, DR7).

### Reads and writes

- **Reads:**
  - `get` 41, `list` 40, `read_content` 17.
  - `read_record_text` 5, two of them through the family register.
  - The passages' `list_for_source` 12, one through retrieval.
- **Writes:**
  - `update` 7, `decide` 4, `remove` 2.
  - `add` 2, or 3 counting Tibi's engine's benchmark fixture.
  - Plus staging and moves inside the content workflow, and the space moves.

### The content workflow

- **The content routes call 33 of its methods:**
  - views, comments and the library;
  - suggestions, images and drafts.
- **Elsewhere, clients call:**
  - `names_text`, `current_version` (the receipts), `first_version` (on add), `ensure_all_versions` (at start);
  - `forget` (on delete), `retry_records` (the Sales layer), `folders_of` and `comment` (the access layer);
  - `hooks`, `self_approval`, `rebuild_facts` and `refresh_processes`.

### Who uses the stores

- **Importers:** 41 import edges from 26 modules (S59's allow-list).
- **Users that do not import them:** 11 production modules more:
  - the access layer and the answer service;
  - the governance statement review and statements;
  - the staged publish's settle step;
  - the Sales statement governance;
  - and the Sales modules.
- **Raw stores read from an app's state, in production:**
  - 18 literal reads in 6 files;
  - 5 through a name bound to a state, 4 through `getattr`, 5 through `app.state.family_register`.
- **Raw stores read from an app's state, in tests:** 184 reads in 30 files.
- **Tibi's engine** reads none. Its fixture builds its own stores.

### The folder and the lock

- **The register as a folder locator:** 54 reads of `.base_dir` on register-like receivers in 14 modules (55 in 15
  with the engine's fixture), plus 3 through `registers[...]`.
- **The derived stores belong to:** analytics, governance, ontology, external, regulatory, evidence, space config and
  statements, and the Sales layer.
- **A lone core's lock** is the register's index file.

## Promises (v2)

- **D1, behaviour unchanged.**
  - Every existing test passes. A test changes for one of two reasons only, and each change is listed in its story's
    record:
    - its set-up moves onto the interface;
    - a patch target moved with its code, and the test is restated to the same check (DR11).
  - S57's S1–S8 hold (quoted below).
  - **Duck-typed consumers keep working.** The read interface keeps the stores' method names.
    `create_app(register, auth, retrieval, answer, …)` and `RetrievalService(register, section_store)` keep their
    signatures; Tibi's frozen fixture calls them positionally. A hermetic test builds the fixture's core with a fake
    generator. That test sits outside the engine's files (DR8).
  - **An identity test:** `app.state.register`, `app.state.section_store` and `app.state.content.store` are the
    instances the component uses. The scenario suite's fault injection stays valid (DR11).
  - **Errors** are today's types, or subclasses with the same bases, and never `HTTPException`. There is a table of
    what each command raises. Every route keeps its mapping, with a status test per route (DR14).
- **D2, one owner, in production.**
  - Only `assistant.documents` imports the three store modules (`sources.register`, `ingestion.store`,
    `content.store`). The one exception is Tibi's frozen benchmark fixture, under the engine's fingerprint.
  - S59's rule becomes "imported only by the Documents component" in S60a, with the reason recorded in Boundaries.md.
    Its allow-list shrinks story by story to the fixture.
  - **The import rules (DR1):**
    - the component never imports `assistant.answer` or `assistant.governance`;
    - no module in the first package cycle (`ingestion`, `sources`, `process`, `ontology`, `eam`) imports the
      component; those modules take it by injection, untyped;
    - the register's errors (`ContentReplaced`, `TextNotNamed`, `ApprovalOutsideDecide`) move to a leaf,
      `assistant/sources/errors.py`, which the first cycle may import; the register keeps their names;
    - the component re-exports no store class.
  - S59's cycle rule stays green on its 18 entries, with no allowance added. The red team's scenario E becomes a test.
  - The tooling (`scripts/`, `automation/`) is outside, a stated limit with REF S65 (DR17).
- **D3, the contract (restated, DR4).**
  - S1–S5 and S8 run in process, through **one builder function** that `create_app` also uses. The suite therefore
    runs production's wiring: the actions engine, the approve, reject and publish handlers, and their validation
    rules. It is always governed, never `governed_by=None`.
  - **S7 splits in two:**
    - **S7a**, in process: the component and its stores refuse a write without the lock, and reads never wait.
    - **S7b**, the door at the app's edge: the HTTP tests in `tests/test_workspace_door.py` stay.
  - **S6** stays with the answer pipeline's tests.
  - The suite quotes S1–S8 (DR18).
- **D4, one way in (DR5).** A store write happens only inside a component command.
  - **Enforcement, switched on in S60e once every writer has moved:** the three stores' write methods refuse unless
    the component's command context is active. That context is a context variable the component sets around each
    command. An inventory test over every write method proves it, as `test_workspace_door.py` does for the lock, and a
    guard proves the inventory test.
  - **Until then, an early warning with a shrinking allow-list.** It is an AST check for loads of `register`,
    `content`, `section_store` and `family_register` on an app's state or on a name bound from one, and for
    `getattr(<…>.state, "<store>")`, outside the builder.
  - Tests keep their access.
- **D5, the folder (DR13).**
  - A space's folder is the workspace's; else the injected register's; else `KP_DATA_DIR`.
  - The component builds its passages and content stores from its register's folder.
  - The lock's path comes from one place and is never recomputed from a folder.
  - The Sales layer's own stores stay in the guide's folder: no migration.
  - A test proves each space's derived stores land in its own partition.
  - No client derives a path from `register.base_dir`.

### S57's promises, quoted (ADO #2140)

- **S1:** until a new version is committed (its record written), every reader sees only the live approved version. A
  file replaced on disk outside content management is shown by the content views as it is.
- **S2:** a reader holding a record gets that record's text and passages or none, never another version's. Views and
  readers that pair a record with its text read them together.
- **S3:** a publish that fails at any step, or a crash, leaves the live version whole. Staged material is discarded,
  or, once committed, settled by the next writer or reader.
- **S4:** a version number names one text and is never reused.
- **S5:** a publish whose record names its version entry is published, whatever fails after it (audit, events,
  rebuilds, the workspace's own records). One whose record does not is not published, and says so. Rebuilds are tried
  again. The approval event is written once. A lost event or step is recorded in the document's activity.
- **S6:** a version entry is created uncommitted and becomes visible only when its record names it. An uncommitted
  entry names nothing, and its number is never reused. A citation names the version written on the record its passage
  came from, and none when that record named none.
- **S7:** one writer per workspace, at the door.
  - Every request that may change something takes the workspace's one lock once, at the app's edge, before any handler
    runs. Every job that writes (start-up, a new space) holds it from its start.
  - The governed stores refuse a write from anything that does not hold it. They are each space's register, passages
    and content store, the Sales knowledge store and the governance desk.
  - Requests that only read never take the lock and never wait. A reader that would also record something only tries
    it.
- **S8:** every approval or rejection names the text it decides on (its SHA-256), and so does every decision on a draft
  (publishing it, returning it to its author). A decision on any other text is refused, and nothing changes.
  - A file replaced on disk outside content management cannot be decided on until it is published as a new version.
  - A document's approval changes only through the register's decide or a commit naming a new text, with no exception.

## Design (v2)

### The builder and the lock

`assistant/documents/` holds one `Documents` per space. One builder function, `build_documents(...)`, makes it; both
`create_app` and the contract suite call it (DR4).

- **Commands check the lock (`require`) and never take it** (DR9).
- **The component adds no lock and no governor of its own.** It reads its stores' governor.
  `documents.govern(lock)` is the one call that sets it. The Sales layer's `govern()` uses it from S60a, and the door
  reads the same value.
- **Readers that also record something keep `if_free`.**

### Reading (DR3, DR8)

- **The stores' read methods, by their names:** `get`, `list`, `read_content`, `space_of` and the passages'
  `list_for_source`.
  - `space_of` must keep its name: the Sales catalogue reads it through `getattr`.
- **The permissive read the source routes use:** `read_record_text`. A file replaced on disk is returned as it is.
- **The strict reads decisions use:**
  - `record_text(id)`: the record's own text. It refuses a replaced file.
  - `names_text(id, sha)`.
- **Also:** `current_version` and `first_version`.
- The contract suite has a replaced-file case for each read.

### Decisions: two commands (DR2)

**`review(id, expected_sha, approve)`** is today's content-workflow review. The content routes use it. It:

- checks the strict text;
- retries the records step;
- refuses "already approved";
- calls the workspace's decide hook;
- writes the log.

**`decide(id, status, sha)`** is the audited action: `approve_source` or `reject_source`. Its four validation rules
and its side effects come with it: the audit record, the process-registry and facts-map rebuilds, and the analytics
event.

- **Its users:** the governance routes, the actions, the Sales hook for a document with no record, and Knowledge.
- **The family view** routes it as `FamilyActions` does today.

**The register's own decide** stays private to the component and in the store, the one point of enforcement.

A contract test proves a decide hook that calls `decide` never re-enters `review`.

### The actions (DR4)

- **The approve, reject and publish handlers move into the component in S60a, FastAPI-free.** Their validation rules
  move with them: `source_exists`, `names_current_text`, `not_already_approved` and `not_already_rejected`.
- **They raise the component's errors.** `routes_governance` no longer registers them, and maps the errors to today's
  statuses and messages.
- **`_set_status`'s `HTTPException` becomes an error the route maps the same way.**
- **`accept_issue` stays with governance,** with its rules `issue_fields_present` and `non_empty_text`.
- **The side effects stay registered by name by the app** (`create_app`, four registrations today). These are the
  audit, the process-registry and facts-map rebuilds, and the analytics event. The actions engine calls them by name,
  so the component imports none of their code. It reaches neither `process` and `ontology` nor `analytics` (DR1).

### Commands under the contract (DR7)

Only what changes approval, the text or what is published is a contract command:

- `upload`, `ingest`;
- `review`, `decide`;
- `save_draft`, `accept_suggestion` (a draft edit), `submit`;
- `return_to_draft(draft_sha)`, `publish(draft_sha)`, `restore(n)`;
- `rename`, `update_details`, `delete`;
- `transfer`.

**The editorial features keep their methods and names.** These are comments, the library (groups, order and the
drag-and-drop `move`), suggestions until accepted, images and the views. They move inside with the content workflow,
as `documents.editorial`.

### The space move, `transfer` (DR7, DR12, Bug #2186)

It is called `transfer`, not `move`, which stays the library's.

- **One transaction per database,** through the stores' `export_document` / `import_document`.
- **Its crash behaviour is stated.**
  - The case: the target holds the document while the origin still does, with the same text.
  - Then the start-up layout and a retried transfer **complete** the half-done transfer. Today they raise "The target
    space already holds this document", and the workspace does not start.
- **`keep_approval` stays internal to the layout.** It is not a parameter of the public command, because S57's "no
  exception" tolerates it only for the layout.
- **Both spaces must share one lock,** asserted.
- **`prune_emptied`** writes under the lock check.
- **The DoD's crash and failed-write lines** become the transfer's scenario kinds.

### The family view

`FamilyDocuments` is a view over the three Sales spaces' `Documents`, routing by document. It replaces
`FamilyRegister`, `FamilySections` and `app.state.family_register`.

### Not in S60

- the commit number and the event per commit (phase 3, with the derived views);
- the hooks dictionary as a typed policy (S58);
- one transactional store (later).

### S57's three follow-ups for S60 (DR15)

- **`record_text` beside `names_text`:** done in S60a (Reading, above).
- **`governed_by` set by the Sales app:** replaced by `documents.govern(lock)` in S60a.
- **Hooks set from outside:** they stay set by the Sales app in S60, and become a typed policy in S58. This is recorded
  on #2172 and #2158.

## The error contract (DR14)

S60a completes this table and tests each line.

| Command | Raises (bases) | Content routes | Governance routes | Sales routes |
|---|---|---|---|---|
| reads | `NotFound` (`KeyError`), `ContentReplaced` (`LookupError`) | 404 / as today | as today | 409 (`KeyError`), as today |
| `review`, draft commands | `ContentError` (`ValueError`), `TextNotNamed` (`ValueError`) | 409 | — | 409 |
| `decide` | the action's refusal, as today's outcome; `TextNotNamed` | — | today's status and message | 409 |
| any write without the lock | `NotHolding` (`RuntimeError`) | 500, as today | 500, as today | 500, as today |

## Stories (v2, reordered, DR10)

| Story | What | Size |
|---|---|---|
| S60a | The foundation. `assistant/documents/` with the builder; the error leaf; the FastAPI-free actions and their rules moved in; `documents.govern`; the reads and decisions above, delegating. S59's rule admits the component, with the reason recorded. The contract suite on the production path (S1–S5, S7a, S8); the identity test; scenario E as a test; the early warning with today's allow-list; the fixture test | L |
| S60b | `transfer`: the space move as above, fixing Bug #2186; its own red team | M |
| S60c | The core's clients onto the component: the routes, retrieval, answering, governance, regulatory, analytics, process, the access layer, the settle step and statements. First-cycle clients by injection, untyped | L |
| S60d | The Sales layer onto it: `FamilyDocuments`, the knowledge store, the governance desk, Tibi's routes, the Sales API and the library. S60's mark in the Sales content step goes (`_approve` / `_reject`, line 257). The `_save` mark stays S68's | L |
| S60e | One way in, and the folder. The command context switched on in the stores, with its inventory test and guard. `.base_dir` replaced by the folder in the 14 modules. The allow-lists shrink to the engine's fixture, and the early warning's to nothing | M |

**Sequencing with S58 and S68 (DR15):**

- S60d comes before S58, because S58 builds on the family view's strict reads.
- S68's retrieval names come after S60c, because both touch `retrieval.service`.

**Each story goes through:**

- its promises and its impact map on its ADO item;
- the gate;
- a red team on the code: for a refactor, its target is D1 and D4, meaning anything that behaves differently, or a
  path around the component;
- the independent review;
- a merge into `main`;
- a go-live: S60b changes what the start-up does, and every story changes running code.

## Impact map (v2, from call sites and attribute reads, DR6)

### New

- `src/assistant/documents/`: the component, the builder, the actions and their rules, the family view, the folder and
  the editorial part.
- `src/assistant/sources/errors.py`: the leaf.
- `tests/documents/`:
  - the contract suite;
  - the inventory and identity tests;
  - the cycle scenario;
  - the fixture's core;
  - the transfer's scenario kinds.

### Changed

- **The core:**
  - `src/assistant/api/app.py`: the wiring, the receipts' `current_version`, and 20 `.base_dir` reads.
  - `routes_content`: 33 workflow methods. `routes_governance`: the handlers and rules move out.
  - `routes_sources`, `routes_ingestion`, `routes_feedback`, `routes_statements`, `routes_analytics`, `routes_process`
    and `routes_regulatory`.
  - `api/access.py`: `getattr` on the state; `folders_of`.
  - The rest: `answer/service.py`, `retrieval/{service,index}.py`, `governance/{intelligence,reanalysis,review_jobs,statement_review,statements}.py`,
    `regulatory/{discovery,impact}.py`, `analytics/export.py`, `process/registry.py`, `ontology/sync.py`,
    `sources/{service,bulk_import,settle}.py` and `ingestion/service.py`.
- **The Sales layer:**
  - `services/opsatlas_sales/{app,spaces,knowledge,governance,content,tibi_api,routes_sales_api,routes_spaces,routes_conversations,statement_governance}.py`;
  - the Sales ontology's `workspace_content(register.base_dir)`;
  - the content assets folder.
- **Tests tied to where code is (DR11):**
  - `tests/guard_register.py`: patch targets restated;
  - `tests/door_helpers.py`: `lock_of`;
  - `tests/test_workspace_door.py`: it parses the store files;
  - `tests/test_scenarios_publish.py`: it injects faults into the same instances, kept valid by the identity test.
- **The guard rails:** `tests/boundary_rules.py` and `docs/ways-of-working/Boundaries.md` (the rule, the counts, the
  S60 bullets).

### Unchanged

- **Tibi's engine.** Its fixture keeps working through the kept names and signatures, proven by the fixture test.
- **The stores' file formats.** There is no migration, so no new step on the way back.

## Stated limits (DR17)

- **The tooling** (`scripts/`, `automation/`) imports and writes the stores outside the component and the lock, for
  example `scripts/import_packs.py` and `scripts/data_reset.py`. S65 decides.
- **Folder stores reached by path** (`sources/`, `sections/`, `content/assets`): D4's command context covers writes
  through the stores, not files written by path.
