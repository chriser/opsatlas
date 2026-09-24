# Knowledge architecture comparison and recommended backlog changes

22 September 2026. Review of *Replicating an Internal / External SME Capability in ChatGPT*, supplied as `SME_Knowledge_Architecture_ChatGPT_Migration.docx`, against the OpsAtlas code, initiative plan and 71 mapped live ADO items. Document recommendations are evaluated as proposals, not instructions to migrate or connect services. No runtime or ADO scope/state changes were made for this review.

## Recommendation

Adopt the document's source routing, lifecycle metadata and permission-aware knowledge interface. Keep the local conversational architecture and Atlas as the durable knowledge platform. Implement the interface first for our interviewer; expose it through MCP later if another consumer needs it. Do not build a second SME knowledge repository alongside Atlas.

The attachment is an architecture and migration proposal, not a trained model specification or measured implementation. It supplies no model weights, voice design, inference configuration, evaluation results or demonstrated latency. It can improve what our interviewer knows and how evidence is selected; it does not resolve natural speech, interruption or comprehension by itself.

## Comparison with our actual position

| Attachment proposal | Our position and evidence | Recommendation and backlog fit |
|---|---|---|
| Separate shared reasoning/routing policy from the corpus (§1, §9) | Architecture already separates service, ledger and Atlas. Routing policy is not yet a reusable, versioned source-selection contract. | Adopt a platform-neutral policy contract under S120/#1587 and S121/#1588. A ChatGPT skill can later describe it, but should not be its only implementation. |
| Distinguish authoritative sources from narrative evidence (§2) | Atlas retrieval filters approved sources; the live interview adapter currently loads a bounded synthetic fixture. Approval alone does not determine relevance, authority or applicability. | Add question-specific routing and source-role metadata to #1587/#1588; richer reconciliation belongs to S202/#1532. |
| Raw transcript plus curated topic records (§3–4) | Revisioned transcript ledger and unpublished draft export exist. Full structured assertion lifecycle and owner adjudication remain planned. | Strong agreement. Extend S201/#1531 and S204/#1534 with topic records linked to exact transcript revisions. Automatic extraction creates candidates, never automatically approved facts. |
| Preserve original PDFs, normalised text and provenance (§5) | Atlas SourceRecord carries version/hash and source approval. Interview evidence carries source hashes and excerpts. Neither alone proves precise PDF-page-to-claim traceability. | Extend evidence/publication contracts in #1587/#1534 with original hash, extraction version and page/section/span locators. Test tables, OCR and changed extraction output. |
| Dedicated knowledge MCP with search/fetch/related tools (§8) | Atlas already has retrieval, ontology, sources and process APIs. No equivalent general authorised interviewer knowledge contract is implemented in the inspected path. | Build a narrow Atlas-owned read interface, then an optional MCP facade. Reuse #1587; separately estimate cross-client packaging instead of hiding it in the interview story. |
| Classification, effective dates, review dates and supersession (§10) | These are substantially anticipated by our claim design, but the current core SourceRecord is intentionally small. Claim dates and source lifecycle are not implemented merely because they appear in the design. | Extend #1531/#1534/#1536. Separate recorded/retrieved time, effective period, source version and review deadline. An overdue review should be visible; it does not automatically prove a claim false. |
| Public/internal source separation and end-user access (§12) | Atlas still has a single-operator PoC auth model. The source sensitivity enum is synthetic/anonymised, not an NDA access-control scheme. | Critical implementation gap. Expand S301/#1541 acceptance for search, fetch, related links, cached packs and derived records. Public-facing SME delivery would be additional scope. |
| Retention by meeting type (§11) | S302/#1542 covers retention, corrections, deletion and backups, but no operational meeting-type policy is delivered. | Add a retention matrix there. Preserve raw evidence subject to approved retention; do not interpret “retain transcripts” as permission to retain audio indefinitely. |
| Evaluate source choice, citations, freshness and leakage (§13) | S119/#1586 focuses on conversation quality; source challenge precision is in #1588 and access controls in #1541. | Add a linked knowledge-quality suite across these stories. Report retrieval, reasoning, speech and security results separately. |
| Live Jira/Confluence/GitHub integrations (§7) | Our development system is ADO; the existing Atlas corpus is a different source estate. | Copy the routing principle, not its vendor list. Add connectors only for an agreed source need. GitHub mirroring does not make GitHub the authoritative source of ADO work-item status. |

## Where our approach is stronger

Our design is more explicit about the creation and approval of new organisational knowledge. It separates participant confirmation from owner approval, binds approval to an exact revision/hash, invalidates derived work after corrections, and requires idempotent publication, revocation, supersession and rebuild survival. The attachment describes promotion but leaves much of that operational contract unspecified. These are design advantages; E2 implementation is still pending.

Some relevant protections already exist: a revisioned SQLite ledger, correction history, a hashed unpublished review packet, synthetic evidence pinning and a draft that explicitly marks factual validation pending and publication disabled. They are foundations, not a completed knowledge-enrichment loop.

The local voice service also has capabilities outside the attachment's scope: streaming audio, cancellation, generation fencing, recognition recovery, separate social memory and selected Chatterbox speech. Our live/deferred/background distinction addresses conversational timing directly. The attachment supplies no comparable acoustic or turn-gap evidence. This does not establish that our human-like conversation goal has been achieved.

Atlas already combines lexical and optional semantic retrieval and has ontology/process representations. Its current retrieval implementation builds the lexical corpus and performs similarity work over eligible sections during a query. That is a concrete scaling issue to benchmark; replacing it with a newly named database is not yet a justified remedy.

## Important changes to the supplied proposal

**Authority depends on the question.** For “what is required?”, use the applicable approved policy. For “what did the deployed system do?”, inspect the deployed version/configuration and relevant execution evidence. For “why?”, use decision records. For “what happens in practice?”, preserve the SME's scoped account. Repository HEAD is not proof of production behaviour; a newly dated recollection is not necessarily more authoritative than an applicable policy. Conflicts remain explicit rather than being resolved by a single global ranking.

**NDA is not just a classification label.** Entitlements may vary by customer, agreement, project, role and purpose. A tool's caller-supplied `classification` filter must never grant access. Authorisation applies before evidence reaches the model and again on fetch, related-source traversal and cached content. Derived records inherit restrictions unless an authorised release process changes them. Separate agents help only if their credentials, tools and caches preserve that separation.

**Curated text must not launder uncertainty.** Every material assertion needs source spans, scope, status and lineage. Multiple documents derived from one meeting are not independent corroboration. Corrections must invalidate affected summaries, embeddings, cached packs and pending review results. Confidential source deletion must also address derived copies and caches under the agreed retention policy.

**Live access and pinned evidence serve different purposes.** Fetch current permitted sources before the session or in background work; pin versions for reproducible comparisons. Refresh or revocation events invalidate affected comparisons. Do not search every live system synchronously before each spoken reply.

## How this fits the three reasoning layers

The proposed design keeps four distinct stores/views rather than one universal memory:

1. Expression state: current turn, playback state, preferences and recent social context. No corpus search and no authority to assert business facts.
2. Working conversation memory: structured claims, unresolved references, answered questions and a bounded permitted evidence pack. Fast local reasoning reads this view. Each entry retains transcript revision and whether it is tentative, confirmed or superseded.
3. Durable interview ledger: recoverable transcript revisions, candidates, corrections and review events. Working memory is a rebuildable view of this history, not an alternative source of truth.
4. Governed Atlas knowledge: approved durable sources and projections. Background research queries this and any explicitly permitted authoritative systems, producing cited clarification candidates for later turns.

This is a recommended integration direction, not the current complete implementation. The social preview currently stores six exchanges and links to a separate process interview; it does not yet provide seamless shared factual reasoning.

The attachment contributes mainly to stores 2 and 4 and the background lane. The 350 ms evidence budget and 1.5-second conversational target remain targets requiring end-to-end measurement. MCP supplies an interface, not a latency optimisation. First bound context, prefetch permitted evidence, retain indexes between queries, invalidate by revision and measure contention on the 64 GB Mac. Consider a persistent vector index only if corpus-scale retrieval measurements show it is needed; retain lexical identifiers and ontology links alongside it.

## Proposed backlog changes and delivery sequence

These are review proposals, not newly created ADO work items or accepted estimates.

| Priority | Existing work | Concrete addition and acceptance evidence |
|---|---|---|
| Next integrated conversation increment | S112/#1579, S115/#1582, S116/#1583 | Join social and interview orchestration with typed working memory. A participant's explicit answer prevents the same premise being asked again; a correction invalidates dependent understanding; small talk never becomes a process claim. Test multiple unrelated processes. |
| Design now; deliver with Atlas grounding | S120/#1587, S121/#1588 | Versioned question-to-source policy and evidence-pack contract. Labelled cases choose policy, deployed implementation, work status or historical rationale appropriately. Missing/forbidden evidence produces uncertainty, not model-memory facts. Record selection reason, source version and retrieval time. |
| Include in grounding evaluation | S119/#1586, S121/#1588 | Add stale/new conflict pairs, version differences, policy-versus-practice divergence, wrong-source temptations and source outages. Score citation support, correct source choice, false challenges and omission separately; report p50/p95 end-to-end audio timing and sample counts under background load. |
| Required before restricted evidence | S301/#1541, S302/#1542, S303/#1543 | Scope reads by authenticated principal; test denied search/fetch/traversal, cross-session cache reuse and revocation during a session. Permission contract should be designed before caches/adapters even though the real-data gate remains later. |
| Governed enrichment increment | S201–S206/#1531–#1536 | Durable topic records with provenance, effective dates, review owner, supersession and derived-data invalidation. Replay after rebuild and retry after partial publication must preserve the same approved logical record. |
| Later optional integration | New bounded proposal after #1587/#1541 | Read-only Knowledge MCP over the same authorised Atlas service, with client conformance tests. Add separate public consumer only if there is an actual audience requirement. No ChatGPT migration dependency for the local interviewer. |

Keep the conversational quality gate #1590 open. Define metadata and authorisation contracts early to avoid rework, but do not turn the next iteration into a broad connector programme. The next useful sizeable release is an integrated social-to-interview experience with reliable working memory and a small synthetic source-routing evaluation. Full publication and external access remain separately gated.

## Live backlog and evidence caveats

The read-only ADO snapshot on 22 September found #1522 (ledger) Resolved; #1576–#1581 (streaming and timing) Active; #1583 (recap) Active; #1582, #1585–#1590 New; and #1531–#1536 plus #1541–#1543 New. This includes status drift: Chatterbox has been selected in conversation and code, while #1585 remains New. Update evidence/status against actual acceptance criteria rather than closing a story from one preference or a passing unit suite. Parent rollups also lag the implementation.

The older opening of 08-backlog.md describes an earlier unstarted checkpoint. Use the later amendments, code and fresh ADO snapshot together. This review read the 71 mapped initiative items, not every project item or discussion.

## OpenAI packaging claims

Official documentation confirms distinct controls for skills, plugin installation, connector authentication and source permissions. Installing a plugin or sharing a skill does not itself grant access to connected sources. This supports the attachment's permission-separation principle. See [Skill controls](https://learn.chatgpt.com/docs/enterprise/skills) and [Roles and workspace permissions](https://learn.chatgpt.com/docs/enterprise/roles-and-workspace-permissions).

This review did not establish the attachment's specific 11 December 2026 GPT retirement date or every named connector/workspace entitlement. Treat those as unverified migration assumptions until a migration is actually proposed. They have no bearing on the recommendation to retain local interviewing and platform-neutral knowledge contracts.

## Evidence pointers

- Supplied DOCX: sections 1–15 and Appendix A; all 11 rendered pages inspected. The original was not modified or uploaded.
- [ADO snapshot and attachment hash](evidence/2026-09-22/knowledge-architecture-backlog-review.json).
- [Architecture](04-architecture.md), [backlog](08-backlog.md), [accepted delivery amendments](19-conversational-core-delivery.md), [social prototype limitations](28-social-conversation.md), [Chatterbox selection](29-chatterbox-audio-continuity.md).
- Current implementation: `services/sme_interviewer/evidence.py`, `ledger.py`, `conversation_store.py`, `review.py`; `src/assistant/sources/models.py`, `api/auth.py`, `retrieval/service.py`.

This is a design/code/backlog review. No new runtime benchmark or human-quality evaluation was run, and no implementation superiority is inferred from the supplied document's lack of measurements.
