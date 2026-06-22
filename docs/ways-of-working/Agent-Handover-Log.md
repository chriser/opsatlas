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

### 2026-06-22 19:24 — Codex (Sprint Planning / Pull-Forward)
- Tickets touched: #849, #725, #727, #731, #732, #733, #752, #781, #786, #749-#751, #753-#755, #787-#789, #850-#857.
- Done: Closed #849 after Human UAT pass. Pulled 25 story points of Codex-owned build work into Sprint 2: analytics aggregation/history (#727), diagnostic analytics (#732, #733, #752) and the first external-data-source slice via GOV.UK snapshots (#786). Created estimated implementation tasks #850-#857 for #732 and #733 so the stories are executable in Sprint 2.
- Open / next: Sprint 2 now has a substantial build queue. Natural execution order is #727 first, then #752/#732/#733, then #786 once the analytics aggregation foundation is stable.
- Next owner: Codex for build stories; Claude remains review owner on parent Features #725, #731 and #781.
- Cautions: Parent Feature spans were updated by child sprint rule: #725 and #731 now span Sprint 2 only; #781 starts Sprint 2 and still ends Sprint 7 because later regulatory/external-context children remain in future sprints.

### 2026-06-22 19:07 — Codex (UAT Bug Fix)
- Tickets touched: #849, Test Case #844, Test Run #43.
- Done: Reviewed the failed Sprint 2 UAT comment for `S2 UAT 08 - Duplicate review and auto-remediation suggestion`, recorded bug #849, and fixed the zero-section ingestion path. Heading-only or otherwise sectionless content now fails ingestion with a clear operator-visible error, clears stale sections, and records the source as `failed` rather than `ingested`. Governance now explains registered, failed, and defensive ingested-with-zero-section states distinctly.
- Open / next: Human should re-run Test Case #844 after the fix is deployed/pulled, using duplicate markdown files with real body content under the headings.
- Next owner: Human for UAT re-test; Codex/Claude if #849 needs follow-up.
- Cautions: A source can still be `not_ingested` in Governance when it is merely registered; for failed ingestion, the issue detail now points to fixing content and ingesting again.

### 2026-06-22 18:08 — Codex (Build/UAT Setup)
- Tickets touched: Azure Test Plans only; Sprint 2 delivery items referenced in UAT.
- Done: Created Azure Test Plan #835 `Sprint 2 UAT - Governance Workbench, Data Pack Onboarding and Analytics Foundation`, root suite #836, with frontend-focused manual test cases #837-#848. Cases cover launch/navigation, source upload/ingest, governance approval, Ask/citations, Process Registry, governance issue detection/review/acceptance, duplicate remediation, Analytics charts, guardrail wording #834, Settings audit trace and source cleanup.
- Open / next: Human to run the UAT cases in Azure Test Plans. Passing cases can support closing Sprint 2 Resolved items; failed cases should result in bugs.
- Next owner: Human for UAT.
- Cautions: The tests intentionally avoid backend/API inspection. One Process Registry case notes that if an approved source was added during the same session and the page remains empty, a normal app restart may be needed because the registry is built from approved sources at app startup.

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
