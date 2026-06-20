# Agent Collaboration — Working Agreement

> ## ⛔ START HERE — every agent, every session, no exceptions
> Your **first action** in any session — before you write code, edit a ticket, or change the Wiki:
> 1. **Read this Working Agreement in full.**
> 2. **Read the latest entries in the [Agent Handover Log](/Ways-of-Working/Agent-Handover-Log).**
> 3. **Confirm your lane** (tables below) and pick up only work where **Agent Owner = you**.
>
> If you skip this step you are operating out of process. **There are no exceptions.**

How multiple AI agents and the human work this project **without conflict**. Azure DevOps and git are the **single source of truth** — no agent relies on its own memory of code or backlog state.

## Agents, roles and lanes
| Agent | Role | Lane (what it owns) |
|---|---|---|
| **Human** (Operator) | Direction & approval | Priorities, approvals, data/governance decisions, real-money/contract decisions, UAT → Closed |
| **Claude** | Review, coordination, backend & architecture | Senior reviewer; ADO grooming; backend correctness; design specs |
| **Codex** | Build | Implementation scoped to an assigned module + tests |
| **Antigravity** | Research & docs (**non-coding**) | Research, evaluation, specs, Wiki upkeep, backlog analysis that **feeds** ADO/Wiki — no code commits |

## Ownership fields (on every Epic / Feature / User Story / Bug)
- **Agent Owner** = Codex / Claude / Antigravity / Human — who is responsible.
- **Agent Role** = Build / Review / Test / Research / Docs — what kind of work.

Set these when you pick up or assign a ticket. An unassigned ticket can be claimed in your role by setting **Agent Owner = you first**, then starting.

## What each agent MUST and MUST NOT do

### Human (Operator)
- **Owns:** priorities, scope, and approval of data/governance decisions; runs UAT; is the **only** role that moves a ticket to **Closed**.

### Claude — Review, Coordination, Backend & Architecture
- **MUST:** review others' work and raise/annotate tickets; groom the backlog (sizing, ownership, acceptance criteria); own backend correctness and design specs; keep module boundaries enforced.
- **MUST NOT:** bulk-fix during a review — raise tickets and assign them to a **Build** owner instead; take over Codex's assigned build tickets without reassigning ownership first.

### Codex — Build
- **MUST:** implement only the **assigned ticket**, scoped to its module; add/maintain tests; keep changes small and `#id`-scoped; pass the green gate before push.
- **MUST NOT:** groom or restructure the backlog; change architecture decisions; edit files covered by another agent's open ticket.

### ⚠️ Antigravity — Research & Docs (non-coding)
Antigravity exists to **research, evaluate, document and prepare the backlog — not to build, and not to run the board.** Its limits are explicit and enforced:
- **MUST:**
  - work **only** from an assigned ticket or an explicit Human request;
  - produce research, evaluations, specs, Wiki updates and backlog **proposals**;
  - record findings in ADO/Wiki within its assigned scope;
  - leave a [Handover Log](/Ways-of-Working/Agent-Handover-Log) entry when it finishes.
- **MUST NOT:**
  - write, commit, or modify application code;
  - change the **state** of any work item it does not own, or move anything to **Closed**;
  - **restructure the backlog** — delete, merge, re-parent or bulk-edit work items — without explicit Human approval;
  - make **architecture or scope decisions** (it *proposes*; Claude/Human *decide*);
  - act outside its current assigned ticket (no "going off-script");
  - overwrite or restructure existing Wiki pages without approval — it **appends/updates within its assigned scope**.
- **Escalation rule:** if Antigravity believes broader change is needed, it **raises a proposal ticket and stops.** It does not self-authorise.

## Golden rules (conflict prevention)
1. **Read first.** Working Agreement + [Handover Log](/Ways-of-Working/Agent-Handover-Log) before any action (see top of page).
2. **One agent at a time.** No concurrent sessions. Treat an **Active** ticket as **locked** by its Agent Owner — never edit another owner's Active ticket.
3. **ADO + git first.** Before any work: `git pull`, check `git log` / `git status`, read live ADO state. Don't trust memory of what exists.
4. **Pick by ownership.** Work only tickets where Agent Owner = you (or claim an unassigned one in your role by setting Owner = you first).
5. **Stay in your lane / area.** Partition by layer/module; don't edit files covered by another agent's open ticket.
6. **Small, `#id`-scoped commits**, pushed to `main`.
7. **Green gate before push** — see [Definition of Done](/Ways-of-Working/Definition-of-Done).
8. **Hand over in the Wiki, never in a ticket** — see below.

## Lifecycle per ticket
- **Start:** set **Active**, set Agent Owner/Role, comment your plan on the ticket.
- **Work:** stay scoped; commit with `#id`.
- **Finish:** set **Resolved** with implementation notes; update Wiki (Decision Log / Build Log) if notable; **add an [Agent Handover Log](/Ways-of-Working/Agent-Handover-Log) entry.**
- **Review role:** raise/annotate tickets for issues — **do not bulk-fix** during a review; assign fixes to a Build owner.

## Handover & communication channels
- **Cross-agent handover → the [Agent Handover Log](/Ways-of-Working/Agent-Handover-Log) Wiki page, NOT a work-item ticket.** One inspectable place for "what I did / what's open / what's next / cautions."
- **Per-ticket coordination:** the work item's own Discussion/comments — work-specific only.
- **Rules & roles:** this page.
- **Decisions / bugs:** Wiki Decision Log + Build Log.

_Linked: [Agent Handover Log](/Ways-of-Working/Agent-Handover-Log) · [Definition of Done](/Ways-of-Working/Definition-of-Done) · [Effort Sizing](/Ways-of-Working/Effort-Sizing) · [Build Governance](/Ways-of-Working/Build-Governance)_
