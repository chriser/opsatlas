# Independent review brief (the purple team)

The last step before a change goes live (the Definition of Done's quality bar). It replaces Codex's review, by the
Human's decision of 4 October 2026: OpsAtlas reviews its own work, self-sufficiently, inside Claude Code, with a
reviewer that had no part in building the change.

## Who the reviewer is

A separate Claude agent, started fresh for the review. It has not seen the builder's conversation, its plans or its
reasoning: only what this brief and the request give it, and the repository. It does not fix anything. It decides
whether the change is fit to go live, and says why. Use the project agent `independent-reviewer`
(`.claude/agents/independent-reviewer.md`) where the session offers it; otherwise a general agent given this brief.

The red team (`Red-Team-Brief.md`) attacks the promises during the build. The reviewer comes after it, once the red
team's exit rule is met, and judges the whole change: the promises, the code, the tests, the records and the go-live.

## What the request gives the reviewer

- The items (ADO ids and titles) and their **promises** and **stated limits** (the ADO description, the evidence
  record).
- The **branch** and the **commit range** (from the live commit to the head).
- The **evidence records** (`docs/benchmark/evidence/...`) and the **go-live notes** (what to build, which services to
  restart).
- Anything the builder could not test.

## Rules

- **Read-only.** Do not edit or restore any tracked file, commit, push, or write to ADO or the wiki. Create new files
  only under `tests/review/`, named `test_review_<item>_<what>.py`, for findings you can show with a failing test.
- Never contact the network, live services (ports 8780, 8773, 11434, 11435) or a model. Every thread is a daemon thread
  and every join has a timeout.
- Budget: about 40 tool calls, unless the request says otherwise. Say what you did not reach.

## What to check

1. **The gate.** Run `ruff check .`, the guard proofs (`tests/test_guards_proven.py`) and the full suite. Compare with
   the counts the record states. Name any test that fails, and any that only passes alone.
2. **Every promise has a proof.** For each promise, find where the code keeps it and the test or guard that proves it.
   A promise with no proof is a finding.
3. **No test was weakened.** Read the diff of every existing test the range changed. A restated test must keep what it
   checked: look for removed or loosened assertions, wider tolerances, skips, and expected failures added without a
   stated limit or an open item behind them.
4. **Every guard is real.** For each guard added or changed, check that its off-switch disables the mechanism it names
   (not a no-op) and that its proof fails when it is off.
5. **Stated limits are honest.** Each is real, Low, recorded, and tested where it can be. Nothing above Low is hidden as
   a limit, and nothing open is hidden as done.
6. **Boundaries.** Flag a store written outside its owning module, private methods called across modules, a new hook or
   copy of state, and any rule now enforced in more than one place.
7. **Data safety.** No secrets, no real organisations or people, synthetic data only.
8. **Records.** ADO, the evidence record, the wiki (the backlog page, the Decision Log, the Agent Handover Log) agree
   with the code and with each other; the go-live notes are consistent (what to build, what restarts).
9. **Go-live risk.** What existing workspaces meet on first start (new fields, file layouts, migrations), changed
   defaults, behaviour a user will notice, and the way back if it goes wrong.
10. **Fresh eyes.** Spend part of the budget attacking the promises yourself, first where the record says nothing was
    tested.

## Severity and verdict

- **High:** under one ordinary fault or one real concurrent request, a reader is given unapproved text or another
  version's text, an approval lands on a text nobody approved, the live version is lost or unreadable, data leaks
  across an access boundary, or the workspace stops accepting writes.
- **Medium:** the same outcomes only through an unusual but plausible path, or a promise with no proof, or a weakened
  test.
- **Low:** cosmetic, records only, or only through several rare faults at once.

**Verdict:** **PASS** (nothing above Low; the Lows are listed), or **FAIL** (a finding above Low). After a FAIL the
builder fixes, and the reviewer checks the fixes and what they touch, not the whole change again.

## The report

The verdict first; then each finding with its id, severity, evidence (file and line, test name, command output) and
why; the checks done, with their results; and what could not be checked.
