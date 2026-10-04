# Decision register and open questions

> **Human clarification after the conversational trial:** retain entirely local planning. The proposed OpenAI-hosted comparison was rejected and withdrawn; no hosted inference was performed. The failed local configurations do not establish local infeasibility. Continue with conversation-state correctness and bounded local question planning before further model selection. See [checkpoint and recovery audit](13-conversation-checkpoint.md).

**Owner: Human product/knowledge owner. Last updated: 20 September 2026.** User requirements are established constraints. The Human accepted G0 in the follow-up conversation: “I am happy with the design agreement.” This approves the documented isolated synthetic E1 scope. The Human subsequently selected Voice B; acoustic, publication and participant gates remain pending; backlog creation alone never grants approval.

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

## Architecture decisions and remaining gates

| ADR | Recommendation | Alternatives and consequence | Status / decision gate |
|---|---|---|---|
| 001 | Separate local service, initially in the same repo with independent dependencies and data | New repo increases release isolation but adds coordination; in-core implementation risks existing dependencies | Accepted / G0 |
| 002 | Browser/headset, one English SME and synthetic process first | Teams/Webex or room audio adds platform/acoustic/participant complexity before core value is proven | Accepted / G0 |
| 003 | Modular ASR → bounded dialogue → checked text → TTS | End-to-end speech may improve flow but makes claim/utterance inspection and cancellation harder to assure | Accepted / G0; benchmark at G1 |
| 004 | Local speech audition with Kokoro reference and one or two challengers | Selecting solely from demos or published latency risks wrong hardware/voice fit | Human selected B / Kokoro bf_isabella at G1; acoustic acceptance pending |
| 005 | Separate live, break and background validation | Synchronous exhaustive review conflicts with measured Atlas review cost; unchecked automatic approval is unacceptable | Accepted / G0 |
| 006 | Durable interview ledger plus Atlas-owned approved-source publication | Direct graph writes can disappear on rebuild; importing entire transcripts exposes unapproved content | Direction accepted / G0; publication evidence pending G3 |
| 007 | Scope/date-aware assertions with explicit unresolved state | Forced single answer would erase legitimate variants and uncertain or conflicting evidence | Accepted / G0 |
| 008 | Participant confirmation distinct from accountable-owner approval | Generic operator identity is acceptable only as a labelled synthetic PoC limitation | PoC boundary accepted / G0; identity gate remains G4 |
| 009 | Raw audio storage off by default; explicit retention and correction policy | Retaining recordings helps re-transcription but increases privacy/storage burden; policy needed before participants | Transient-audio PoC default accepted / G0; participant policy remains G4 |
| 010 | Free account before focused challenges; user control over interruption intensity | Frequent proactive correction can harm recall, comfort and participation | Accepted / G0; behaviour refinement v0.2 awaits evaluation |
| 011 | Open hardware feasibility later; no Echo reflash assumption | Commodity device reuse may be attractive but supported firmware/acoustics are unproven | Proposed / E4 |
| 012 | Follow-up records first, outbound invitations only after explicit permission/integration | Automatic scheduling risks contacting wrong people or overstating authority | Follow-up records accepted / G0; outbound integrations remain E4 |

Each accepted ADR must add approver, date, selected option, reason, affected stories and any re-evaluation trigger. Supersede decisions by a new entry; do not rewrite their history.

## Decisions and remaining inputs

| ID | Current disposition | Next effect |
|---|---|---|
| Q01 | Confirmed by Human: Mac Studio M4 Max, 16-core CPU, 40-core GPU, 64 GB unified memory | G1 verifies host/runtime and measures simultaneous load |
| Q02 | Browser/headset, one English SME accepted with the initial design | No channel decision blocks setup |
| Q03 | Synthetic supplier-activation fixture accepted within G0 defaults; real pilot process/owner remains open | Real owner needed before organisational pilot |
| Q04 | Human selected B / Kokoro bf_isabella; C rejected as American-sounding | Use B by default; headset with built-in microphone confirmed; live acoustic trial pending |
| Q05 | Single operator, synthetic data and transient raw audio are the accepted PoC boundary | Named participant access, retention and authority remain G4 decisions |
| Q06 | G0 accepted by Human on 19 September 2026 in this conversation | Isolated E1 build is authorised; no need to ask for design approval again |
| Q07 | Three local PDFs supplied; selected relevant sections read and synthesised | Edition/extract limitations recorded; further chapters optional |

**Decision provenance:** Human approval applies to the recommendations published in commit `0214161`, followed by the hardware and British English female voice clarifications. Rationale: the Human explicitly accepted the design and supplied the planned target machine. Affected work: #1507, hardware #1508, reading #1512/#1513 and E1 #1515, starting with #1519. G0 permits the isolated synthetic trial; G1/G2 evidence may require revising model choice, scope or targets. G3/G4 remain separate decisions.

This approval does not authorise enterprise data, publication into the accepted corpus, meeting integrations or hardware spending. The [readiness and reading record](10-readiness-and-reading.md) details the permitted next step.

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

- **19 September 2026, follow-up:** Human accepted the published design agreement and confirmed Mac Studio M4 Max, 16-core CPU, 40-core GPU, 64 GB unified memory. G0 is accepted for the documented isolated synthetic E1 trial; no implementation was delivered in this readiness update.
- **19 September 2026, follow-up:** Three reading PDFs supplied in `books/`; selected sections informed conversation policy v0.2. MI is the second edition; Doing Interviews is a partial second-edition export, distinct from the originally recommended titles/editions.
- **19 September 2026, follow-up:** Human selected a British English female voice preference. Individual voice and runtime configuration remain subject to G1 listening and hardware measurements.

### 19 September 2026 — Human voice choice

The Human listened to the running audition and selected **B**, saying it was best in voice style. C would otherwise be better but was American-sounding. Record B (`bf_isabella`, Kokoro model v1.0 fp32, speed 1.0, en-gb) as the default and C as failing the requested accent. A remains a comparison, not an accepted fallback. Affected story: #1521; implementation/measurements: #1519 and partial #1520. Re-evaluate if fidelity, sustained listening comfort or acoustic performance fails. This decision does not accept human recognition accuracy or full G1 turn-taking. [Measured prototype](11-prototype.md).


### 19 September 2026 — Prototype dialogue model refinement

Under the Human-authorised contextual follow-up iteration (#1524), the local dialogue model changes from installed Qwen 2.5 7B to installed **Qwen 2.5 14B Instruct**. Compact source-ID assessment keeps follow-up preparation around 2.5–3 seconds in the measured final synthetic scenario. The 14B model explored all five deliberately missing details; 7B prematurely treated one gap as covered. This is a reversible prototype selection based on a small development comparison, not a general model ranking or G2 acceptance. Voice B remains unchanged. See [implementation and evidence](12-synthetic-interview.md#contextual-follow-ups--19-september-2026).


## Local conversation v4 runtime — 19 September 2026

Within the Human-authorised local-only #1524 iteration, the synthetic prototype uses the already-installed `gpt-oss:20b` through loopback Ollama: low reasoning for coverage/review, medium for question writing. A 45-second overall planning ceiling and visible deferral bound failure. The forced-topic experiment was rejected. This is a reversible prototype choice for Human trial; final development regressions produced two useful follow-ups and one deferral, not all-pass conversational or latency acceptance. Source-backed state retention and correction invalidation pass deterministic regression checks. No hosted inference, new model download, production claim or G2 acceptance. [Implementation, evidence and remaining work](14-local-conversation-iteration.md).

## Local conversation v5 runtime — 20 September 2026

Following the Human's accepted v4 trial and explicit feedback, #1524 keeps `gpt-oss:20b` local and changes question writing from medium to low reasoning. Narrow deterministic observations protect explicitly completed supplier outcomes and decision owners from being reopened when model extraction misses them. The independent low-reasoning review, exact source checks, one repair and 45-second ceiling remain. Prepared Voice B thinking cues and an animated status fill the measured local planning interval without adding inference. Three final seeded scenarios completed in 6.767–7.649 seconds; this is development evidence, not G2 acceptance. With explicit Human authorisation, the existing ADO `GITHUB_PAT` secret was rotated from the working repository credential; build 677 passed the GitHub mirror without widening permissions. [Implementation and evidence](15-thinking-and-comprehension-iteration.md).

After the Human accepted v5 but challenged its robotic filler and remaining delay, #1524 moves the live path to resident local `qwen3.5:35b-a3b` question writing plus focused `qwen2.5:7b-instruct` review. Typed question identity and narrow explicit facts replace the general coverage-model call on every turn. Both models use an 8,192-token context and 30-minute keep-alive. Spoken filler is delayed until 2.2 seconds. Four final warm seeded turns completed in 1.622–1.738 seconds. SQLite remains authoritative; a derived hybrid lexical/vector index will be benchmarked with the real evidence adapter, with LanceDB as the first embedded candidate and Qdrant retained for later server scale. This reversible local candidate remains subject to long-session and Human conversational acceptance. [Architecture and evidence](17-low-latency-conversation-architecture.md).


## Accepted review direction — 20 September 2026

The Human explicitly requested adoption of Claude's independent review and the next iteration. ADR-013 (separate speech and claim validation), ADR-014 (talker/thinker lanes), ADR-015 (duplex session), ADR-016 (recap confirmation) and ADR-017 (Atlas-derived agenda) are accepted directions; each requires implementation evidence before being marked delivered. The speech grammar must constrain assertions, not merely check named entities. S114 instrumentation is first, then S109 transport. S106/#1524 is resolved on v5/v6 delivery with remaining intent assigned to S112/S115/S120/S121. Human G1.5 remains unaccepted. [Plan and exact timing definitions](19-conversational-core-delivery.md).

## 24 September 2026 — Tiberius and isolated product-knowledge workspace

The Human named the assistant Tiberius (Tibi), accepted the direction towards an OpsAtlas sales companion, and authorised iterations 1 and 2: separate clean runtime data plus initial grounded product recall. They required documentation in ADO. Existing Atlas data must remain intact. Chatterbox remains selected. This authorises internal non-confidential product rehearsal, not wake-word background listening, customer meetings, automatic claim promotion or a completed G1.5 gate. Product records are prepared for explicit local operator review; commercial commitments need separate evidence and approval. Dan's future contributions should retain attribution and surface disagreement for adjudication. See delivery #1670–#1672 and the sales-workspace runbook.

## 2026-09-24 — Tiberius interview publication boundary

Voice turns remain provisional. Server-bound contributor provenance, wording confirmation, relationship disposition and factual approval are separate steps. Corrections withdraw old sources; uncertain/disputed statements do not answer. Same-topic overlap is a review aid, not an automatic contradiction verdict. Existing local Chatterbox/ASR is retained; no cloud planner. See [iteration 3](32-tiberius-product-interviews.md).
