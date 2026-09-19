# Decision register and open questions

**Owner: Human product/knowledge owner. Last updated: 19 September 2026.** User requirements are established constraints. Recommendations remain Proposed until a dated Human decision is recorded; creating backlog items is not design approval.

## Established requirements

| ID | Status | Decision / origin |
|---|---|---|
| C01 | Established by user | Research, structured wiki, decisions and backlog before development |
| C02 | Established by user | Standalone service integrated into Atlas as an additional page |
| C03 | Established by user | Local inference and speech; no external voice/LLM API requirement |
| C04 | Established by user | Preserve working Atlas; consider additive ontology/core changes only where justified |
| C05 | Established by user | Support staged knowledge capture, challenge, human adjudication and later enrichment |
| C06 | Established by user | Natural, respectful interaction that benefits the contributor |
| C07 | Established by user | No new ADO UAT test cases; retain delivery traceability and source control |
| C08 | Established by user | Meeting companion, desk device and projection belong to later vision |

## Proposed architecture decisions

| ADR | Recommendation | Alternatives and consequence | Status / decision gate |
|---|---|---|---|
| 001 | Separate local service, initially in the same repo with independent dependencies and data | New repo increases release isolation but adds coordination; in-core implementation risks existing dependencies | Proposed / G0 |
| 002 | Browser/headset, one English SME and synthetic process first | Teams/Webex or room audio adds platform/acoustic/participant complexity before core value is proven | Proposed / G0 |
| 003 | Modular ASR → bounded dialogue → checked text → TTS | End-to-end speech may improve flow but makes claim/utterance inspection and cancellation harder to assure | Proposed / G0, benchmark at G1 |
| 004 | Local speech audition with Kokoro reference and one or two challengers | Selecting solely from demos or published latency risks wrong hardware/voice fit | Proposed / G1 |
| 005 | Separate live, break and background validation | Synchronous exhaustive review conflicts with measured Atlas review cost; unchecked automatic approval is unacceptable | Proposed / G0 |
| 006 | Durable interview ledger plus Atlas-owned approved-source publication | Direct graph writes can disappear on rebuild; importing entire transcripts exposes unapproved content | Proposed / G0/G3 |
| 007 | Scope/date-aware assertions with explicit unresolved state | Forced single answer would erase legitimate variants and uncertain or conflicting evidence | Proposed / G0 |
| 008 | Participant confirmation distinct from accountable-owner approval | Generic operator identity is acceptable only as a labelled synthetic PoC limitation | Proposed / G0/G4 |
| 009 | Raw audio storage off by default; explicit retention and correction policy | Retaining recordings helps re-transcription but increases privacy/storage burden; policy needed before participants | Proposed / G0/G4 |
| 010 | Free account before focused challenges; user control over interruption intensity | Frequent proactive correction can harm recall, comfort and participation | Proposed / G0/G2 |
| 011 | Open hardware feasibility later; no Echo reflash assumption | Commodity device reuse may be attractive but supported firmware/acoustics are unproven | Proposed / E4 |
| 012 | Follow-up records first, outbound invitations only after explicit permission/integration | Automatic scheduling risks contacting wrong people or overstating authority | Proposed / G0/E4 |

Each accepted ADR must add approver, date, selected option, reason, affected stories and any re-evaluation trigger. Supersede decisions by a new entry; do not rewrite their history.

## Questions that affect the next step

| ID | Needed from Human | Proposed assumption while unanswered | Blocks |
|---|---|---|---|
| Q01 | Machine model, RAM, GPU and whether a separate local server is available | No hardware performance guarantee or purchase; shortlist remains conditional | G1 setup/selection |
| Q02 | First channel: browser/headset, Teams/Webex, or in-room group | Browser/headset, one English SME | G0 scope agreement |
| Q03 | Pilot process and accountable process owner | Synthetic supplier-activation process from an isolated Atlas fixture | G0 scope; real pilot later |
| Q04 | Preferred voice/accent, warmth/humour and interruption style | Neutral professional English; optional light warmth; no voice cloning | G1 audition |
| Q05 | Approver authority, who may see drafts and what retention is appropriate | Single operator, synthetic process; no new participant study or confidential input | G0 data boundary; G4 real pilot |
| Q06 | Agreement to ADRs 001–003, 005–010 and E1 staged-output scope | All remain Proposed; implementation stays New | G0 permission to build |
| Q07 | Optional Perlego availability / selected reading notes | Public sources suffice for initial decision | Does not block G0 |

G0 may approve only the isolated synthetic E1 trial, with G1 voice selection delegated to a listening session. It need not authorise enterprise data, publication into the accepted corpus, meeting integrations or hardware spending.

## Risk register

| Risk | Impact / mitigation | Owner / evidence |
|---|---|---|
| False certainty or misplaced challenge | Qualify discrepancies; check scope and transcript; preserve sources on both sides | Codex / labelled precision and recall, Human review |
| Valid variants collapsed into one rule | Capture conditions, dates, policy vs practice; explicit unresolved state | Knowledge owner / variant holdout |
| Knowledge lost on graph rebuild | Durable source publication and replay test; prohibit direct graph writes | Codex / G3 rebuild evidence |
| Interview service degrades Atlas | Separate runtimes, one-session cap, pause deep jobs, load benchmark | Codex / G3 resource evidence |
| Voice sounds good but changes meaning | Pronunciation/number/negation checks, short checked clauses | Codex + Human / G1 listening and fidelity |
| Participant feels assessed or trapped | Contributor controls, corrections, honest policy, no personal ranking | Human / G2/G4 feedback |
| Identifiable audio crosses old academic boundary | Real-participant/data approval gate and minimised retention | Human / reviewed participant/data plan |
| Stale sources or forged approval | Hash/revision checks, real authority at publication, revalidation on change | Codex / G3/G4 negative tests |
| Review queue never closes | Coverage counts, explicit owner, due-date agreement and pending state | Human / review backlog age |
| Hardware/model incompatibility | Isolated environments and small comparative spike before selection | Codex / G1 manifest and measurements |
| Vendor/platform dependency reintroduced | Local-only runtime gate; separately decide Teams/Webex transport | Human + Codex / egress evidence |
| Historical docs misread as current state | Dated baseline audit and current pointers; preserve past records | Codex / E0 publication |

## Dated history

- **19 September 2026:** User supplied the interviewer vision and authorised research, ADO wiki/backlog creation and repository documentation before build agreement.
- **19 September 2026:** Original root `.env` PAT was rejected as expired. User confirmed another `.env` had been updated, corrected this file, and a retry succeeded. Only the stale `ADO_PROJECT_NAME` setting was corrected to the verified project name; credentials are never recorded here.
- **19 September 2026:** User supplied final DT603 Parts A and B. These supersede earlier DT602 context for the delivered-scope assessment; neither paper grants new operational permissions.
- **19 September 2026:** Authenticated Git fetch confirmed `c7e6ff7` locally and remotely. Live ADO audit found 823 items and 53 wiki pages before this initiative. Current offline baseline: 450 backend tests and Ruff passed.
- **19 September 2026:** Discovery epic and research records created. This pack proposes the service and gates; no Human acceptance of the proposed architecture or implementation start has yet been recorded.
