# Restore Tiberius's conversational layers

24 September 2026 · isolated internal rehearsal · owner experience acceptance pending

## Correction of direction

The preceding sales integration replaced open conversation with approved-record selection, then added scripted social/teaching replies around that selector. That narrowed the interaction too far. The sales recall route now uses `LayeredCompanion`; the separate product-contribution interview remains unchanged. General conversation is not constrained to the starter product records or the small glossary. No cloud inference was introduced.

## Voice rollback

Restore the native-speed Chatterbox sentence adapter from `ccd4dd5`: same British reference, decode each sentence once, pass its samples through without tempo conversion, gain manipulation, comma splitting or inserted silence. Remove the FFmpeg delivery adapter. Keep the existing transport/playback continuity protections. This rolls back the processing the user reports as degrading quality; it does not claim the resulting sound is subjectively perfect or solve the earlier natural-pacing preference.

A synthetic worker run returned 7.013 seconds of audio with peak 0.383 and zero clipped samples. This is a smoke test, not a listening assessment or controlled quality comparison. No microphone recording or audible playback was performed.

## Layer 1: natural conversation and general explanations

A local Qwen conversation pass generates short responses from recent dialogue rather than matching scripted greetings or glossary entries. It can talk about the person's day, respond to interests, explain general concepts, and rephrase a misunderstood explanation. No Atlas request is made for ordinary conversation or general knowledge. General knowledge is explicitly labelled model knowledge, not approved OpsAtlas evidence. The prompt prohibits invented human experiences, repetitive sales steering and approval/publication claims.

This remains probabilistic generation; style, relevance and factual accuracy can fail. No keyword filter is described as a comprehensive product-claim firewall. A secondary explicit product-assertion check catches some routing errors, while the model is responsible for routing indirect product follow-ups.

## Layer 2: current-conversation reasoning

The same foreground inference also compares the current message with the recent conversation. Repetition should lead to a different explanation; incompatible statements should lead to a neutral clarification. Changed plans and scope differences are not automatically falsehoods. An explicit conflict annotation requires both quotations to match actual supplied wording; fabricated recollections fall back to clarification.

Keep twelve recent messages for fast model context. Separately retrieve up to four older, relevant excerpts from the full transcript using bounded lexical matching. This improves recall without placing the entire transcript in every prompt; it is not exhaustive semantic memory. No cross-session identity or personal memory is introduced.

Real local probes: garden small talk continued without a product pitch; ontology received a general explanation and a different formulation; a Monday-to-Tuesday change was remembered without being treated as a contradiction; a same-case £15,000/£50,000 discrepancy produced a clarification. The latter's generated annotation was `none` despite the useful clarification, showing that metadata classification still needs evaluation. Warm observed response reasoning ranged roughly 1.2–1.9 seconds for these general turns, and 2.4–3.4 seconds for product turns. These measurements are not latency guarantees and exclude speech.

## Layer 3: evidence work, kept separate

For product questions/assertions, a second pass receives a bounded pack of currently eligible approved product records. It produces a concise, plain-language answer and source ids. This intentionally changes the previous exact-excerpt-only policy: the wording is model synthesis and is labelled as such, not separately approved prose. Source ids, eligibility and byte hashes are checked again after inference. Missing/revoked sources cannot support an answer. Unknown/planned/experimental records must not become delivered-capability claims. Knowledge approval/publication remains exclusively in the existing review workflow.

A further independent evidence pass is scheduled after product speech completes, so it does not compete with voice synthesis. It checks both user and assistant statements, anchors a possible concern to a recorded turn and current source ids, and proposes a scope question. Results appear in the interface and are saved separately as `knowledge_checks`; concerns can inform a later conversational turn. This check can challenge Tibi's own answer. A deliberately false synthetic claim of perfect answers/enterprise readiness was flagged against approved sources.

One background check is active per conversation. A new foreground turn, pause or disconnect cancels unfinished checking to prioritise conversation. Cancellation/failure is never reported as consistency. Completed findings persist; they do not inject audio mid-utterance, approve facts or mutate product knowledge. Findings have no complete owner-resolution workflow yet.

**Scope limit:** this is an independent pass over up to 24 approved product cards, not deep retrieval across every ingested OpsAtlas document, semantic graph traversal, or the planned coffee-break completion workflow. That broader research/review queue is still outstanding. Sharing one local model/GPU also means the checks are logically separate, not physically independent workers. A second model pass is not proof of factual correctness, and a generated factual mistake may be spoken before the background check catches it. This remains internal rehearsal.

## Transcript repair

The visible transcript was sourced from `Companion.history`, which is trimmed to twelve messages. On each committed turn the same trimmed list overwrote `social_dialogue`, discarding earlier conversation wording. It was a storage/display bug, not evidence that speech recognition had cut a particular audio utterance.

Store the full committed conversation in `social_transcript`, separately from rolling model context. Display that full list, reload it with saved sessions, and include exact turn wording in future `social_exchange` audit events. Older sessions initialise the new transcript from whatever wording they still retain. Already discarded historical messages cannot be reconstructed from the old events, which did not store their text. Do not invent or claim recovery of those missing messages. Failed/uncommitted turns and interrupted spoken playback are separate issues; this fix preserves committed textual turns.

## Validation and rollout

350 Python tests and 60 JavaScript tests pass, plus Ruff and whitespace checks. New tests cover Atlas-independent chat, general explanations, generated source-grounded answers, concurrent revocation, fabricated conflict quotes, secondary product routing, background-review anchoring, older relevant memory, and transcript retention across ten turns while the model window remains twelve messages. Native voice samples pass through unchanged in adapter tests.

[Local synthetic evidence](evidence/2026-09-24/tiberius-layered-conversation.json) records the observed conversation, separate review and audio smoke metrics. No live user conversation was changed by those probes. Existing Governance approvals remain intact. Refresh Tibi to load the UI changes, then start or resume a conversation; start new to hear the introduction. Documentation and existing ADO delivery items remain open for owner acceptance, with deeper corpus work explicitly unfinished.
