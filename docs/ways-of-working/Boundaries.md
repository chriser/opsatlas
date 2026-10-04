# Module boundaries

The checks that keep OpsAtlas's parts apart, run in the gate (REF S59, after the retrospective of 4 October 2026). Most
faults found while delivering the REF programme came from one fact kept in many places: a store written from several
modules, a rule checked at every call site, a private method called from another package. These checks make a change
that reaches across a boundary fail within seconds, instead of being found by a red team days later. They change
nothing in the running app.

## The rules

| Rule | Where | Today |
|---|---|---|
| The core (`assistant`) never imports the Sales layer or Tibi's engine (`services`) | `tests/boundary_rules.py` | clean |
| IAM (`assistant.iam`) imports no domain package | same | clean |
| A document store's module (`sources.register`, `ingestion.store`, `content.store`) is imported only by today's importers | same | 41 allowed |
| Tibi's engine (`services.sme_interviewer`) reaches outside itself only as today (its benchmark fixture; the shared conversation contract, claims, foundation, workspace and activity modules) | same | 20 allowed |
| No new import edge inside a package cycle (today: `ingestion`, `sources`, `process`, `ontology`, `eam`; and `answer`, `retrieval`, `analytics`, `governance`, `evidence`) | same | 18 allowed |
| Each store's file name (72 JSON, JSONL and SQLite files, Tibi's included) is named in code only by its owning module; a new store must be declared with its owner | same, `STORE_OWNERS` | 8 stores with allowed exceptions |
| No reaching into another module's private members in production code (ruff `SLF001`) | `pyproject.toml` | 9 sites, marked `# noqa: SLF001` |

Tests (`tests/test_boundaries.py`) check each rule against the code, and each check against planted code, so none is
vacuous; two guards in the guard register prove the checks by switching them off.

## Allow-lists only shrink

Each rule starts from today's code: what already crosses a boundary is listed in `tests/boundary_rules.py` (`ALLOWED`,
`STORE_ALSO`) or marked with `# noqa: SLF001`. A check fails for a **new** crossing, and also for an allowed one that
has **gone**: remove it from its list, so the list stays true and only shrinks.

- **To remove a crossing:** change the code, then delete its entry. The work planned to remove most of them: REF S60
  (the Documents component) takes the document stores' importers, the space moves' raw access to the content database
  and the private calls into the content workflow; REF S58 gives the Sales review history one owner and removes the
  Sales layer's private calls into retrieval.
- **To add a store:** declare its file name and owning module in `STORE_OWNERS`. Only the owner names the file; others
  go through the owner.
- **Never add an allowance to make a check pass.** A new crossing is a design question: bring it to the item's design
  (its impact map) and the independent review, with the reason written here.

## What is exempt, and why

- **Tibi's engine** may use its own private members: it is a component with its own fingerprint, gate and replays, and
  its files are not edited for lint changes.
- **Tests** and **evaluation** may look inside what they test. Set-up should still go through public requests (below).

## Test set-up through public requests

Shared builders (`tests/builders.py`; the `sales_workspace` fixture in `tests/conftest.py`) arrange state the way a
person would, through the routes: a hermetic Sales app, signed in, with an organisation space, and documents uploaded,
ingested and approved over HTTP. A test that writes a store directly to arrange state is tied to internals (the
workspace door alone made 129 such tests fail). Move a test onto the builders whenever it breaks for internal reasons;
`tests/test_workspace_door.py` is the first.
