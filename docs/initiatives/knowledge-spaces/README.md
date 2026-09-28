# Knowledge spaces: the product guide and organisations' data, side by side

**Status:** decided by the Human on 28 September 2026 (see Decisions). Phase 1 is in progress.

## What the Human asked for

- **The OpsAtlas Product Guide.** OpsAtlas's own knowledge (what it is, how it is built, what it can do, how it helps
  a company, how to use it) becomes a product guide. Tibi uses it as a sales assistant, and users can ask it how to
  use OpsAtlas.
- **Organisations' data.** OpsAtlas can also hold an organisation's own business data, so that the product does its
  real job for that organisation: answers, process maps and flows, the Enterprise Activity Model and analytics.
  This must work for Organisation A, then B, C, D and more.
- **Separate but together.** The two are separate, but they belong in the same workflow, ideally managed in one
  place, as today's Governance Review is.
- **Tibi knows where to look.** A question about OpsAtlas is answered from the product guide. "How should
  Organisation A set up a supplier?" is answered from Organisation A's sources only.
- **Users and access.** Today there is one administrator (the Human). Later, a user may see only Organisation C's
  data, plus the product guide, and never Organisation A or B.

## The answer in one paragraph

Add one concept, a **knowledge space**: a governed boundary that every document, fact, conversation and log belongs
to.
- There is one space for the **OpsAtlas Product Guide**, and one for **each organisation**.
- **Folders stay what they are today:** a way to organise *inside* a space.
- **Enforcement is in the storage.** Each space keeps its data in its own partition, and every request, including
  Tibi's, is scoped to the spaces its user may see.
- **The Governance Review page stays one page.** Spaces are its top level, so it looks like the folders the Human
  described.
- **Tibi does not guess across boundaries.** A conversation is bound to the product guide plus, at most, one active
  organisation. Tibi routes each question between those two, and nothing else exists for it.

## Why folders alone are not enough as the boundary

Putting everything under two folders ("OpsAtlas Product Guide" and "Organisation A data") is the simplest start, and it
is the right *picture*. As the *boundary*, it fails in four ways:

| Risk | Why it matters |
|---|---|
| Folders move | Library drag and drop was built to move documents freely. One drag would put Organisation A's document in Organisation B's folder, and into B's answers. |
| Filters get forgotten | Every search, answer, process map, EAM view, analytics chart, governance review and cache would need a "which folder tree" filter. One missed filter leaks data between organisations. |
| Access control | Permissions on nested, movable folders are hard to get right and hard to audit. |
| Deleting an organisation | Exporting or deleting everything belonging to Organisation B has to be complete. A folder tree does not guarantee that. |

## Options considered

| | A. Folders as the boundary | B. One store, with a space label on every item | C. One partition per space (recommended) |
|---|---|---|---|
| Isolation | Weak: depends on folder filters | Depends on every query filtering the label | By construction: a request can only open its spaces' partitions |
| Effort | Smallest | Medium: every query changes | Medium to large: a space context in the API, but today's store code is reused as it is |
| Scaling to B, C, D… | Poor | Good | Good: a new organisation is a new partition |
| Export or delete an organisation | Hard to prove complete | Needs a sweep of every store | Remove or archive one directory |
| Governance, EAM, analytics | Mixed data unless filtered | Filtered | Naturally per organisation |
| Looks in the UI | Folders | Folders | Folders: spaces appear as top-level "folders" with a lock |

**Recommendation: C.** It gives the Human's picture (one page, folders) on top of a boundary that cannot be dragged
across or filtered wrong. The current stores (source register, sections, embeddings, content, ontology, process
registry, governance) already live in one data directory. Each space gets its own copy of that layout, so most code
works unchanged inside a space.

## The model

```
Spaces registry (spaces.json)            Users and access (users.db)
 ├─ product-guide   OpsAtlas Product Guide   everyone signed in: read and ask; product owners: edit and approve
 ├─ sales-playbook  OpsAtlas Sales Playbook  internal sales and admin only (proposed split: see decision 2)
 ├─ org-a           Organisation A           its members only
 ├─ org-b           Organisation B           its members only
 └─ …
System settings (not a space): Tibi's conversation style and persona, models, services. Admin only.

.runtime/opsatlas-sales/spaces/<space>/   one partition per space, today's layout inside it:
   sources/  sections/  embeddings  content/ (drafts, versions, comments, library folders)
   ontology.db  process_registry.json  governance/  analytics_events  logs/ (activity, conversations)
```

- **A document belongs to exactly one space.**
  - Folders organise it within that space. Drag and drop works inside a space and never across one.
  - Moving a document to another space is a separate, audited **Transfer** by an administrator. The document leaves
    one partition and arrives in the other as a new, unapproved document.
- **Each organisation space has the full OpsAtlas workflow on its own data:**
  - governed sources, content management and statement governance;
  - the process registry and process maps, the Enterprise Activity Model, and analytics.
  - These are the Classic capabilities, now run per organisation.
- **The product guide keeps what Tibi uses today:** curated product records, spoken answers and the product ontology.
- **Governance never compares across spaces.**
  - The statement review runs inside one space: Organisation A's statements are never judged against Organisation B's.
  - An organisation's process documents are never judged against the product guide.

## How Tibi, the Digital SME and Written Query know where to look

**1. The conversation is scoped before it starts.**
- The user signs in, and the control panel has an **active organisation** selector.
- A user with one organisation has it fixed. An administrator chooses one, or none: product only.
- The conversation is bound to the product guide, plus the sales playbook for internal users, plus that one
  organisation.
- The Tibi service gets a short-lived token that allows only those spaces. The core refuses anything else, so a
  mistake in Tibi cannot reach another organisation.

**2. Each question is routed between the spaces the conversation allows.**

| Question | Signals | Answered from |
|---|---|---|
| "How do I approve a document in OpsAtlas?" | Names OpsAtlas or one of its features; the product ontology matches | Product guide |
| "How should we set up a new supplier?" | Business process terms; the organisation's process ontology matches (suppliers, articles, roles, systems) | Organisation A |
| "How would OpsAtlas map our supplier process?" | Both | Both, each passage labelled with its space |
| "What does Organisation B do?" | Another space's name | Neither: "I can only use Organisation A's knowledge and the OpsAtlas guide." |
| Unclear | Both weak, or both strong and conflicting | One short question: "In OpsAtlas, or in Organisation A's process?" |

Tibi already routes between conversation and product evidence. This adds a second decision, which space's
evidence, built from the same signals. Retrieval runs in each allowed space and scores break ties.

**3. The organisation's evidence goes through the same checks.**
- Organisations won't hand-write records as the product guide has. Tibi answers from the organisation's
  *approved sections* and its process ontology facts.
- Those answers pass the same sentence gate and delivery authorisation as product answers (audit F02, F03). The
  evidence digest is per space.
- Answers cite the space and the source, for example "Organisation A · Supplier setup pack 1, section 3".

**4. Logs follow the space.** Conversation logs, review marks, activity and analytics are kept per space. An
administrator's overview shows counts across spaces, not content.

## Users and access

| Role | Can |
|---|---|
| Platform administrator (the Human) | Everything: all spaces, users, system settings, transfers. The current workspace key stays as the break-glass admin sign-in. |
| Product owner | Edit and approve the product guide (and the sales playbook) |
| Sales | Read and ask the product guide and the sales playbook; use rehearsal mode |
| Space owner | For one organisation: manage its members, approve its sources, run its governance |
| Space editor | For one organisation: upload, edit, comment and propose; not approve |
| Space viewer | For one organisation: ask Tibi, the Digital SME and Written Query; view process maps, the EAM and analytics |
| Every signed-in user | Read and ask the product guide |

**How it is enforced:**
- **Sign-in.** Each person has their own local account, with a hashed password and expiring sessions. SSO comes
  later if needed.
- **Every request.** Each request resolves who is asking and which space it is for, and the server checks the role.
  Only then does it open that space's partition.
- **Hiding is not the control.** The interface hides what a user can't use, as a convenience only; the server check
  is what protects the data.
- **Audit.** The activity log records who opened which space.

## Real business data: a decision to make first

This project's working rule has been **synthetic or anonymised data only**, and the audit's point is that controls
must exist before they are relied on. Proposal:

1. **Organisation A is synthetic.** Import a copy of OpsAtlas Classic's 21 anonymised learning packs (supplier setup,
   article setup, master data, integration, packaging and more), with their 21-process registry. They are exactly
   the kind of business data this design is for, and nothing leaves the Mac.
2. **Real client data comes only after users and access are live.** It also needs the isolation tests passing and
   the Human's explicit approval of how it is handled:
   - processing stays local (Ollama on this Mac), and no outside model is used;
   - per-organisation export and deletion;
   - retention.

## Plan of action

| Phase | What is delivered | Size | Proves it |
|---|---|---|---|
| **1. Spaces and partitions** | The spaces registry. One partition per space. A space context on every API route. Today's 42 sources migrated into the product guide (and the sales playbook, if split). Governance Review shows spaces as the top level, with folders inside. Drag and drop stays inside a space. Transfer is admin only. | Large | Everything works exactly as today, inside the product guide. Migration on a copy of the live workspace first (the audit lesson). |
| **2. Organisation spaces** | Create, rename and archive an organisation. Upload, ingest, govern, content-manage, process registry and maps, EAM and analytics per organisation. Organisation A imported from the Classic learning packs. | Large | The EAM and process maps for Organisation A. Nothing of A appears in the product guide, and the reverse. |
| **3. Space-aware answers** | Tibi, the Digital SME and Written Query scoped to the product guide plus the active organisation. The per-question route between them. The organisation evidence path through the same gate and authorisation. Space-labelled citations. Per-space logs. Scoped tokens for the Tibi service. | Large | A routing suite (product, organisation, both, unclear, other organisation). A leak suite: planted phrases in Organisation B never surface from Organisation A's conversations, answers, maps, EAM, analytics or logs. Latency replay within budget. |
| **4. Users and access** | Accounts, roles and memberships. Sign-in per person, with the key kept for break-glass. The server-side check on every request. The admin page for users and spaces. Access audit. | Large | Role tests on every route. The leak suite repeated for a Space viewer of Organisation C. |
| **5. Hardening, before any real data** | Per-organisation export and deletion. Backup of each partition. The isolation and leak suites in CI. A security review of the boundary. | Medium | The Human's approval to load real data. |

Phases 1 and 2 give the separation the Human asked for, with the Human as the only user. Phase 3 makes Tibi use it.
Phase 4 opens it to other people. Phase 5 is the gate for real client data.

## Decisions (the Human, 28 September 2026)

| # | Question | Decision |
|---|---|---|
| 1 | Spaces as the boundary, shown as top-level folders in one Governance Review | **Yes** |
| 2 | An internal Sales Playbook apart from the Product Guide, and Tibi's conversation style in system settings | **Yes** |
| 3 | Organisation A from the Classic learning packs | **No.** The Human loads brand-new information; organisation spaces start empty. |
| 4 | The administrator's view | **Across organisations for now.** The administrator may choose *All organisations*. Tibi then answers from any organisation, labelling each passage with its organisation. Other users are always limited to their own organisation. |
| 5 | No real client data before phase 5 | **Agreed** |

**Phase 5, the gate before real client data:**
- per-organisation export, and deletion that is proven complete;
- per-organisation backup, with a tested restore;
- the leak and access suites in CI;
- a security review of the boundary (sign-in, the per-request check, Tibi's scoped token, logs);
- written handling rules (retention, and local processing only);
- then the Human's approval.

## Phase 1 in detail

| Story | What it delivers |
|---|---|
| KS S1 Spaces and partitions | `spaces.json` (id, kind, name, status). One partition per space under `spaces/<id>/core`. Each space's core is built from today's `create_app` on its own register, with one shared sign-in. |
| KS S2 One space per request | Every core API request is served by exactly one space's core, chosen by the `X-OpsAtlas-Space` header. A missing header means the Product Guide, which every user may read; an unknown or forbidden space is refused. Sign-in, activity, services, conversation logs, the Tibi gateway and space administration stay outside spaces. |
| KS S3 The OpsAtlas family | The Product Guide, Sales Playbook and System partitions. Tibi's evidence API aggregates the family, and records may cite evidence anywhere in it: a guide record rests on DT603 paper sections that now sit in the playbook. The product ontology and the statement review cover the family, because they are one owner's claims about one product. Each record shows its space. |
| KS S4 Migration | Today's workspace is split per the map below. Approvals, versions, comments, review history and folders are preserved. The migration is previewed on a copy first, and the old directory is kept until the Human confirms. |
| KS S5 Governance Review by space | Spaces are the top level, with folders inside. Drag and drop works inside a space. An administrator's **Transfer** moves a document to another space: it arrives unapproved, and the move is audited. |
| KS S6 The control panel follows the space | An active-space selector. Knowledge Sources, Written Query, Citation Check, the Process Registry, the EAM, Analytics and documents follow it. Document links carry their space. |

**Migration map** (the Human's decision 2):

| Space | Documents |
|---|---|
| Product Guide | The product records in *What OpsAtlas is* (except Commercial position), *How it works*, *Governance and trust*, and *Deployment and roadmap* (except Path to production), plus *Tibi, the voice companion* |
| Sales Playbook | Commercial position, Path to production, the three owner notes, and the twelve DT603 paper sections (still evidence for guide records) |
| System | Tibi's six conversation-style records |

Stakeholder validation and Real deployment stay in the guide, because they were not in the Human's list. **Transfer**
moves them later if wanted.
