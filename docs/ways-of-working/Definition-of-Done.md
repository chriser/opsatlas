# Definition of Done & Work-Item State Model

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

1. **Code complete** and merged to `main` (small, focused, `#id`-scoped commit; conventional message + Co-Authored-By).
2. **Green gate**: `pytest` and `ruff check .` pass; module-boundary checks (e.g. import-linter contract, if configured) intact; `npm run build` passes **if** a frontend surface was touched.
3. **Tests** added/updated covering the change (offline/deterministic where possible).
4. **ADO updated**: status set, and a comment recording the **commit hash** + what was delivered. When the work affects another agent, add a handover entry in the **[Agent Handover Log](/Ways-of-Working/Agent-Handover-Log)** Wiki page (not in the ticket).
5. **Boundaries & data safety**: module boundaries intact; no secrets in code; **all data remains synthetic / anonymised only** — no real or confidential source material, no real system or organisation names, no personal data, nothing commercially sensitive enters the repo, indexes, logs or tooling.
6. **Docs**: module maturity / relevant Wiki pages updated if behaviour or surface changed.
7. **Browser-verified** for UI work (preview snapshot/screenshot + no console errors).

If any item can't be met, the ticket stays **Active** (or **New**) with a comment explaining the blocker — do not Resolve partially-done work.

## UAT → Closed
The Human (with Antigravity support for scripts/evidence) runs the UAT test cases held in ADO against Resolved items. Passing UAT → **Closed**. A failure raises a **Bug** (owner assigned, sized) and the parent stays Resolved/Active until fixed.

_Linked: [Effort Sizing](/Ways-of-Working/Effort-Sizing) · [Agent Collaboration](/Ways-of-Working/Agent-Collaboration) · [Agent Handover Log](/Ways-of-Working/Agent-Handover-Log)_
