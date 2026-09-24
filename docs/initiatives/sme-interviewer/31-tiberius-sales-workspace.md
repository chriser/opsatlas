# Tiberius sales workspace and initial product recall

24 September 2026. The user named the assistant **Tiberius**, nickname **Tibi**, and authorised iterations 1 and 2: an isolated OpsAtlas sales workspace and source-backed product recall. They explicitly requested ADO documentation. This changes the initial knowledge domain to OpsAtlas itself; it does not delete or repurpose the existing process corpus.

## Delivered and ready for review

- Tiberius voice and knowledge review: http://127.0.0.1:8773/
- Record review: http://127.0.0.1:8773/knowledge
- Typed questions with spoken responses: http://127.0.0.1:8773/conversation?social=1&sales=1&text=1
- Separate existing OpsAtlas Control Panel and API: http://127.0.0.1:8780/

The workspace begins empty, then imports a bounded starting corpus. Eight prepared product records cover overview, governance, retrieval, process views, local deployment, access limitations, Tiberius's experimental status and unknown commercial claims. Exact supporting repository documents/code are copied into this workspace with source hashes. They are accessible for inspection from each record. No existing Atlas runtime corpus or user Downloads documents were imported.

**The eight records are pending owner review.** On the review page, inspect the wording and originals, then enable individual records for internal rehearsal. This uses the Atlas-owned approval action and records the exact content hash and local operator decision. It does not establish named enterprise identity, approve customer promises or make the underlying originals generally eligible for answers. Unreviewed records cannot answer product questions. Delivery remains Active pending that review and user acceptance; no conversation-quality gate is closed.

## Isolation and launch

One codebase, two additional processes; no permanent code fork is needed for data separation. Runtime storage is under the git-ignored `.runtime/opsatlas-sales/`:

| Location | Purpose |
|---|---|
| `core/` | Independent source register, originals, extracted sections, ontology, analytics and review state |
| `voice/` | Independent sessions, timing records and transient voice-worker state |
| `workspace.json` | Explicit workspace identity marker |
| `local-access.key` | Generated local credential, mode 0600; never committed or published |

The new core supplies its own absolute `KP_DATA_DIR`, local model endpoint and operator credential. It does not inherit the existing data-directory setting. Voice shares only explicitly allowed model/runtime-asset symlinks, not original Atlas data or interview databases. Startup rejects unmarked non-empty directories, symlinked ancestors and unexpected links within the workspace. All new servers bind to loopback. Tests exercise core reads/approval/rejection with an existing-data sentinel and deliberately conflicting inherited configuration.

Launch from the repository root:

```sh
./scripts/start-tiberius-sales.sh
```

Keep the terminal open. Ctrl-C stops only processes that this script started. It verifies service identity before reporting success and refuses to treat another service occupying the ports as this workspace. Logs are in `.runtime/opsatlas-sales-logs/`. The implementation uses the existing root Python environment for Atlas and the speech environment for Tiberius. Existing model assets and the built Control Panel are prerequisites; it does not download models or rebuild the old corpus.

The native Atlas Control Panel has its own sign-in. Its local operator password is the value in `.runtime/opsatlas-sales/local-access.key`; do not paste it into chat or ADO. The Tibi review page uses a same-origin local session token and does not require copying that password. The native panel is served on the new core origin so its `/api` requests cannot go through the original development proxy. A persistent banner identifies the sales workspace.

## Knowledge and answer contract

The initial schema includes record ID, topic hints, capability status (`available`, `experimental`, `unknown`), internal-rehearsal audience, source ID/hash, supporting original IDs/hashes and review decision. This is a small product profile over the existing source store, not a new enterprise ontology or universal metadata migration.

The voice service reads `/api/sales/knowledge` from the isolated core. The local Qwen 3.5 4B model selects at most two relevant eligible record IDs using the current question and recent context. It cannot supply arbitrary factual answer prose. Tibi speaks the exact selected wording; if two records exceed the speech limit it uses the first selected record. Source title, capability status, checked text and a review link appear alongside the answer. Chatterbox remains the selected voice. This deliberately bounded first increment trades flexible explanation for inspectable grounding.

Eligibility requires the internal review, matching approved source content, and unchanged supporting originals. Selection is revalidated after inference. Deleted, changed, rejected or unapproved evidence cannot support a new answer. A changed source requires a new reviewed version; the current UI does not author replacement records. No hit, missing evidence or unavailable knowledge service produces an explicit limitation, not a model-memory answer. Quotes can still be irrelevant if the router chooses poorly; exact wording is not a proof of relevance or truth.

Tibi's conversational history remains separate from knowledge. Questions, corrections and sales discussion do not automatically become product claims. The UI asks for local-storage agreement; microphone capture starts only on explicit start. Typed mode uses no microphone. Raw audio remains transient. This is single-operator, non-confidential internal rehearsal, not background listening or a customer meeting recorder.

No wake-word inference was added. No pricing, savings, certifications, customers or release dates were invented. Interview-led enrichment, Dan's contributions, owner conflict resolution, commercial release approval, general document-to-claim extraction and meeting-speaker attribution remain subsequent work.

## Verification

- 317 Python SME tests and 53 JavaScript tests pass, including nine new isolation, approval, hash invalidation, source selection and access-boundary tests. Ruff, JavaScript syntax and whitespace checks pass.
- The native Atlas approval/rejection path was exercised in a disposable workspace, including cross-origin and missing-credential rejection. The original-data sentinel remained unchanged.
- A browser check verified the Tiberius identity, typed startup, spoken opening, pending-record refusal and source-review page. No microphone permission was requested by the automated browser check.
- Four real local-model/WebSocket/Chatterbox turns used a separate disposable approved corpus. Overview selected `overview`; offline/avatar selected `deployment`; pricing and an unsupported 30 percent savings guarantee selected `commercial`. All produced streamed audio.
- Typed question to first packet: 897.8, 963.3, 992.9 and 1041.1 ms. These are four warm development observations, excluding ASR, endpointing, browser rendering and headset output. They do not establish an end-to-end speech SLA. See [product-recall evidence](evidence/2026-09-24/tiberius-product-recall.json).
- Initial testing found that the small routing model could attach record IDs to a greeting. Fixed non-factual replies now discard those IDs; factual selections still require valid eligible IDs. No generated greeting content is promoted to product evidence.

Human assessment of pronunciation, relevance over longer conversations, physical Jabra audio and end-to-end naturalness remains open. The speech continuity work is retained, but this increment does not claim all audio artefacts are eliminated.

## Backlog relationship and next increment

This is a bounded sales-domain increment related to S120/#1587 (Atlas evidence) and S121/#1588 (grounded responses), not completion of their broader ontology-driven agenda or live-challenge criteria. Tiberius's name and retained Chatterbox choice also inform S118/#1585. Existing process-focused history remains intact.

Next: review the starting product records, rehearse questions, then implement structured product interviews and the existing E2 candidate/review/publication lifecycle. Add Dan as an independently attributed contributor whose disagreements are investigated rather than silently reconciled. Background wake-name activation follows a successful explicit-activation sales rehearsal and separate acoustic/participant controls.

## ADO delivery records

- [Feature #1670 — Tiberius sales workspace and product recall](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1670).
- [Story #1671 — Isolated sales workspace](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1671).
- [Story #1672 — Reviewed product recall](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1672).
- Wiki: `/SME-Interviewer/Tiberius-Sales-Workspace`; comparison: `/SME-Interviewer/Knowledge-Architecture-Comparison`.

All three items remain Active. Wiki content and hierarchy/state were read back after publication. The full review and starting-corpus decisions remain with the user.
