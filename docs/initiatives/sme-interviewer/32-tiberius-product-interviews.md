# Tiberius iteration 3 — attributed product interviews

Delivered 24 September 2026. Internal rehearsal; owner acceptance remains open.

## Use it

1. Open http://127.0.0.1:8773/ and choose **Contribute product knowledge**.
2. Select **Chris** or **Dan** and one product topic. Start with the existing headset/Chatterbox flow, or use the typed-and-spoken link on Knowledge review.
3. Answer, clarify, interrupt or pause as before. Ask for a recap to hear recent captured wording. Reopen a saved interview to continue with the same contributor/topic.
4. Pause, then open http://127.0.0.1:8773/knowledge. Inspect the original question and captured answer. Correct a proposed excerpt or enter a clear claim when interpretation was uncertain. Set available/planned/uncertain and confirm the wording.
5. Save the proposal. It is still pending. Inspect supporting originals and related topic records. Record compatible/distinct scope, replacement, or dispute with a rationale. Replacement/dispute applies to **all related records shown**, explicitly labelled in the UI.
6. Enable a resolved claim for internal rehearsal separately. Return to **Ask about OpsAtlas** mode; approved additions are available on the next question. No restart or model training is required.

Correcting an existing contribution withdraws the old approval and creates a new pending version. Excluding a record removes it from subsequent answers. A disputed or uncertain interview claim cannot be enabled until resolved/corrected. Wording confirmation is not factual approval. Names are self-declared on this single-operator Mac, not authenticated identities.

## Architecture and integrity

- The existing continuous recording, ASR, endpointing, interruption and Chatterbox paths are retained. Local `qwen3.5:4b` generates a follow-up and provisional excerpt/status/issue. No external inference or new model download.
- Product interview settings are validated at session creation and included in the creation identity. Reusing a request ID with changed contributor/topic conflicts. Saved settings are used on resume.
- The voice path does not publish to Atlas. A generation check precedes durable `product_turns` storage in the isolated voice SQLite ledger. Cancelled stale responses cannot become contributions. Original question, recognised text, contributor, topic and local interpretation are retained. Session limit: 60 contributions.
- Interview context contains a bounded topic pack (up to eight records), recent dialogue and recent account memory. Exact duplicate questions get a fresh review/evidence prompt. Explicit recap uses committed wording instead of asking the model to reconstruct facts. This is recent-account memory, not unlimited semantic memory.
- The proposal proxy obtains attribution and original wording from the server-side saved turn. Browser-supplied contributor/original-text fields cannot replace that provenance.
- Proposal IDs derive from session/turn. Exact retries reuse the same sources. Corrected versions reject the old native source before registering new source material, so interruption fails closed. Rejected originals remain retained.
- Durable input sources contain raw wording, corrected wording, question, contributor, topic, availability and confirmation time. Derived Markdown contains a fingerprint of the input, binding approval to provenance as well as spoken text. Both are registered and ingested through Atlas. Existing Atlas source approval actions enable/reject reviewed claims; dispute/supersession also withdraw native source approval. Relationship decisions and review decisions are retained in the local audit history.
- The sales catalog is a durable file plus immutable registered source versions. Sections are derived through normal ingestion. This is **not** the full E2 atomic ontology publication/rebuild implementation; no claim of graph-only publication or distributed transactional recovery is made.
- Recall continues to speak reviewed excerpts and revalidate source hashes after inference. Planned claims have an explicit spoken qualification. Uncertain/disputed claims cannot supply product answers. Original Atlas data is not used or modified.

## Validation

Automated coverage includes idempotent proposal creation, stale correction/approval, changed provenance with identical claim wording, old-source withdrawal, restart/readback, uncertainty, stale overlap lists, scoped resolution, Chris/Dan disputes, supersession, cancelled generation exclusion, server-bound attribution and deterministic recap. The final regression run passed **327 Python SME tests and 53 JavaScript tests**; Ruff and diff whitespace checks passed.

Real local checks use a disposable workspace on ports 8774/8781. Browser verification exercised mode selection, saved interview review, transcript correction, planned status, explicit scope rationale, approval and enabled readback. A real local recall then cited and spoke the newly approved planned-deployment claim. Test approvals never touched the delivery corpus.

Evidence files under `evidence/2026-09-24/` retain synthetic local-model/voice results. First-packet timing excludes microphone recognition, endpoint detection, browser playback and subjective headset quality. The final three reasoned development turns reached the first audio packet in **1.28–1.39 seconds**; the deterministic recap took **0.16 seconds**. Four development turns are not a latency SLA or broad semantic evaluation.

## Remaining limits / next acceptance

- The small local model can still choose an incomplete excerpt, mark clear statements uncertain, or miss semantic nuance. The review screen therefore preserves full original wording and never auto-approves model interpretation. When extraction is empty but the turn is classified responsive, the review form starts from the full captured wording; unclear/off-topic turns require explicit clarification. One editable proposal per turn is supported; multi-claim decomposition is not delivered.
- Same-topic records are conservative review candidates, **not** proven semantic contradictions. Cross-topic contradiction discovery, cross-contributor semantic comparison at scale, and background deep analysis remain backlog work.
- The interview pack is bounded; recall still checks the current catalog. A growing-corpus load/quality benchmark and indexed retrieval should precede scaling. No neural/vector database has been introduced without that evidence.
- Only one local operator and one headset speaker at a time. Wake-name/background listening, Jabra room echo, diarisation, customer-facing publication and enterprise identity remain outside this release.
- Human acceptance: test one short Chris interview, confirm/correct and enable a scoped claim, ask Tibi about it, then add a differing Dan account and inspect the dispute workflow. Assess accent, pacing and interpretation on the real microphone. Automated audio packet checks do not replace that acceptance.

## Operations

The existing [workspace runbook](31-tiberius-sales-workspace.md) and launchd start/status/stop commands apply. Refresh the browser after deployment. Existing saved conversations, credentials and review decisions are preserved. The delivery remains in the isolated `.runtime/opsatlas-sales` workspace.
