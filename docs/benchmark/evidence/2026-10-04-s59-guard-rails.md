# REF S59: the guard rails (4 October 2026)

Step 0 of the retrospective's migration path (REF F11 #2170). These are checks in the gate that make a change crossing
a module boundary fail within seconds. Nothing in the running app changes. The rules, the counts and the stated limits
are in [Boundaries.md](../../ways-of-working/Boundaries.md).

## Promises

- **G1:** a change fails the gate within seconds if it does any of these:
  - adds an import across a boundary;
  - names a store's file outside its owner;
  - reaches into another module's private member.
- **G2:** nothing in the running app changes.
- **G3:** the allow-lists only shrink. An allowed crossing that has gone must be removed from its list.

## The independent review

### First review, at `04757d6`

**Verdict: FAIL**, on two Medium findings where G1 was not kept for a form the code already uses:

- **F1:** importing another module's private name (`from m import _x`) is not seen by ruff. Eleven such imports were
  uncounted.
- **F2:** a store's file named with a folder (`'data/ontology.db'`) or in an f-string (`f'{root}/content.db'`) was
  invisible to the store check. Three existing crossings and 17 file names were missing from the map.

There were five Lows:

- **F3:** a stale or blanket `noqa` mark passes.
- **F4:** forms that slip, to be named as stated limits.
- **F5:** the scan's scope; IAM's rule should be an allow-list; the cycle rule is package-level.
- **F6:** the engine's exemption is wider than the page said.
- **F7:** the fixture's path handling; two copies of the helpers; generic store names.

The report is in `research_notes/independent-review-2026-10-04-S59.md` (local). Its tests are in
`research_notes/independent-review-tests/test_review_S59_guard_rails.py`.

### The fixes

- **F1:**
  - A new rule: no module uses another module's private name, by importing it or through the module's name.
  - A package's private names are its own, and Tibi's engine may use its own.
  - Today's 12 are allowed: the 11 imports, plus the engine reading the Sales claims' `_ALLOWED_ACRONYMS`, which ruff's
    exemption for the engine had hidden.
  - REF S68 #2184 gives them public names; the engine's waits for its next version.
  - A planted test and a guard prove it.
- **F2:**
  - A store's name counts wherever it is the last part of a string constant, f-string parts included.
  - Seventeen file names were declared (89 in all).
  - Four crossings were allowed, giving 12 stores with exceptions.
  - Planted tests cover a folder, an f-string and a Windows path.
- **F3:** ruff's RUF100 (a mark that suppresses nothing) and PGH004 (a blanket mark) are on for production code;
  today's code has neither. A planted test proves it.
- **F4:**
  - An import named by a string constant (`import_module("…")`, `__import__("…")`) is now caught.
  - The other forms are stated limits on the page: a computed import, private access without a dot, a store reached
    without its file name, folder stores and other file types, re-exports, and package-level cycles.
- **F5:**
  - The scan covers every module under `src/`, not only `assistant`.
  - IAM's rule is an allow-list: nothing outside itself but the settings.
  - The cycle rule is described as package-level.
- **F6:** the page counts the engine's 24 hidden private-access sites: 13 on the third-party voice model, 10 on its own
  objects, and 1 on the Sales layer, now caught.
- **F7:**
  - The fixture no longer adds to the path on each use.
  - The builders import the helpers as the door tests do.
  - Generic store names are a stated limit.

The reviewer's tests went from 11 failing to 5:

- **3** are stated limits: a store reached through `with_suffix`, through an imported constant, or through a path
  attribute.
- **2** are framed against ruff, or against a count of zero. The new rule catches those imports, and today's are on its
  allow-list.

The gate after the fixes:

- `ruff check .` is clean.
- `tests/test_boundaries.py`: 22 passed, up from 16.
- Guards: 57, each proven (one new).
- Full suite: 1,545 passed, plus 5 expected failures.

### Re-review of the fixes, at `9c36045`

**Verdict: PASS**, with nothing above Low. The reviewer checked:

- **F1 and F2 are closed.** The reviewer's own scan, using none of the builder's functions, finds exactly the 12
  private uses and exactly the 89 store names. The 18 non-owner namings match the 12 stores with exceptions. Every
  planted form is caught.
- **F3 to F7 are closed.**
  - The mark rules fire on every production path tried.
  - IAM's allow-list catches five planted imports.
  - The engine's 24 sites split 13/10/1, checked one by one.
  - The door tests pass alone.
- **G2 holds:** no change under `src`, `services` or `config`.
- **The gate** matches this record.

There were five new Lows:

- **N1:** a store named inside a SQLite URI with a query slips.
- **N2:** a file-level `# ruff: noqa: SLF001` allows every reach-in in its file.
- **N3:** a subclass in another module using its base's private member through `self` or `super()` passes.
- **N4 (records):** the stated limits said none was used today, but some are.
- **N5 (records):** the tooling (`scripts/`, `evaluation/`) is outside the AST rules, and the page did not say so.

What was done:

- **Records:** N4 and N5 are fixed on the page, and N1–N3 are stated there as limits. That is a records-only commit,
  so the merged code is the code reviewed.
- **REF S65 #2176** takes N1 and N2, which are cheap to close. It also takes the decision on bringing the tooling
  under the rules (N5).

The report is in `research_notes/independent-review-2026-10-04-S59-fixes.md` (local). Its tests are in
`research_notes/independent-review-tests/test_review_S59_fixes.py`: 23 pass and 4 fail (N1 ×2, N2, N3).
