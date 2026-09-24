# Linked delivery backlog

**Follow-up:** G0 is now accepted, hardware is confirmed and the voice preference is British English female. The [readiness record](10-readiness-and-reading.md) supersedes unanswered-decision wording from the original publication below. Implementation remains unstarted at this readiness checkpoint but is authorised for E1.

Published 19 September 2026: **5 Epics, 12 Features, 28 User Stories and 7 Tasks**. Every item has a stable plan key, named owner, estimate, scope, acceptance criteria and gate. ADO contains parent/child and predecessor/successor links. Research delivery is eligible for Resolved after verification; Human acceptance is still required. All implementation and future investigation remain New.

The [machine-readable planning manifest](backlog.json) includes the initial items and the accepted conversational-core amendments. [ADO identifiers](ado-links.json) map that manifest to published records. Live workflow status belongs to ADO; this plan does not automatically accept gates or close work.

Story points are relative Fibonacci sizes; Feature/Epic effort rolls up child story points. Task estimates are hours and are not added to those rollups. Estimates are provisional, not a schedule or authority to start. No ADO Test Case, Test Suite or Test Plan was created.

## Route to the first demonstration

1. Review this pack and record G0 in [SME-S005 / #1507](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1507); hardware and scope tasks below support the decision.
2. Run the isolated speech/turn audition in [SME-F10 / #1516](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1516); select a voice from measured local evidence.
3. Build the staged interview in [SME-E1 / #1515](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1515); demonstrate natural interaction, traceability and a reviewable draft.
4. Prove owner adjudication and durable Atlas publication in [SME-E2 / #1527](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1527). Only then describe the loop as knowledge enrichment.
5. Complete participant, identity, data and operational gates in [SME-E3 / #1538](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1538) before a real organisational pilot.
6. Consider meeting and desk-device work under [SME-E4 / #1545](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1545) after a separate decision.

Dependencies are evidence requirements. Completing a predecessor never grants Human approval by itself. The G2-to-G3 and G3-to-G4 transitions must have dated Human acceptance in the decision register.

## Conversational-core amendment — accepted 20 September 2026

The [accepted review](16-independent-review.md) adds F13–F16 and S109–S123, already published as #1572–#1590. The machine-readable manifest now contains all 71 items, with their existing ADO identities. The older tables below preserve the original backlog; their superseded scopes are: S102 recognition quality, S103 interim Voice B (selection in S118), S105 fixture foundation (Atlas in S120), S106 delivered v5/v6 planning only. S107 waits on S123; S108 depends on S119.

Follow the [revised delivery order](19-conversational-core-delivery.md), starting with S114 measurement and then S109 transport. F13–F15 take capacity priority over E2. The G1.5 decision remains Human-owned, and no new Test Plans/Suites/Cases are authorised or needed.

## SME E0 — Research, Atlas baseline and architecture agreement

[SME-E0 / #1500](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1500) — Establish current evidence, propose the service and obtain agreement before development.

| Item | Scope | Owner / role | Size | Gate | Predecessors |
|---|---|---|---|---|---|
| [SME-F00 / #1501](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1501) · Feature | Evidence and reviewable design pack | Codex / Research | 16 effort | G0 | — |
| [SME-S001 / #1502](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1502) · User Story | Reconcile the live Atlas baseline and delivery record | Codex / Research | 3 points | G0 | — |
| [SME-T007 / #1514](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1514) · Task | Reconcile rollback and missing historical roadmap references | Codex / Research | 1 h | Maintenance | — |
| [SME-S002 / #1504](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1504) · User Story | Research local voice, interview methods and future channels | Codex / Research | 5 points | G0 | [SME-S001 / #1502](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1502) |
| [SME-S003 / #1505](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1505) · User Story | Specify service boundaries, claim lifecycle and participant experience | Codex / Docs | 5 points | G0 | [SME-S001 / #1502](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1502), [SME-S002 / #1504](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1504) |
| [SME-S004 / #1506](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1506) · User Story | Publish the wiki, backlog and current baseline pointers | Codex / Docs | 3 points | G0 | [SME-S003 / #1505](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1505) |
| [SME-F01 / #1503](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1503) · Feature | Human scope, hardware and data decisions | Human / Review | 2 effort | G0 | — |
| [SME-S005 / #1507](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1507) · User Story | Agree the isolated proof-of-concept scope and architecture | Human / Review | 2 points | G0 | [SME-S004 / #1506](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1506) |
| [SME-T001 / #1508](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1508) · Task | Confirm host hardware and available local acceleration | Human / Review | 0.5 h | G0 | — |
| [SME-T002 / #1509](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1509) · Task | Select first channel, process and accountable owner | Human / Review | 0.5 h | G0 | — |
| [SME-T003 / #1510](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1510) · Task | Set participant access, recording and retention expectations | Human / Review | 1 h | G0 | — |
| [SME-T004 / #1511](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1511) · Task | Choose voice style and review audition preferences | Human / Review | 0.5 h | G0 | — |
| [SME-T005 / #1512](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1512) · Task | Optionally provide targeted Perlego reading notes | Human / Review | 1 h | Optional | — |
| [SME-T006 / #1513](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1513) · Task | Incorporate optional interview-method reading | Codex / Research | 2 h | Optional | [SME-T005 / #1512](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1512) |

## SME E1 — Local voice interview with a reviewable draft

[SME-E1 / #1515](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1515) — After G0, demonstrate one synthetic SME session with read-only Atlas evidence and staged output.

| Item | Scope | Owner / role | Size | Gate | Predecessors |
|---|---|---|---|---|---|
| [SME-F10 / #1516](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1516) · Feature | Local speech and turn-control audition | Codex / Build | 10 effort | G1 | — |
| [SME-S101 / #1519](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1519) · User Story | Benchmark offline model configurations on the target host | Codex / Build | 3 points | G1 | [SME-S005 / #1507](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1507), [SME-T001 / #1508](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1508) |
| [SME-S102 / #1520](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1520) · User Story | Prove speech recognition, endpointing and cancellation | Codex / Build | 5 points | G1 | [SME-S101 / #1519](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1519) |
| [SME-S103 / #1521](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1521) · User Story | Select a voice through a blinded listening comparison | Human / Review | 2 points | G1 | [SME-S101 / #1519](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1519), [SME-T004 / #1511](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1511) |
| [SME-F11 / #1517](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1517) · Feature | Evidence-aware session and capture service | Codex / Build | 15 effort | G2 | — |
| [SME-S104 / #1522](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1522) · User Story | Implement isolated sessions and a revisioned interview ledger | Codex / Build | 5 points | G2 | [SME-S102 / #1520](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1520), [SME-S103 / #1521](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1521) |
| [SME-S105 / #1523](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1523) · User Story | Supply a bounded approved evidence pack through an Atlas adapter | Codex / Build | 5 points | G2 | [SME-S005 / #1507](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1507), [SME-S104 / #1522](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1522) |
| [SME-S106 / #1524](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1524) · User Story | Implement adaptive questions and bounded live clarification | Codex / Build | 5 points | G2 | [SME-S104 / #1522](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1522), [SME-S105 / #1523](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1523) |
| [SME-F12 / #1518](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1518) · Feature | Atlas interview page and synthetic demonstration | Codex / Build | 8 effort | G2 | — |
| [SME-S107 / #1525](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1525) · User Story | Add the optional Atlas interview page and participant controls | Codex / Build | 5 points | G2 | [SME-S104 / #1522](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1522), [SME-S106 / #1524](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1524) |
| [SME-S108 / #1526](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1526) · User Story | Evaluate the staged interview on held-out synthetic scenarios | Codex / Test | 3 points | G2 | [SME-S107 / #1525](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1525) |

## SME E2 — Human adjudication and durable Atlas enrichment

[SME-E2 / #1527](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1527) — After successful staged capture, complete an approved, reversible knowledge lifecycle.

| Item | Scope | Owner / role | Size | Gate | Predecessors |
|---|---|---|---|---|---|
| [SME-F20 / #1528](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1528) · Feature | Scoped claims and deferred reconciliation | Codex / Build | 13 effort | G3 | — |
| [SME-S201 / #1531](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1531) · User Story | Define scoped assertions, variants and confirmation states | Codex / Build | 3 points | G3 | [SME-S108 / #1526](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1526) |
| [SME-S202 / #1532](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1532) · User Story | Run resumable validation of new and changed claims | Codex / Build | 5 points | G3 | [SME-S201 / #1531](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1531) |
| [SME-S203 / #1533](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1533) · User Story | Provide owner adjudication with evidence from both accounts | Codex / Build | 5 points | G3 | [SME-S202 / #1532](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1532) |
| [SME-F21 / #1529](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1529) · Feature | Governed source publication and rebuild survival | Codex / Build | 13 effort | G3 | — |
| [SME-S204 / #1534](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1534) · User Story | Export a pending process source with durable provenance | Codex / Build | 3 points | G3 | [SME-S203 / #1533](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1533) |
| [SME-S205 / #1535](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1535) · User Story | Implement idempotent Atlas-owned publication | Codex / Build | 5 points | G3 | [SME-S204 / #1534](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1534) |
| [SME-S206 / #1536](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1536) · User Story | Verify rebuild, revocation, supersession and rollback | Codex / Test | 5 points | G3 | [SME-S205 / #1535](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1535) |
| [SME-F22 / #1530](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1530) · Feature | Follow-up ownership and aggregate learning measures | Codex / Build | 3 effort | G3 | — |
| [SME-S207 / #1537](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1537) · User Story | Track bounded follow-ups and knowledge capture outcomes | Codex / Build | 3 points | G3 | [SME-S203 / #1533](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1533) |

## SME E3 — Controlled participant pilot and operational readiness

[SME-E3 / #1538](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1538) — Prepare trustworthy participant access and evaluate value in an approved environment.

| Item | Scope | Owner / role | Size | Gate | Predecessors |
|---|---|---|---|---|---|
| [SME-F30 / #1539](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1539) · Feature | Participant identity and data controls | Codex / Build | 8 effort | G4 | — |
| [SME-S301 / #1541](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1541) · User Story | Implement scoped service and participant authority | Codex / Build | 5 points | G4 | [SME-S206 / #1536](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1536) |
| [SME-S302 / #1542](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1542) · User Story | Approve participant information and implement retention controls | Human / Review | 3 points | G4 | [SME-S005 / #1507](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1507), [SME-S206 / #1536](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1536) |
| [SME-F31 / #1540](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1540) · Feature | Operational assurance and pilot evidence | Codex / Build | 8 effort | G4 | — |
| [SME-S303 / #1543](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1543) · User Story | Prove load isolation, recovery and local-only operation | Codex / Test | 5 points | G4 | [SME-S301 / #1541](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1541), [SME-S302 / #1542](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1542) |
| [SME-S304 / #1544](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1544) · User Story | Run a small approved pilot and decide the next increment | Human / Review | 3 points | G4 | [SME-S303 / #1543](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1543) |

## SME E4 — Future meeting companion and desk-device feasibility

[SME-E4 / #1545](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1545) — Parked vision; investigation only when separately prioritised, no dates or procurement.

| Item | Scope | Owner / role | Size | Gate | Predecessors |
|---|---|---|---|---|---|
| [SME-F40 / #1546](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1546) · Feature | Meeting transport and group facilitation feasibility | Human / Research | 6 effort | Later | — |
| [SME-S401 / #1548](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1548) · User Story | Assess Teams and Webex media integration requirements | Codex / Research | 3 points | Later | [SME-S304 / #1544](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1544) |
| [SME-S402 / #1549](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1549) · User Story | Specify a multi-party companion with request-to-speak control | Codex / Research | 3 points | Later | [SME-S304 / #1544](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1544) |
| [SME-F41 / #1547](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1547) · Feature | Open desk endpoint and optional visual embodiment | Human / Research | 4 effort | Later | — |
| [SME-S403 / #1550](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1550) · User Story | Evaluate an open microphone and status-ring desk device | Codex / Research | 3 points | Later | [SME-S304 / #1544](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1544) |
| [SME-S404 / #1551](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1551) · User Story | Retain avatar and projection as an optional future concept | Human / Review | 1 points | Later | — |

## Human decisions and optional reading

G0 review is [SME-S005 / #1507](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1507). Hardware is [SME-T001 / #1508](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1508); channel/process is [SME-T002 / #1509](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1509); access, authority and retention are [SME-T003 / #1510](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1510); voice preferences are [SME-T004 / #1511](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1511). These decisions can authorise only an isolated synthetic E1 experiment; broader publication and participant work have later gates.

Optional Perlego reading is [SME-T005 / #1512](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1512) and synthesis of supplied notes is [SME-T006 / #1513](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1513). Neither blocks the initial design decision. The titles and publisher links are in [research](03-research.md); public primary sources support the initial proposal without paid access.

Traceability follow-up [SME-T007 / #1514](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1514) records the missing historical Epic #1289 reference and August Ask rollback linkage. Read-only investigation found a direct 404 for #1289 and no matching rollback in the completed-PR query. These references remain unresolved; this task is the maintenance record for Human disposition. Its investigation is complete and awaits Human closure because Tasks have no Resolved state. Do not reinstate rolled-back code or invent a historical ticket disposition.

The project has custom Agent Owner/Role fields on Epics, Features and User Stories. Task ownership is recorded explicitly in its description and Owner tag because those custom fields are not available for Tasks. Tasks have no Resolved state; the Human closes completed Tasks.

## Tiberius sales-domain increment — authorised 24 September 2026

The user authorised an isolated OpsAtlas Sales workspace and initial product recall, with ADO documentation. This additive domain profile does not replace or clear the existing business-process corpus. The manifest now includes 74 mapped items. Broader grounding and conversation gates remain open.

| Item | Delivery and status |
|---|---|
| [SME-F17 / #1670](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1670) | Tiberius sales workspace and product recall · Active |
| [SME-S124 / #1671](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1671) | Separate data, sessions, credentials, labelled Control Panel and restart runbook · Active, implementation tested |
| [SME-S125 / #1672](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1672) | Eight pending product records, hash-bound evidence selection and Chatterbox delivery · Active, owner review and acceptance pending |

[Implementation, evidence and limitations](31-tiberius-sales-workspace.md). #1672 is related to #1587 and #1588, whose broader ontology-agenda and challenge criteria are not completed by this increment. No new ADO test-management artifacts were created. Estimates are provisional scope sizes, not delivery promises.
