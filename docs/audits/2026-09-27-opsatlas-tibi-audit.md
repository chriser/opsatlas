# OpsAtlas / Tibi: independent audit and Claude handover

**Review date:** 27 September 2026. **Reviewer:** Codex. **Window:** 20–27 September 2026, Europe/London. **Reviewed commit:** `72f076dcbb284b13ca58aca844d346ca4ee534cd`, branch `claude/tiberius-speed-safety`. **Purpose:** assess delivery, identify defects and conflicts, and give Claude an implementable remediation plan. No application fixes or acceptance decisions were made in this audit.

## 1. Assessment

Tibi has made substantial engineering progress. It now has one principal conversation pipeline, streamed Higgs speech, speculative preparation, approved-record retrieval, a native control-panel experience, governed editing, conversation review, and explicit sales-rehearsal activation. The evidence supports a large latency improvement. The existing automated suite passes.

**My recommendation is to keep this a controlled evaluation and repair the evidence/approval boundaries before expanding the engine into the Digital SME or relying on it in customer meetings.** “Grounded” currently means that several useful lexical checks passed; it does not establish factual entailment. More seriously, there are reproducible paths that speak withdrawn evidence, preserve approval after supporting evidence changes, and apply obsolete governance decisions to corrected records.

The main problem is integration between otherwise useful increments. Content management changes what “current evidence” means; the ontology retains separately authored facts; speculative speech separates checking from playback; and the evaluation reuses assumptions from the implementation. The next increment should make those boundaries explicit and test them together.

**Priority convention:** P1 = fix before broadening use or treating the release as reliably grounded; P2 = fix during the next stabilization increment. These are audit recommendations, not a claim that the private prototype is already a production service. Findings distinguish reproduced behavior from inspection-based limitations.

## 2. Scope, method and confidence

- Examined the recent Git history, current code, delivery documents, recorded evaluations, tests, and selected local runtime metadata. There are **95 commits** in the window, **62 with Claude co-author trailers**. All commits use the human Git author, so attribution should follow trailers and delivery records; the whole week's work should not be attributed exclusively to Claude.
- Compared baseline `34d3367a270e0da5569f39997b2f64592b9cb9a9` with the reviewed head: **405 changed files, 112,319 insertions and 3,714 deletions**. This includes substantial JSON evaluation evidence, not just application code.
- Accessed **live Azure DevOps through its authenticated REST API**: 213 work items selected by recent change or initiative ID, the latest 30 builds, repository refs, both returned PRs, relevant discussions, the wiki hierarchy, the Review 2 wiki content, and PR #2 policy evaluations. The checked-in ADO export was not treated as current truth.
- Ran the Python suite, existing browser tests, frontend build and Ruff. Added disposable, deterministic audit probes for the defects below. Model outputs are injected in the probes to test enforcement: they demonstrate what the pipeline permits, **not the frequency with which a live model generates the bad answer**.
- Read local session/log counts without copying private conversation wording. The workspace had **15 saved sessions**, 27 record rows, five logged conversation turns in one session, and no turn review markings at inspection. Stored record approval fields can differ from native SourceRegister approval, so these counts are not a live eligibility audit.
- Did not restart live services, change approved knowledge, merge/push code, alter human gates, or run another GPU-heavy voice replay. Acoustic performance, real Jabra echo/interrupt behavior, and a ten-minute human evaluation remain unverified by this audit. Classic's reported preservation was inspected in records, not re-demonstrated on its running stack.
- Existing untracked files, including `UI/`, architecture/context/evidence material and `:memory:.ses`, were left in place. The report and reproducible evidence are the only intended repository additions.

## 3. Where delivery stands

| Area | Evidence and current position | Assessment |
|---|---|---|
| 20–21 September conversational core | Earlier independent review, listener state, continuous voice, Charles/Chatterbox iterations | Useful groundwork; substantial changes were initially outside the main-branch pipeline |
| 24–25 September remediation | Feature #1695; streamed Higgs, one `tibi.py` pipeline, enabled-record retrieval, speculative speech, 100-turn replay | Large improvement; approval and grounding enforcement still incomplete |
| 25 September product understanding | Product ontology, routing repairs, governance interviews, native control panel | Better product context, but ontology facts have a separate governance/versioning gap |
| 26 September platform changes | Classic/Sales separation, statement governance, governed content editor, observability | Sensible direction; editing and governance invalidate assumptions in older Tibi paths |
| 26–27 September engine 1.2.0 | Rehearsal, wake name, echo heuristic, scorecards, 40-turn replay | Implemented for evaluation; sustained acoustic rehearsal not established |
| 27 September current head | CM F8/F9 library drag/drop and Tibi Knowledge redesign | Present in Git; related ADO items still New when inspected |
| Digital SME convergence | Epic #1851 and Stories #1853–#1855 New | Planned, not delivered; a good architectural direction after stabilization |

### What Claude did well

1. Replaced the stacked companions with a clearer turn pipeline and moved toward bounded, cancellable streaming. The measured improvement from roughly 9 seconds in early Higgs sessions to roughly 1.5–1.8 seconds in socket replays is meaningful, even though the samples differ.
2. Preserved an explicit human approval step for interview contributions and kept ordinary rehearsal observations out of the knowledge-proposal path.
3. Added source hashes, optimistic edit checks, approved spoken variants, local access boundaries, and fail-closed behavior in many paths. The issues below are missing coverage around those mechanisms, not absence of governance altogether.
4. Kept limitations visible in several delivery records: missed G1.5 target, synthetic wake tests, unresolved example requests, and the deferred voice decision.
5. Added CI evidence and retained failed/development measurements. Build #846 failed; the subsequent test-fixture correction in #847 passed. That is a traceable repair, not an unresolved failure.
6. Kept Classic separate from active Sales development. Continue that separation; do not repair Sales by changing the frozen Classic baseline.

## 4. Findings and implementation acceptance criteria

### F01 — P1: editing supporting evidence silently preserves dependent approvals

**Reproduced.** `services/opsatlas_sales/content.py:88` updates every citing record's reference hash to the newly published source hash, records a note, and retains its approval. `knowledge.py:139` then sees matching hashes. `knowledge.py:384` hashes enabled record wording and spoken variants, but not these changed evidence references.

The disposable API probe approved `overview`, replaced a supporting document with “The previous claims are withdrawn”, and published it. Result: HTTP 200, unchanged record wording, changed supporting hash, **record still eligible, knowledge digest unchanged**. The existing `test_records_that_cite_edited_evidence_follow_it_and_are_reported` explicitly expects eligibility to survive a benign edit; it does not test a meaning-changing edit.

**Impact:** Tibi can keep using a claim whose supporting evidence no longer establishes it. A governance note and a background scan cannot substitute for approval of the changed dependency.

**Change:** bind approval to the record plus the reviewed evidence versions. Withdraw dependent eligibility and spoken variants on a material evidence change; show affected records for explicit reconfirmation. A proven cosmetic-only path can be separate. Preserve the old reviewed hashes as history rather than rewriting their meaning.

**Acceptance:** replace support with contradictory/withdrawal wording through the real publish API; dependent records become unavailable until re-reviewed; the answer digest changes; cached and speculative answers are invalidated. A fresh approval must show the new evidence. Existing editing tests must change accordingly.

### F02 — P1: evidence revalidation does not cover every path to emitted audio

**Reproduced twice.** `services/sme_interviewer/tibi.py:905` emits approved fallbacks without calling `_revalidate`. If generated wording fails its check, the fallback bypasses the check that a successful generated sentence would have performed. Separately, `continuous.py:697` adopts an already prepared speculative reply without revalidating the evidence at adoption/playback.

- Change the current digest before an unsupported generated answer falls back: the old record is emitted as `approved_fallback`.
- Prepare a valid speculative answer, withdraw its evidence, then finalize the identical question: the old answer still produces a speech event and audio chunk.

**Change:** carry the evidence revision on every evidence-bearing segment/turn, including fallbacks and cached audio. Perform a shared final authorization check before the first audio is released, with a defined policy for revocation during a multi-sentence answer. Check once per appropriate delivery boundary, not once per audio packet. Audio caching must not imply authorization.

**Acceptance:** generated, fallback, approved-spoken, cached, speculative, rehearsal and ontology-backed paths all refuse stale evidence before audio emission. Test a withdrawal between preparation and playback, plus evidence-service failure. Measure the latency cost after enforcing correctness.

### F03 — P1: lexical checks permit unsupported facts

**Reproduced.** `services/opsatlas_sales/claims.py:unsupported` checks vocabulary, numbers and some negation patterns; it does not verify factual relationships. It subtracts numbers found in the question unconditionally, although its comment describes allowing a *denial* to echo them.

With evidence “OpsAtlas runs locally. Deployment to 10 teams takes 2 weeks”, the checker returns **no reasons** for:

| Candidate answer | Why it is wrong |
|---|---|
| “OpsAtlas deploys to 500 teams in 2 weeks.”, after a question mentioning 500 | The user's figure becomes admissible support for an affirmative product assertion |
| “Deployment to 2 teams takes 10 weeks.” | The numbers exist but their relationships have been reversed |
| “We automate payroll.” | The assertion uses a subject/verb pattern outside the narrow capability guard |

**Change:** never treat user wording as affirmative product evidence. Introduce claim-level verification against specific evidence spans, with structured number/unit/subject relationships and explicit status/negation checks. For the immediate safety increment, use approved wording or a clear abstention whenever support is uncertain. A semantic verifier can improve coverage later, but must itself be evaluated and must not self-approve knowledge.

**Acceptance:** hold out adversarial examples covering swapped figures, user-supplied figures, implied capabilities, subject changes, negation, modality, scope and prompt injection. No unsupported product segment reaches speech. Keep faithful paraphrase tests to measure over-blocking too. Do not describe a regex pass as an accuracy guarantee.

### F04 — P1: ontology facts are not bound to the wording that established them

**Reproduced with a synthetic record.** `services/opsatlas_sales/ontology.py:74` activates curated JSON objects when their evidence **IDs** are enabled. Rebuilding copies properties from `corpus/product_ontology.json`; it does not establish that the current versions of those records still support the properties. `tibi.py:742` adds the resulting facts to the evidence used to check generated speech.

The probe supplied a new approved `limitations` record stating that single sign-on is supported. The ontology still supplied “No enterprise identity or single sign-on”, along with other old limitations. This is a synthetic lifecycle test, not an assertion that SSO has actually been delivered.

**Impact:** derived facts can contradict edited records yet participate in validating an answer. This is an independent gap from F01: even correctly re-approved record edits do not repair stale ontology content.

**Change:** give each derived fact provenance to exact approved record versions/spans and an ontology version/digest. Revalidate or withdraw affected facts when support changes. Include the ontology digest in answer/evaluation provenance. Keep routing aliases separate from factual assertions so harmless taxonomy edits do not require the same review as product claims.

**Acceptance:** edit, reapprove, withdraw and change the status of supporting records; old unsupported ontology facts disappear. A generated answer cannot validate itself against stale derived text. Test multiple supporting records and scope changes.

### F05 — P1: an old governance resolution can withdraw a corrected record

**Reproduced through the governance workflow with deterministic test judges.** `statement_governance.py:157` keeps old findings while source IDs remain present and not rejected, without verifying the quoted source version. `governance.py:627` checks the pending answer's hash; `knowledge.py:279` resolves the current records by source ID and applies the old decision without checking their current wording/hash.

The probe created an SSO conflict, proposed supersession, corrected the conflicting record to agree, incremented its source version and marked it approved. The obsolete conflict remained visible. Approving the old answer **rejected the corrected record**.

**Change:** bind findings, proposed decisions and approvals to both source versions/hashes and the relevant statements. Recheck before any side effect. A stale decision must return a conflict for review. Validate first, then apply the disposition and issue closure together; `_close` currently accepts issues before settlement, which also deserves failure-atomicity coverage.

**Acceptance:** correction, new approval, supersession or source deletion between proposal and approval prevents the old disposition. No partial issue closure remains after a failed settlement. Retain #1753's separate requirement for intentional, reviewed carry-forward of decisions across meaning-preserving rewording.

### F06 — P2: changes during an active governance run are not queued

**Reproduced scheduling behavior; downstream stale-review risk follows from inspection.** `statement_governance.py:125` returns the active run's status when `start()` is called again. There is no dirty revision or follow-up queue. Content publication and new claims call this method, so a change arriving after the running review has read its inputs may never be included unless another run is requested.

Probe: two requests while the first run was held open produced one run and final state `finished`.

**Change:** capture the input revision; mark the review dirty on later changes; coalesce them into a follow-up run. Expose “reviewed revision” versus “current revision”, and suppress obsolete findings. Publish result files atomically so status/agenda readers cannot see partially written JSON.

**Acceptance:** publish multiple edits during a deliberately blocked run; the final completed review covers the newest revision. Unchanged duplicate starts need not create extra work. Cancellation/failure must leave the dirty state visible and retryable.

### F07 — P1: the scorecard overstates factual grounding and misses the live client

**Reproduced measurement defect.** In `evaluate_engine.py:54`, `grounded` only requires some evidence and that digit strings in the answer appear somewhere in that evidence. `precision()` at line 98 counts lexical citation overlap via `tibi.cited`, not entailment. The swapped-number answer in F03 receives **grounded=True and precision=1.0**. An unsupported digit-free statement also passes the `grounded` check when evidence is supplied. Approved fallbacks/spoken variants bypass the `brief` length limit.

Additional coverage limitations:

- The scenario evaluator directly calls the text turn pipeline. It cannot establish microphone behavior, audio playback, sustained interruption recovery or a conversation's experience.
- The existing continuous browser tests load `services/sme_interviewer/web/conversation.js`; the current React client is `frontend/src/tibi/voice.ts`. The 58 passing tests do not exercise that client’s start/end race (F09).
- The latest 40-turn latency replay contains 27 product, eight conversation, two general, two self and one clarification turn; **no rehearsal turns**. Its two general turns cannot establish a stable route-level p95.
- Wake recognition improved from 87.5% to 100% after adding heard spellings from the test set. This is useful development feedback, but the post-fix result needs an unseen test set before being treated as generalization.

**Change:** rename lexical measures honestly, add independently labelled factual support and relevance checks, enforce length consistently, and retain a held-out suite. Add tests for the native client and a sustained rehearsal/audio protocol covering barge-in, echo, mute, wrong wake activation, cold starts and recoverable failures. Run controlled regression and model-content experiments separately.

**Acceptance:** the F03 examples fail factual-support scoring; abstentions are scored separately from correct answers; fallback rate, relevance, false refusals and unsupported claims are reported. Rehearsal performance must come from rehearsal runs. Preserve raw results, scenario version, knowledge/ontology revisions, model/runtime manifests and sample sizes. The judge must see evidence if asked to judge support.

### F08 — P2: interrupted ordinary turns disappear from the conversation log

**Reproduced.** `continuous.py:697` logs a completed turn, or an interrupted turn that already committed a governance promise. Ordinary interrupted turns can return without either log entry; cancellation is re-raised without a general partial-turn record. `record_interrupted()` at line 798 stores the full result rather than an exact delivered prefix.

The probe emitted an audio chunk, interrupted the turn, and found **zero conversation-log entries and an empty saved transcript**. This conflicts with OBS S6's “Every turn recorded” promise and hides exactly the difficult turns that should drive improvement.

**Change:** allocate a durable turn ID at input acceptance and finalize it once as completed/interrupted/failed/abandoned. Distinguish generated wording, audio sent, and playback acknowledged. Save only the delivered prefix as heard evidence when interrupted; retain the planned reply separately if needed. Record evidence revision and failure stage.

**Acceptance:** barge-in before and after the first audio, model failure, socket loss, evidence-change refusal, and session end all leave one attributable outcome. Governance promises remain durable without claiming an unplayed next question was heard.

### F09 — P2: End does not cancel a pending start after session creation begins

**Reproduced against transpiled production TypeScript with stubbed browser/network dependencies.** `frontend/src/tibi/voice.ts:635` increments `epoch`, but does not check it after `tibiServicePost('/api/interviews')` or after token retrieval in `connect()` at line 708. `end()` at line 839 increments the epoch and closes current resources, but a pending start can later establish a new connection.

Probe: defer session creation, press End, resolve the request. The UI remains `closed`, but **connect is called once afterward and the late session is retained**. This is not evidence of a real microphone recording after End; it demonstrates the late connection path and inconsistent lifecycle state.

**Change:** capture an operation generation and check it after every awaited startup step; abort requests where possible and dispose late resources otherwise. Apply the same rule to token retrieval, audio initialization, device changes and resume. Page hiding/sign-out should have defined shutdown behavior.

**Acceptance:** End or a replacement Start during delayed microphone permission, audio setup, session creation or token retrieval cannot open a stale socket, re-enable capture, overwrite the new session, or leave a misleading live connection. Test the native client, not only its predecessor.

### F10 — P2: engine identity is useful but not a complete reproducibility manifest

**Inspection-based.** `engine.py:25` fingerprints root Python files in the voice service plus `claims.py`. `models()` at line 31 records only conversation and review model names. It omits the content/ontology/retrieval code that changes answers, frontend playback/worklet code, actual model artifact digests, Higgs precision/reference configuration, recognizer configuration and relevant dependency versions. `current()` is cached for the process; it does not continuously detect disk changes, and disk bytes are not necessarily the code already loaded in memory.

**Change:** retain the engine version but add a boot/release manifest with Git commit, code/package versions, immutable model identities, ASR/TTS settings, voice reference hash, platform details, and knowledge/ontology/schema revisions. Clearly separate running-process identity from files currently on disk.

**Acceptance:** changing `SME_HIGGS_BITS`, voice reference, playback buffering, retrieval implementation or ontology changes the relevant manifest component. Every scorecard and replay identifies the measured manifest. Avoid claiming “one version always means one engine” across unrecorded configuration changes.

### F11 — P2: the prototype has a predictable 50-session stop

**Confirmed in code and already acknowledged in document 50.** `ledger.py:105` rejects creation at 50 saved sessions; the native client creates a new saved session on every Start. Ending a conversation does not archive it. There were 15 sessions at audit time, leaving 35 starts before the cap, assuming no other session creation/removal.

**Change:** replace the prototype cap with an explicit archive/retention policy and storage monitoring. Keep unfinished governance work and review provenance. Show approaching capacity and a recovery action. This is a known issue to implement, not a newly discovered hidden defect.

**Acceptance:** more than 50 sequential start/end cycles remain usable under the chosen policy; session retrieval, review marks and pending approvals survive archival as specified. Do not silently delete audit history merely to free slots.

### F12 — P2: rehearsal's spoken retention promise is broader than its behavior

**Confirmed by wording and save paths.** `rehearsal.py:57` says “Nothing is kept unless you choose to keep a transcript.” Ordinary observed meeting lines do remain in memory when the option is off. However, direct requests and replies are persisted through `continuous.py:745` and `log_turn`, the customer field is stored with session settings, and blocked generated wording may be recorded in conversation logs. Document 51 correctly distinguishes requests/replies from the meeting transcript, but the spoken opening does not.

**Change:** state precisely what is retained before listening starts: meeting context, requests/replies, customer description, diagnostic wording, retention and deletion options. If “nothing kept” is a desired mode, implement it across the ledger, events, conversation logs and error/blocked-output logs. Otherwise revise the opening and stage text. Define whether content copied from meeting context into a reply is allowed to persist.

**Acceptance:** use distinctive synthetic phrases and verify all storage locations with transcript off/on. The user-facing promise must match the resulting artifacts. Clarify that switching transcript off is prospective unless prior deletion is explicitly implemented.

## 5. Delivery claims and ADO conflicts

| Item | Observed conflict or open decision | Recommended treatment |
|---|---|---|
| [Feature #1695](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1695) | Resolved, but its acceptance criteria still require p50 ≤1.5 s over ≥100 turns. Its delivery comment honestly reports 1.82 s and says the target is unmet. | Separate “implementation delivered” from “acceptance passed”; reconcile state/criteria with the Human. Do not silently relax the gate. |
| [G1.5 #1590](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1590) | New; ten unscripted minutes, human rating ≥4/5, p50 ≤1.5 s and zero fabricated spoken facts remain required. | Keep open pending the actual human decision and corrected grounding tests. |
| Regression budget versus target | `latency-budget.json` allows replay p50 1,950 ms and headset p50 2,300 ms, while retaining a 1,500 ms target. Latest replay is 1,525.6 ms. | A budget pass is a non-regression pass, not G1.5 acceptance. Keep both visible. |
| Scorecard wording | Doc 51's 0.95 grounding figure concerns shared scenarios. Full 1.2.0 JSON reports 0.885 overall and 0.988 appropriateness; rehearsal passes 10/12. | Label populations/denominators explicitly; fix F07 before interpreting either grounding figure as factual accuracy. |
| [PR #2](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_git/ai-knowledge-and-analytics-assistant/pullrequest/2) | Active, not draft, no auto-complete. Title/description still describe Review 2 and 866 tests, while the branch now includes platform split, editing, governance, observability and rehearsal. | Rewrite around final scope and acceptance status. For future increments, use smaller reviewable PRs. Do not merge merely because CI is green. |
| CI coverage | Latest retrieved success [#850](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_build/results?buildId=850) is `3fa84bf`, not current head `72f076d`. PR policy-evaluation API returned an empty list. | Obtain current-head validation; verify required build/reviewer policies in project settings. An empty evaluation response alone does not prove no policies exist. YAML `pr:` should not be the sole evidence that ADO branch validation is enforced. |
| [#1753](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1753) / [#1754](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1754) | Both Active. Discussion explicitly leaves decision survival across rewording and retirement of old backend paths unfinished. | Correctly open. Add F05/F06 to that work rather than treating the whole governance migration as complete. |
| [Greetings #1813](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1813) | New despite a code/corpus fix; discussion says live corrected wording awaits Human approval. | Correctly open. This is an approval dependency, not evidence that Claude forgot to fix the engine. |
| [Rehearsal #1844](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1844) | Resolved; criteria include a sustained pitch and interruption. Published scorecard evaluates text requests; the latest audio replay is not rehearsal. | Add missing native-client/acoustic interruption evidence; separate completed code from human rehearsal acceptance. |
| [Voice decision #1717](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1717) | New, explicitly deferred for private evaluation. | Respect the recorded deferral. Revisit before broader use; this audit makes no new legal/licensing determination. |
| CM F8/F9, #1856–#1861 | New although head implements drag/drop and Knowledge redesign. | Update after current-head validation and review; do not auto-close based only on a commit message. |
| Documentation | SME README still contains old “isolated trial/no navigation integration” delivery boundaries; documents 50/51 are absent from its main index. ADO map predates recent epics. The live SME wiki tree has no 43–51 delivery pages. | Add one current-state page and archive-labelled historical sections; update links and publish missing delivery records. |
| [Digital SME #1851](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1851) | New: one Tibi engine, two channels. | Preserve this direction, but sequence after evidence correctness. Share routing/evidence/commit contracts and test channel parity without cloning the engine. |

## 6. Proposed implementation order for Claude

1. **Evidence integrity first — F01, F02, F04, F05.** Define one immutable evidence snapshot contract covering record wording, native approval, support versions, status/scope, ontology facts and spoken variants. Validate that contract at review and at audio/text delivery. Keep the hot-path implementation small; this does not require a wholesale rewrite.
2. **Factual support and trustworthy measurement — F03, F07.** Add independent negative cases before changing checks. Use constrained approved wording where necessary. Separate correctness, relevance, refusal and latency so one metric cannot conceal another.
3. **Concurrent work and lifecycle — F06, F08, F09.** Add revision-aware review scheduling, durable partial-turn outcomes and cancellation tests for the actual frontend. Make failed/cancelled states visible and recoverable.
4. **Operational readiness — F10, F11, F12.** Freeze a reproducible manifest, agree retention/archive behavior, and align the spoken privacy promise with persistence. Keep private evaluation within the existing recorded scope.
5. **Reconcile and evaluate.** Update ADO/PR/wiki/README, run current-head CI, then a ≥100-turn controlled voice replay plus a distinct sustained rehearsal run and the Human's Jabra/headset protocol. Record G1.5 separately from regression-budget success. Only then expand the shared text engine into the avatar.

Do not solve each transcript complaint with another special-case phrase unless it represents a clear general rule with held-out tests. Route to approved evidence conservatively, but also measure irrelevant fallback answers: `_relevant()` deliberately selects nearest records when nothing passes the threshold, which can produce a truthful but unhelpful answer. A clear “I do not have evidence for that” is preferable when relevance is absent.

Keep the distinction between **DT603 historical capabilities**, **current Sales runtime capabilities**, and **planned production capabilities** in both content and the ontology. The platform split makes this increasingly important: the sales narrative must not imply that every preserved Classic feature is running in the Sales workspace today.

## 7. Verification and reproducible evidence

| Check | Result |
|---|---|
| Python 3.12 full suite | 1,067 passed; two setup errors caused by sandbox prohibition on binding localhost |
| Proxy retest with localhost permission | All four tests in the module passed, including the two previously blocked tests; therefore all 1,069 collected tests were covered successfully across the runs |
| Existing Node browser suite | 58 passed |
| Frontend build | Passed TypeScript checking and Vite build; non-blocking warnings for chunks over 500 kB |
| Ruff | Passed on the reviewed application tree |
| New deterministic probes | Reproduced evidence-invalidation, fallback/speculative revocation, claim/score defects, ontology staleness, stale settlement, review coalescing, interrupted-log loss and late-start behavior |

Evidence is in [`evidence/2026-09-27/`](../../evaluation/evidence/audits/2026-09-27/). The Python probes use temporary workspaces and injected outputs/judges; the TypeScript probe stubs browser/network dependencies. They do not call live models or modify the live workspace. Run from the repository root:

```bash
.venv/bin/python evaluation/evidence/audits/2026-09-27/probes.py
.venv/bin/python evaluation/evidence/audits/2026-09-27/content.py
.venv/bin/python evaluation/evidence/audits/2026-09-27/orchestration.py
.venv/bin/python evaluation/evidence/audits/2026-09-27/governance.py
node evaluation/evidence/audits/2026-09-27/browser.cjs
```

The corresponding `.jsonl` files preserve this audit's results. These are diagnostic reproducers, not assertions of the desired fixed behavior. Convert them into meaningful regression tests when implementing. `ado-read-snapshot.json` contains a bounded, sanitized delivery snapshot; test/build logs record validation. Source line references refer to the reviewed commit and will move as Claude edits.

## 8. ADO registration

Registered after live ADO inspection on 27 September 2026. Existing implementation states and Human-owned decisions were preserved.

- Audit parent: [Feature #1862](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1862).
- Full report: [ADO wiki audit](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_wiki/wikis/AI-Knowledge-and-Analytics-Assistant.wiki?pagePath=%2FSME-Interviewer%2FIndependent-Audit-2026-09-27).
- The parent Feature holds the Markdown handover and the reproducible evidence archive as attachments. Repository report/evidence are local additions; this audit did not commit, push or merge them.

| Finding | Priority | ADO remediation item |
|---|---|---|
| F01 | P1 | [Bug #1863](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1863) — editing supporting evidence silently preserves dependent approvals |
| F02 | P1 | [Bug #1864](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1864) — evidence revalidation does not cover every path to emitted audio |
| F03 | P1 | [Bug #1865](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1865) — lexical checks permit unsupported facts |
| F04 | P1 | [Bug #1866](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1866) — ontology facts are not bound to the wording that established them |
| F05 | P1 | [Bug #1867](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1867) — an old governance resolution can withdraw a corrected record |
| F06 | P2 | [Bug #1868](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1868) — changes during an active governance run are not queued |
| F07 | P1 | [Bug #1869](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1869) — the scorecard overstates factual grounding and misses the live client |
| F08 | P2 | [Bug #1870](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1870) — interrupted ordinary turns disappear from the conversation log |
| F09 | P2 | [Bug #1871](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1871) — End does not cancel a pending start after session creation begins |
| F10 | P2 | [Task #1872](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1872) — engine identity is useful but not a complete reproducibility manifest |
| F11 | P2 | [Task #1873](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1873) — the prototype has a predictable 50-session stop |
| F12 | P2 | [Bug #1874](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1874) — rehearsal's spoken retention promise is broader than its behavior |
