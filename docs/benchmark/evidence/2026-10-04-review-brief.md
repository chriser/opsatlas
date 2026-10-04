# Review brief: REF F10, H3b and S57 (4 October 2026)

For the independent reviewer (`docs/ways-of-working/Independent-Review-Brief.md`), which replaces Codex's review by the
Human's decision of 4 October 2026. S57 (#2140) was labelled S23 when it was built, and S58 (#2158) S24.

Branch `claude/ref-h3b`, from the live phase 2 head `1b9bc23` to the head named in ADO. The range holds three items,
built and red-teamed under the Definition of Done (`docs/ways-of-working/Definition-of-Done.md`); its last step is
this review. None of it is live.

| Item | ADO | What it is | Record |
|---|---|---|---|
| REF F10 | #2131 | The Definition of Done in code: seeded random scenarios, guards each proven by switching it off, the red-team brief | commits `ddf8c73`, `e858453` |
| REF H3b | #2126 | Scope applied to every evidence path of an answer (dates, sites, supersession; one reading per answer) | `2026-10-03-h3b-stop-rule.md`, `2026-10-03-h3b-set-v3.md` |
| REF S57 (was S23) | #2140 | A staged publish; the workspace's door (one lock per write request, stores check it); approvals decided in the register, naming their text (S8) | `2026-10-04-s23-red-team.md` |

Size at the first review: 44 commits from `1b9bc23`, 76 test files; see `git log 1b9bc23..` for the current range.

## What to check

- **The promises.** S57's S1–S8 and their stated limits are in ADO #2140's description and at the end of the S23
  record; H3b's are in its stop-rule record. Do the code and the tests keep them, as written?
- **The door** (`src/assistant/storage.py`: `WriteDoor`, `locked`, `if_free`, `writes`, `require`;
  `src/assistant/api/app.py`: `DOOR_PASSES`; `services/opsatlas_sales/app.py`: `govern`). Is every write path behind
  it, can a reader wait, can a lock be taken before it?
- **The register's decision** (`src/assistant/sources/register.py`: `decide`, `names_text`, `update`). Is it the only
  way an approval changes, as S8 says, with no exception?
- **The staged publish** (`src/assistant/content/service.py`: `_write_version`, `_swap`, `_publish_version_action`,
  `_after_commit`, `_records_step`, `retry_records`).
- **The actions engine** (`src/assistant/ontology/actions.py`): a decision stands whatever its side effects do.
- **The tests' restatements.** Older red-team tests were restated for the door; each says so in its docstring. Check
  that no restatement weakened what a test checks.

## How to run the gate

From the worktree root, with the project's virtual environment:

```
ruff check .
python -m pytest -p no:cacheprovider -W ignore -rA tests/test_guards_proven.py      # 53 guards, each proven
python -m pytest -p no:cacheprovider -W ignore -q --deselect tests/test_guards_proven.py
```

The full suite passes with expected failures only: the stated limits (strict) and REF S24's open findings (strict).
`tests/test_ontology_store.py::test_synthetic_scale_1000_objects_runs_under_two_seconds` is a timing test that fails
under load and passes alone.

## Known and open

- **Stated limits** (low): listed at the end of the S23 record, each with a strict expected-failure test where one
  could be written.
- **REF S58 #2158** (open; was S24): the Sales knowledge layer's own governance (its own copy of each record's text and hash,
  its approval and review state, scope resolutions, evidence bindings), split from S23 by the Human after round 11.
  Three Mediums, in `tests/redteam/test_s23_round11_redteam.py`, marked REF S58 (labelled S24 in the test file). They exist in live code today.
- Raised earlier, separate: REF S16b #2136 (the avatar route has no delivery checks) and S19b #2137 (the delivery
  recheck ignores approval).

## Going live, after the review

Claude runs it (the Human's decision, 4 October 2026), in this order:
1. Tag the current live state (`live-2026-10-03b` is the live commit `1b9bc23`).
2. Stop the core and copy the live workspace's data folder, `.runtime/opsatlas-sales` (all spaces, about 18 MB). On its
   first start the new code stamps every old passages file with its text's fingerprint, a format the live code cannot
   read (the first independent review's R1): **the way back is the tag plus this copy**, never the tag alone.
3. Set aside untracked files in the live folder that `main` tracks (the local-avatar documents and experiments, and
   `.claude/agents/independent-reviewer.md`), after comparing them; nothing is deleted.
4. Merge the reviewed branch into `main`; move the live folder to `main`.
5. Rebuild the panel (`npx vite build`): the governance page and the document page send the text they decide on.
6. Start the core. Tibi's voice service needs no restart: its engine fingerprint (`f7705b59aa1f`) and its runtime
   imports are unchanged (confirmed by the independent review).
7. Check that the core, the panel and Tibi respond, then tag `main` as the new live state and report.
