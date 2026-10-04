# Definition of Done & Work-Item State Model

> **19 September 2026 — current user instruction:** no new ADO UAT Test Cases, Test Suites or Test Plans are required. Record acceptance criteria and verification evidence in the delivery story and repository; retain existing test artifacts as history. Automated regression checks and Human acceptance still apply. For documentation-only work, verify the delivered documents, links and publication instead of adding implementation-mirroring tests. The historical UAT wording below must be read with this update. See the [SME Interviewer delivery rulebook](../initiatives/sme-interviewer/06-evaluation-and-delivery.md).

This is the system of record for what each work-item **state** means and the bar a ticket must clear before an agent marks it **Resolved**. It exists so the backlog stays honest and the Operator (Human) has a clean UAT queue.

## State model (Agile process)

| State | Meaning | Who sets it |
|-------|---------|-------------|
| **New** | Not started. Must already have an **Agent Owner** and an **effort size**. | Anyone (at creation) |
| **Active** | In progress. Treated as **locked by its Agent Owner** — no other agent works it. | The owning agent when it starts |
| **Resolved** | Implementation complete and self-verified (see DoD below). Awaiting Human UAT / acceptance. | The owning agent |
| **Closed** | **Verified** against the DoD — UAT passed / Human-accepted (or reviewer-confirmed for internal-only work). | **Human only** (after UAT) |
| **Removed** | Cancelled or superseded. | Anyone, with a reason comment |

**Key rule: agents Resolve, they do NOT self-Close.** Closing is the Human's acceptance step. So *every Resolved ticket is an item waiting for UAT*. That split (recent Resolved awaiting review vs older Closed already verified) is intentional, not a defect.

## Definition of Done (must all be true before an agent sets **Resolved**)

1. **Code complete** on a work branch (`claude/<item>`, from `main`), reviewed (the independent review, below), then
   merged into `main` (small, focused, `#id`-scoped commits; conventional message + Co-Authored-By). `main` is the
   integration and release line: going live means the live folder at `main`, tagged `live-YYYY-MM-DD[x]` (the Human's
   decision of 4 October 2026).
2. **Green gate**: `pytest` and `ruff check .` pass; module-boundary checks (e.g. import-linter contract, if configured) intact; `npm run build` passes **if** a frontend surface was touched.
3. **Tests** added/updated covering the change (offline/deterministic where possible).
4. **ADO updated**: status set, and a comment recording the **commit hash** + what was delivered. When the work affects another agent, add a handover entry in the **[Agent Handover Log](Agent-Handover-Log.md)** Wiki page (not in the ticket).
5. **Boundaries & data safety**: module boundaries intact; no secrets in code; **all data remains synthetic / anonymised only** — no real or confidential source material, no real system or organisation names, no personal data, nothing commercially sensitive enters the repo, indexes, logs or tooling.
6. **Docs**: module maturity / relevant Wiki pages updated if behaviour or surface changed.
7. **Browser-verified** for UI work (preview snapshot/screenshot + no console errors).

If any item can't be met, the ticket stays **Active** (or **New**) with a comment explaining the blocker — do not Resolve partially-done work.

## Quality bar (3 October 2026, the Human's decision)

Added on top of the list above, adapted to OpsAtlas and tiered (REF F10). **Full** for anything that touches state,
access, governance, deletion or Tibi's engine; **lighter** (items 1, 2 and named tests) for panel-only, documentation and
evaluation-set work. Model behaviour keeps the benchmark-first rule: registered marks, a same-session baseline, the
holdout looked at once.

1. **Promises first.** Before any code the item states what must always be true, what can go wrong, and the simplest
   design that keeps the promises, on the ADO item, so the Human can object before anything is built. The design says
   which stores, call sites and paths it touches (an **impact map**, found with the import graph and the store owners,
   not from memory), and for the full tier a red team attacks the design on paper before it is built.
2. **The same list of what can go wrong, every time**, each promise checked against each line with a named test, or one
   line on why it cannot happen:
   - a crash at any step, including between two related writes;
   - a write that fails, or succeeds but reports failure (JSON stores, SQLite, files);
   - a restart mid-operation (core or Tibi restarted during a job, review or conversation; a job that is gone);
   - two requests at once on the same thing (two approvals, approve while editing, concurrent turns);
   - duplicate, stale, out-of-order or malformed input (double submit, stale hash, replayed ticket, empty or oversized
     text, damaged files);
   - access changing mid-way (session revoked, role removed, document restricted between retrieval and delivery);
   - a dependency down or slow (models, embeddings, Tibi, the diagram service);
   - the evidence changing underneath (a document edited, approved or withdrawn between steps);
   - date and time boundaries (midnight, month and year file rollover, effective dates, retention pruning);
   - model output varying run to run (compare within a session, judge independently, never assert exact wording).
3. **Random scenarios.** Stateful and pure logic gets a seeded random-scenario suite (`tests/scenarios.py`): thousands
   of runs mixing the lines above, the feature off and on, every promise checked after every step, models faked, in
   seconds, in the gate. A failure prints the seed that replays it.
4. **Every guard proven.** Each guard is in `tests/guard_register.py` with how to switch it off and the tests that
   must then fail; `tests/test_guards_proven.py` proves each one in the gate.
5. **A red team, then an independent review.** A separate agent of Claude's, given only the promises and the code
   ([brief](Red-Team-Brief.md)), tries to break them; Claude fixes what it finds until a round finds nothing above Low.
   Then a fresh reviewer agent that took no part in the build ([brief](Independent-Review-Brief.md)) judges the whole
   change: the gate, every promise's proof, that no test was weakened, the guards, the stated limits, the boundaries,
   the records and the go-live. It replaces Codex's review (the Human's decision, 4 October 2026): the workflow is
   self-sufficient inside Claude Code.
6. **Findings become permanent.** Each fault a reviewer finds becomes a new scenario kind in the random suite, not one
   more test.
7. **Stop rule.** Two review rounds in a row with faults in the same area: stop patching, write down the design flaw,
   bring the Human a simpler design. A fault in the same area right after a redesign counts; no "completing the design"
   patch past the rule.
8. **One rule, one place.** A new rule (who may write, what counts as approved, which text is read) gets one point of
   enforcement and an inventory test that proves nothing goes around it, rather than a check at every call site.
9. **Done** means all of the above, plus the gate and CI green, merged into `main`, ADO, the wiki (the epic's backlog
   page, the Decision Log and the [Agent Handover Log](Agent-Handover-Log.md)) updated, and the independent review's
   verdict PASS.

## UAT → Closed
The Human (with Antigravity support for scripts/evidence) runs the UAT test cases held in ADO against Resolved items. Passing UAT → **Closed**. A failure raises a **Bug** (owner assigned, sized) and the parent stays Resolved/Active until fixed.

_Linked: [Effort Sizing](Effort-Sizing.md) · [Agent Collaboration](Agent-Collaboration.md) · [Agent Handover Log](Agent-Handover-Log.md)_
