# Agent Handover Log

> ## ⛔ START HERE — every agent, every session
> 1. Read the [Working Agreement](/Ways-of-Working/Agent-Collaboration) **in full**.
> 2. Read the **latest entries below** before doing anything.
> 3. Work **only** where **Agent Owner = you**. Do not write code, edit tickets, or change the Wiki until both are done.

This page is the **single place** cross-agent handovers are recorded. **Do not put handovers in work-item tickets** — keeping them here makes the project state easy to inspect at a glance. Newest entry on top.

## Role reminder — who does what (re-read this every time)
| Agent | Does | Does **NOT** |
|---|---|---|
| **Human** (Operator) | Direction, approval, data/governance decisions, UAT → Closed | — |
| **Claude** | Review, coordination, backend & architecture, ADO grooming | Bulk-fix during review |
| **Codex** | Build the **assigned** module + tests; small `#id`-scoped commits | Groom backlog / change architecture / touch others' files |
| **Antigravity** | Research, evaluation, docs/Wiki, backlog **proposals** | Write code; change/close tickets it doesn't own; restructure backlog; decide architecture; act off its assigned ticket |

## How to log a handover (at the end of every working session)
Add a **new entry at the top** of the Log using this template. Keep it short and factual.

```
### YYYY-MM-DD HH:MM — <Agent> (<Role>)
- Tickets touched: #id, #id
- Done: what changed (commit hashes if code)
- Open / next: what remains, suggested next ticket
- Next owner: <Agent or "unassigned">
- Cautions: blockers, gotchas, do-not-touch areas the next agent must know
```

## Log

### 2026-06-22 17:50 — Codex (Build)
- Tickets touched: #726, #746, #747, #748, #834, #39, #40, #41, #42, #43, #44, #45, #46, #833, #664, #666, #667, plus parent state updates #25, #662, #725.
- Done: Completed Sprint 2 analytics event foundation: event schema/taxonomy (`9df1c61`), append-only JSONL event store (`72d57f4`), lifecycle instrumentation (`d753398`). Found and fixed guardrail wording bug #834 (`a78ac1b`). Completed data governance and supplier setup pack evidence: synthetic rules (`1838162`), anonymisation rules (`5d254a0`), source register template (`7d0ad99`), supplier setup overview (`7f2801a`), roles (`7b4eafe`), steps (`070175e`), structured JSON records (`c9bac8a`), metadata register (`008c494`), anonymisation validation (`3c15721`).
- Open / next: Sprint 2 delivery items are Resolved/Closed for UAT; only cross-sprint parents #724 and #725 remain Active. Next natural work is Sprint 2 UAT suite for the new analytics ledger + data-pack governance evidence, then close after human UAT.
- Next owner: Human for UAT; Claude/Codex for any UAT fixes.
- Cautions: `packs/` is intentionally git-ignored local source data, so tracked Sprint 2 data-pack evidence was placed under `docs/data-and-governance/learning-packs/supplier-setup/`. Analytics events intentionally avoid raw source text, raw questions/prompts, generated answers and issue detail.

### 2026-06-20 — Claude (Coordination)
- Tickets touched: — (governance setup, pre-backlog)
- Done: Created the **Ways-of-Working** Wiki section — [Working Agreement](/Ways-of-Working/Agent-Collaboration), this Handover Log, [Definition of Done](/Ways-of-Working/Definition-of-Done), [Effort Sizing](/Ways-of-Working/Effort-Sizing), [Build Governance](/Ways-of-Working/Build-Governance). Established the agent operating model for this project; handovers now live here (not in tickets); Antigravity's lane defined with explicit MUST-NOTs.
- Open / next: Human to review the Working Agreement (especially the Antigravity scope) and confirm. Per-agent **settings** enforcement of the "read-first" rule is still to be configured.
- Next owner: Human (review)
- Cautions: This is the new handover mechanism — update each agent's settings so its first step is to read the Working Agreement + this Log.
