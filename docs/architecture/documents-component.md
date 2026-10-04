# The Documents component (REF S60, design v3 of 4 October 2026: the simpler design)

S60 is step 1 of the retrospective's migration path (REF F11 #2170), after S59's guard rails.

**One component owns a space's documents:** the register, the text, the passages, the content history and approval.
Clients read and command through it, by clearly named operations. Behaviour does not change.

**Status: the stop rule applied again after round 3 (4 October 2026, night). The decision is parked for the Human.**
Nothing is built.

## Round 3 on v3

Round 3 found 1 High, 4 Mediums and 5 Lows. Every finding above Low is in an area where an earlier round also found a
fault. The report is local: `research_notes/design-red-team-2026-10-04-S60-round3.md`, with probes
`research_notes/design-red-team-S60-probes/probe_s60_r3_*.py`.

**What holds, now confirmed by the round:**

- D2's import rules, with the component as `assistant.documents` plus `assistant.content` and the two leaves, are
  green from S60a to S60d.
- The leaves change no behaviour.
- `documents.govern` sets exactly what today's code sets.
- `strict_text` and `names_text`, and `review`, match today.
- With the actions left where they are, R2-9 is moot.

**What fails:**

- **R3-1, High, decision paths.** Knowledge's reconfirmation calls the register's own decide through the family
  register, and v3 names no target for it. If the family view's `decide` returned the action's result, a record could
  be approved against a file replaced on disk, with every existing test passing. That would break S8 silently.
- **R3-2, errors.** `decide` has four callers that each handle a refusal differently. Three lines of the table are
  wrong.
- **R3-3, transfer.** A core `transfer` calling the Sales `move_document` would break "the core never imports the
  Sales layer".
- **R3-4, D4.** The governance router's handlers, `documents.editorial` and the dropped command list leave raw stores
  outside the component, unstated.
- **R3-5, the contract.** A lone core from `create_app` has no Sales hooks and no workspace lock, so the suite misses
  the paths S60c changes.

**The flaw, as the round wrote it.** v3 defines the component by what it delegates to. There is no complete map of
today's callers giving each caller's operation, errors, actor and routing (one space or the family).

**The options**, in `reports/Morning questions 2026-10-05.md`, recommend building what three rounds found sound and
writing the caller map before designing the rest.

## How v3 came about

**v1, at `d6e2034`.** The design red team's round 1 found 4 Highs, 11 Mediums and 3 Lows.

**v2, at `ff7a1ec`.** v2 took every finding. Round 2 then found 2 Highs, 8 Mediums and 1 Low, all in round 1's areas,
so patching stopped.

**The design flaw.** v2 asked a refactor that changes no behaviour to carry three new mechanisms, each colliding with an
exception S57 made on purpose:

- **a runtime "one way in"** over stores whose readers write by design. Readers settle a committed version, views
  record under `if_free`, and background reviews settle;
- **a transfer that heals itself** over two live copies;
- **moving the decision code** ahead of the staged publish it is bound to.

**The Human's decision, 4 October 2026: the simpler design.**

- **Kept:**
  - one owner by construction;
  - the two kinds of text read;
  - `review` and `decide`, with the actor;
  - a corrected error contract;
  - the folder rule.
- **Dropped:** the runtime context, the self-healing transfer, and every move of the actions' code.
- **Bug #2186 first:** it is fixed narrowly, on its own branch.

The reports are local: `research_notes/design-red-team-2026-10-04-S60.md` and `…-S60-round2.md`. Their probes are in
`research_notes/design-red-team-S60-probes/`.

## What clients use today

Measured at `3e51749`, as re-counted by round 1 (DR6, DR7, DR16).

- **Reads:**
  - `get` 41, `list` 40, `read_content` 17;
  - `read_record_text` 5, two of them through the family register;
  - the passages' `list_for_source` 12.
- **Writes:**
  - `update` 7, `decide` 4, `remove` 2;
  - `add` 2, or 3 counting Tibi's engine's benchmark fixture;
  - staging and moves inside the content workflow, and the space moves.
- **The content workflow:**
  - its routes call 33 of its methods;
  - elsewhere: `names_text`, `current_version`, `first_version`, `ensure_all_versions`, `forget`, `retry_records`,
    `folders_of`, `comment`, `hooks`, `self_approval`, `rebuild_facts` and `refresh_processes`.
- **Importers of the three store modules:** 41 import edges from 26 modules. The modules are `sources.register`,
  `ingestion.store` and `content.store`.
- **11 production modules use the stores without importing them.**
- **Raw stores read from an app's state:** in production, 18 literal reads, plus 5 through a bound name, 4 through
  `getattr` and 5 through `family_register`. In tests, 184 reads in 30 files.
- **`.base_dir` on register-like receivers:** 54 reads in 14 modules.

## Promises (v3)

- **D1, behaviour unchanged.**
  - Every existing test passes. A test changes for one of two reasons only, and each change is listed in its story's
    record:
    - its set-up moves onto the interface;
    - a patch target moved with its code, and the test is restated to the same check.
  - S57's S1–S8 hold.
  - **Duck-typed consumers keep working:**
    - the read interface keeps the stores' method names;
    - `create_app(register, auth, retrieval, answer, …)` and `RetrievalService(register, section_store)` keep their
      signatures, which Tibi's frozen fixture calls positionally;
    - a hermetic test builds the fixture's core with a fake generator.
  - **An identity test:** `app.state.register`, `app.state.section_store` and `app.state.content` are the instances
    the component uses.
  - **Errors** stay as today; see the error contract below.
- **D2, one owner by construction, in production.**
  - The three store modules are imported only by the Documents component, with two exceptions:
    - Tibi's frozen fixture;
    - the Sales space move (`services/opsatlas_sales/spaces.py`), whose redesign the Human dropped from S60. It is a
      stated limit.
  - The component is the new package `assistant.documents` together with the content workflow package
    `assistant.content`, which stays where it is.
  - S59's rule becomes "the store modules are imported only by the Documents component" in S60a, with the reason
    recorded in Boundaries.md. Today's other importers stay allow-listed and shrink story by story.
  - **The import rules:**
    - The component never imports `assistant.answer` or `assistant.governance`. The content workflow's two helpers from
      them (the date reader `read_date` with `UNREADABLE`, and the phase names `PHASES` with `PHASE_WORDS`, all
      standard-library only) move to a leaf, `assistant/dates_and_phases.py`. `answer.scope` and `governance.scope`
      keep the names.
    - No module in the first package cycle (`ingestion`, `sources`, `process`, `ontology`, `eam`) imports the
      component. Those modules take it by injection, untyped.
    - The register's errors (`ContentReplaced`, `TextNotNamed`, `ApprovalOutsideDecide`) move to a leaf,
      `assistant/sources/errors.py`. The register keeps the names.
    - The component re-exports no store class.
  - S59's cycle rule stays green on its 18 entries, with no allowance added. A test runs S59's cycle check with the
    component's real imports.
- **D3, the contract.**
  - S1–S5, S7a and S8 are stated as properties of the component. They run in process on an app built by `create_app`,
    which is production's wiring: the actions engine, its rules, handlers and side effects, registered where they are
    today.
  - The suite calls the component directly, with no HTTP, holding the workspace's lock as a job does. It is never
    `governed_by=None`.
  - **S7a:** the component and its stores refuse a write without the lock, and reads never wait.
  - **S7b:** the door at the app's edge stays proven by the HTTP tests in `tests/test_workspace_door.py`.
  - **S6** stays with the answer pipeline's tests.
  - The suite quotes S1–S8.
- **D4, no raw store in production outside the component,** by construction and a check.
  - D2's import rule covers the imports.
  - An AST check covers the rest: loads of `register`, `content`, `section_store` and `family_register` on an app's
    state, or on a name bound from one, and `getattr(<…>.state, "<store>")`. Its allow-list holds today's reads,
    shrinks per story, and is empty by S60d.
  - **Stated limit:** a store held through a service's attribute is not seen by the check. This covers Knowledge, the
    governance desk, the answer service through retrieval, the family layout's `registers[...]`, and the first-cycle
    helpers given raw stores. Each is listed in the impact map and moved in its story.
  - Runtime enforcement is not in S60. That is the Human's decision; it would be a separate design, with the readers'
    settles in scope.
- **D5, the folder.**
  - A space's folder is the workspace's; else the injected register's; else `KP_DATA_DIR`.
  - The component builds its passages and content stores from its register's folder.
  - The lock's path comes from one place.
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

## Design (v3)

`Documents` is built once per space by `create_app`, as `app.state.documents`. It is a façade over that space's
register, passages store and content workflow. **It delegates to today's objects, and no code moves inside it in
S60.**

### The lock

- **Commands check the lock (`require`) and never take it.**
- **The component adds no lock and no governor of its own.**
- **`documents.govern(lock)` sets the governor of the stores it owns:** the register, the passages and the content
  store. The Sales layer's `govern()` calls it. Knowledge's and the desk's governors stay set as today, separately; this
  is stated.
- **Readers that also record something keep `if_free`.**

### Reading

- **The stores' read methods, by their names:** `get`, `list`, `read_content`, `space_of` and the passages'
  `list_for_source`.
- **The permissive read the source routes use:** `read_record_text`. A file replaced on disk is returned as it is.
- **The strict reads decisions use:**
  - `strict_text(id)`: today's `ContentService.record_text(source)` for that document, with its behaviour (a text,
    decoded or extracted) and its error on a replaced file (a `ContentError`).
  - `names_text(id, sha)`.
- **Also:** `current_version` and `first_version`.
- The contract suite has a replaced-file case for each read.

### Decisions: two commands, delegating

**`review(id, expected_sha, approve)`** is today's content-workflow decide (`ContentService.decide`), unchanged. It:

- checks the strict text;
- retries the records step;
- refuses "already approved" and "already rejected";
- calls the workspace's decide hook, or with no hook the audited action;
- writes the log.

Its actor is the request's signed-in person, as today, so it takes no actor parameter.

**`decide(id, status, sha, actor)`** is the audited action, executed through the actions engine as `_approve` and
`_reject` do today: `approve_source` or `reject_source`, with their rules and side effects as registered today.

- **The actor is passed as today's callers pass it:**
  - the signed-in person;
  - `system`;
  - the operator's name;
  - `service:workspace-key`.
- **The family view** routes `decide` as `FamilyActions` does today.

**The register's own decide stays in the store,** the one point of enforcement.

A contract test proves a decide hook that calls `decide` never re-enters `review`.

### The actions

The actions stay registered where they are today:

- the governance router registers the rules and handlers;
- `create_app` registers the side effects.

The component calls them through the engine. Nothing about them moves in S60.

### Editorial features

`documents.editorial` is the content workflow itself, with its methods by name: comments, the library (with its
drag-and-drop `move`), suggestions, images and views. They are unchanged.

### The space move

`transfer` delegates to today's `move_document`, with Bug #2186's fix. Its steps do not change in S60; making the move
atomic or self-completing is out.

### The family view

`FamilyDocuments` is a view over the three Sales spaces' `Documents`.

- It replaces `FamilyRegister`, `FamilySections` and `app.state.family_register` in S60c.
- It keeps their routing to the first holder, with Bug #2186's holder check for moves.

### The folder

As D5.

### Not in S60

- runtime enforcement;
- a self-healing transfer;
- moving the actions' or the publish's code;
- the commit number and the event per commit (phase 3);
- the hooks as a typed policy (S58);
- one transactional store.

### S57's three follow-ups

- **`record_text` beside `names_text`:** `strict_text` and `names_text`, in S60a.
- **`governed_by` set by the Sales app:** replaced by `documents.govern(lock)` for the documents' stores in S60a.
- **Hooks set from outside:** kept in S60, and a typed policy in S58.

## The error contract (as today; corrected by round 2's R2-8)

| Where | Today, kept |
|---|---|
| Content routes | `NotFound` (`KeyError`) → 404; `ContentError` (`ValueError`) → 409; `TextNotNamed` is not mapped → 500 (kept, stated) |
| `review`'s refusal of a decision | a `ContentError` at the content routes, as today |
| The stores' reads | return `None`, or raise `FileNotFoundError`; never `NotFound` |
| `strict_text` | `ContentService.record_text`'s behaviour and error on a replaced file; not `ContentReplaced`, so the Sales hooks are unchanged |
| Governance routes | the action's refusal: today's status and message, including the failed rule's name |
| Sales routes | `ValueError`, `TypeError`, `KeyError` → 409 |
| A write without the lock | `NotHolding` (`RuntimeError`) → 500 |

S60a adds a status test per route for these lines.

## Stories (v3)

| Story | What | Size |
|---|---|---|
| S60a | The foundation. `assistant/documents/`, the façade delegating to today's objects, built by `create_app`; `documents.govern`; the two leaves, with the old names kept. S59's document-store rule admits the component, with the reason recorded (today's importers stay allow-listed). The AST check with today's allow-list; the contract suite (S1–S5, S7a, S8) on `create_app`; the identity, fixture and cycle tests; the status tests | M |
| S60b | The core's clients onto it: the routes, retrieval, answering, governance, regulatory, analytics, process, the access layer, the settle step and statements. First-cycle clients by injection, untyped. The allow-lists shrink | L |
| S60c | The Sales layer onto it: `FamilyDocuments`, Knowledge, the governance desk, Tibi's routes, the Sales API, the library and the transfer (with Bug #2186's fix). S60's mark in the Sales content step goes (`_approve` / `_reject`); the `_save` mark stays S68's | L |
| S60d | The folder rule: `.base_dir` replaced in the 14 modules. The allow-lists shrink to the stated exceptions (the fixture and the space move); the AST check's allow-list is empty | M |

**Sequencing:**

- S60c goes before S58, because S58 builds on the family view's strict reads.
- S68's retrieval names come after S60b.

**Each story goes through:**

- its promises and its impact map on its ADO item;
- the gate;
- a red team on the code: for a refactor, its target is D1, anything that behaves differently;
- the independent review;
- a merge into `main`;
- a go-live.

## Impact map (v3)

- **New:**
  - `src/assistant/documents/`: the façade, the family view, the folder;
  - `src/assistant/sources/errors.py` and `src/assistant/dates_and_phases.py`: the leaves;
  - `tests/documents/`: the contract suite, and the identity, fixture, cycle and status tests.
- **Changed (S60a):**
  - `src/assistant/api/app.py`: builds the façade;
  - `src/assistant/sources/register.py`, `src/assistant/answer/scope.py`, `src/assistant/governance/scope.py`: the
    names now come from the leaves;
  - `src/assistant/content/service.py`: the helpers from the leaf;
  - `services/opsatlas_sales/app.py`: `govern()` calls `documents.govern`;
  - `tests/boundary_rules.py` and `docs/ways-of-working/Boundaries.md`: the rule, the AST check, the counts.
- **Changed (S60b–S60d), from call sites and attribute reads:**
  - the 26 importing modules;
  - the 11 users without imports: the access layer, the answer service, the governance statement review and
    statements, the settle step and the Sales statement governance;
  - `routes_content` (33 methods), `routes_feedback`, `routes_statements`, the receipts' `current_version`;
  - the Sales modules: `app`, `spaces`, `knowledge`, `governance`, `content`, `tibi_api`, `routes_sales_api`,
    `routes_spaces`, `routes_conversations` and `statement_governance`;
  - the Sales ontology's `workspace_content(register.base_dir)`, the content assets folder, and the 14 `.base_dir`
    modules.
- **Tests tied to where code is:**
  - `tests/guard_register.py`;
  - `tests/door_helpers.py`;
  - `tests/test_workspace_door.py`;
  - `tests/test_scenarios_publish.py`, kept valid by the identity test.
- **Unchanged:**
  - Tibi's engine, proven by the fixture test;
  - the stores' file formats: no migration.

## Stated limits

- **Runtime enforcement of one way in is not in S60.** D4's check does not see stores held through a service's
  attributes, and the impact map lists those.
- **The Sales space move keeps its raw access** to the stores and the content database (D2's second exception) until a
  transfer redesign.
- **The tooling** (`scripts/`, `automation/`) is outside the rules and the lock. REF S65 decides.
- **Folder stores reached by path** (`sources/`, `sections/`, `content/assets`) are seen by no check.
- **`TextNotNamed` at the content routes answers 500**, as today.
