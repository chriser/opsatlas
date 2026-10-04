# Module boundaries

The checks that keep OpsAtlas's parts apart, run in the gate (REF S59, after the retrospective of 4 October 2026). Most
faults found while delivering the REF programme came from one fact kept in many places: a store written from several
modules, a rule checked at every call site, a private method called from another package. These checks make a change
that reaches across a boundary fail within seconds, instead of being found by a red team days later. They change
nothing in the running app.

## The rules

They cover all production code: every module under `src/` (the core, `assistant`, and any new package there) and under
`services/` (the Sales layer and Tibi's engine). Tooling that does not run in the app, `scripts/` and `evaluation/`, is
outside the rules in `tests/boundary_rules.py`; ruff's private-member check covers `scripts/`, and its two mark rules
cover both. `automation/` and `experiments/` are outside the AST checks. Today `scripts/evaluate_evidence.py` takes
four private names of `rag_vs_oag`, and the scripts name 29 stores owned elsewhere (most in `data_reset.py`, which
resets the core's store files). Whether to bring the tooling under the rules is parked for the Human, with a
recommendation (REF S65).

| Rule | Where | Today |
|---|---|---|
| The core never imports the Sales layer or Tibi's engine (`services`) | `tests/boundary_rules.py` | clean |
| IAM (`assistant.iam`) imports nothing outside itself but the settings | same | clean |
| A document store's module (`sources.register`, `ingestion.store`, `content.store`) is imported only by today's importers | same | 41 allowed |
| Tibi's engine (`services.sme_interviewer`) reaches outside itself only as today (its benchmark fixture; the shared conversation contract, claims, foundation, workspace and activity modules) | same | 20 allowed |
| No new import edge between packages inside a package cycle (today: `ingestion`, `sources`, `process`, `ontology`, `eam`; and `answer`, `retrieval`, `analytics`, `governance`, `evidence`) | same | 18 allowed |
| No module uses another module's private name (`_x`), by importing it or through the module's name; a package's private names are its own, and Tibi's engine may use its own | same, `PRIVATE_ALLOWED` | 1 allowed (Tibi's engine) |
| Each store's file name (89 JSON, JSONL and SQLite names, Tibi's included) is named in code only by its owning module; a new store must be declared with its owner. A name counts wherever it is the last part of a string: `'content.db'`, `'data/ontology.db'`, `f'{root}/content.db'`, also inside a SQLite URI with a query (`'file:content.db?mode=ro'`) | same, `STORE_OWNERS` | 12 stores with allowed exceptions |
| No reaching into another module's objects' private members in production code (ruff `SLF001`); a mark that no longer suppresses anything (`RUF100`) or a blanket mark (`PGH004`) fails too | `pyproject.toml` | 3 sites on 2 lines, marked `# noqa: SLF001` |

Tests (`tests/test_boundaries.py`) check each rule against the code, and each check against planted code, so none is
vacuous; three guards in the guard register prove the checks by switching them off.

## Allow-lists only shrink

Each rule starts from today's code: what already crosses a boundary is listed in `tests/boundary_rules.py` (`ALLOWED`,
`PRIVATE_ALLOWED`, `STORE_ALSO`) or marked with `# noqa: SLF001`. A check fails for a **new** crossing, and also for an
allowed one that has **gone**: remove it from its list, or remove the mark, so the list stays true and only shrinks.

- **To remove a crossing:** change the code, then delete its entry. Where each one goes:
  - **REF S60 (the Documents component)** takes:
    - the document stores' importers;
    - the space moves' raw access to the content database;
    - the private calls into the content workflow (`_approve`, `_reject`).
  - **REF S58 (the Sales knowledge layer)** gives the Sales review history one owner. It also takes the Sales content
    step's write of the records (`knowledge._save`, one marked site), which changes the records' governance notes and
    so belongs with S58's decisions.
  - **The other store exceptions** are wiring and tooling that name another owner's file. They are kept unless a
    change removes them:
    - the apps building a store at its path;
    - the IAM recovery command;
    - the engine's replays and fingerprint;
    - the Sales records reading the product corpus;
    - the evaluations and the evidence report naming what they read.
  - **REF S68 #2184** gives public ways in, in place of the other private uses:
    - retrieval's `cosine_similarity`, `word_tokens`, `is_relevant`, `fuse_scores`;
    - governance intelligence's `LINK`, `expansion_matches_acronym`, `readability_sentences`, `readability_word_count`;
    - access's `walk_routes`;
    - IAM's `session_view`, its existing `session_by_id` (for the delivery recheck), and `emergency_recovery` (the
      recovery command's transaction, moved into IAM);
    - the evaluation's `best_fact_match`, `answer_content_tokens`, `normalise_text`, `REFUSAL_RE`.
  - **Tibi's engine** reads the Sales claims' `_ALLOWED_ACRONYMS`; its next version takes a public name. Its files are
    under its fingerprint.
- **To add a store:** declare its file name and owning module in `STORE_OWNERS`. Only the owner names the file; others
  go through the owner.
- **Never add an allowance to make a check pass.** A new crossing is a design question: bring it to the item's design
  (its impact map) and the independent review, with the reason written here.

## What is exempt, and why

- **Tibi's engine** is a component with its own fingerprint, gate and replays, and its files are not edited for lint
  changes. Two things follow:
  - **Its own private names.** The engine may use them: the private-name rule ignores a use inside the engine.
  - **Ruff's check.** Ruff's private-member check is off for all of the engine's files, so it does not see the engine
    reaching into any object's private members, not only its own. Today that hides 24 sites:
    - 13 on the third-party voice model;
    - 10 on the engine's own objects;
    - 1 on the Sales layer. That one, the claims' `_ALLOWED_ACRONYMS`, the private-name rule catches and allows above.
- **Tests** and **evaluation** may look inside what they test. Tests may also keep `noqa` marks that no longer
  suppress anything. Set-up should still go through public requests (below).

## What the checks do not see (stated limits)

The checks read the code's text; they do not run it. These forms pass without any check firing. The independent
reviews' tests pin each one down. Where one is used in production today, it is said below; the others are not used
(the re-review's scan, 4 October). A change that uses one should say so in its design. One that S59's re-review found
is closed (REF S65 #2176): a store named in a SQLite URI.

- **Imports.**
  - An import whose module is computed, such as `import_module(name)` with a variable. An import named by a string
    constant, `import_module("…")` or `__import__("…")`, is caught.
  - Importing through a package that re-exports a document store. Adding the re-export would itself be an allow-list
    change.
  - A name re-exported by the package root. IAM's rule allows the root, because `from assistant import settings`
    imports through it, so a name re-exported by `src/assistant/__init__.py` would pass IAM's rule. Today that file
    holds only `__version__`.
- **Private members.**
  - Reached without a dot: `getattr(obj, "_x")`, `vars(obj)["_x"]`.
  - The private members of an object or class inside the engine. Used today: the 24 sites above.
  - A file-wide or range suppression of the private-member check that names it: `# ruff: noqa: SLF001` or
    `# flake8: noqa: SLF001`, also behind a doubled `#`, after other text in the comment, or with codes separated by
    spaces or tabs, and `# ruff: disable[SLF001]` (the blanket `# ruff: noqa` and `# flake8: noqa` fail ruff's
    PGH004). The count of marks does not see them. S65 tried to list the forms and stopped under the stop rule (two
    reviews found more). A simpler rule is with the Human: no file-wide or range directive in production code but
    today's two (`# ruff: noqa: E501` in two activity-model renderers), or let ruff decide (its SLF001 findings with
    and without `--ignore-noqa` differ only by the listed marks). None exists today.
  - A subclass in another module using its base's private member through `self` or `super()`. Python often treats
    `_x` as "protected", so a design that relies on it should say so.
- **Store names.**
  - A store reached without naming its file:
    - the owner's constant, imported. Used today: the OAG coverage evaluation imports `rag_vs_oag.DEFAULT_LABELS_PATH`
      and reads the questions file that `rag_vs_oag` owns;
    - an object's path attribute (`sqlite3.connect(core.state.content.path)`);
    - a name built with `with_suffix`. Used today: `eval/oag_coverage.py` and `eval/rag_vs_oag.py`;
    - a fully computed name (`f"sales-{kind}.json"`). Used today: `analytics/oag_benchmark.py` globs the
      `rag-vs-oag-*.json` reports that `rag_vs_oag` writes.
  - A store opened through a variable path, such as the engine's latency report's read-only SQLite URI
    (`f'file:{path}?mode=ro'`): the name is not in the code.
  - A string ending in a file name counts as naming it, a URL with a query or a message included: such a string fails
    closed, as an undeclared store or a crossing.
  - Stores that are folders (`sources/`, `sections/`, `content/assets`), and other file types (the workspace's
    `.lock`, `.md` and `.txt` sources, `.csv` exports).
  - Ownership is by file name. Different files that share a generic name (`config.json`, `report.json`,
    `manifest.json`, `profile.json`, `scenarios.json`) count as one store. A new module naming one fails, and its
    design either names the file distinctly or records the exception.
  - A string that ends in a file name but is not a file counts as one too (`'/openapi.json'`, the API schema's route,
    is declared for that reason).
- **Package cycles.** The cycle rule looks at imports between packages. A new import between two modules along a
  package edge that is already allowed passes.

## Test set-up through public requests

Shared builders (`tests/builders.py`; the `sales_workspace` fixture in `tests/conftest.py`) arrange state the way a
person would, through the routes: a hermetic Sales app, signed in, with an organisation space, and documents uploaded,
ingested and approved over HTTP. A test that writes a store directly to arrange state is tied to internals (the
workspace door alone made 129 such tests fail). Move a test onto the builders whenever it breaks for internal reasons;
`tests/test_workspace_door.py` is the first.
