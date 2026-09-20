# Local conversational iteration — v4

19 September 2026 · #1524 · Synthetic prototype for Human trial; conversational release acceptance remains open.

This increment replaces automatic quotation plus topic templates with a locally written question about a missing detail in the confirmed account. It also fixes the loss of prior coverage after short answers. Speech recognition, Voice B, source wording, session history and the unpublished-draft boundary remain unchanged. No hosted inference or external API is used.

## Behaviour

- Source-backed detail assessments survive appended answers, retries and planning failures. A changed earlier contribution, question context or scope invalidates dependent assessments. The next successful assessment rebuilds them from the current wording; stale observations are not presented as current.
- Short answers retain the exact question that gives them context. An explicit unknown can seek a possible source once, then move on. Not knowing that source cannot overwrite an unrelated known detail.
- The writer chooses its focus and supporting sources before wording the question. Already-addressed details are excluded from its focus choices. Hypotheticals remain conditional and policy questions explicitly refer to the guide or policy.
- Exact source revisions, corrected numbers, question shape and selected event/approval assumptions are checked before speech. A separate local review and one repair attempt follow. These are fallible safeguards, not proof that every question is useful or every premise is supported.
- The draft retains question/answer pairs, including “No”. For an assessed unknown, it uses the actual unresolved question instead of replacing it with a generic topic question.
- A deferred question is clearly labelled and does not automatically speak a generic review prompt. The contributor can retry, correct wording or finish the draft.

## Local runtime and latency

The selected prototype runtime is the installed `gpt-oss:20b` through loopback Ollama. Coverage and review use low reasoning; question writing uses medium reasoning, with a 3,072-token output ceiling. The model runs on the Mac, including its review pass. Voice B remains Kokoro `bf_isabella`.

This is slower than v2. Completed medium-reasoning development turns commonly took roughly 12–22 seconds; the final three critical regressions took 13.192–22.501 seconds, including one deferred question. The service now has an explicit **45-second overall planning ceiling**, allowing more time for longer corrected accounts. Individual requests remain bounded. This is a latency trade-off for the synthetic trial, not acceptance of the original conversational latency goals.

## Verification and limits

The final backend gate passed **609 tests** with disposable `KP_DATA_DIR`, and the separate speech environment passed **159 tests**. **14 Node tests**, Ruff, JavaScript syntax, diff checks and the Atlas frontend build passed. Existing Starlette/httpx/AnyIO warnings and the existing frontend chunk-size warning remain.

Live local evaluations retained failed attempts as evidence. The faster writer was rejected after inventing an approval step for certificate renewal. A twelve-scenario medium-reasoning development run still exposed repeated recording questions and long turns. A later application-forced focus experiment regressed on all three critical examples (unstated handover, repeated reason, repeated actor) and was removed. Narrow guards address explicit absent recording, unsupported handovers/approval roles and repeated first-person hold actors; they are not general entailment checks.

On the final candidate, the released-supplier example asked whether additional checks had been performed (17.773 seconds); the unrecorded hold asked what prompted the certificate check (13.192 seconds). The held-supplier example was **deferred after validation** (22.501 seconds). That third case is not counted as a successful follow-up. This is a usable synthetic trial with explicit failures, not an all-pass conversational release or G2 acceptance.

The browser journey exercised “No”, subsequent ERP details, an unknown date, an unknown source, saved drafts, restart/reopen and correction. Earlier source-backed coverage survived the short answer, and the interviewer moved on after the unknown source. A correction at the former 30-second deadline was safely deferred with revised wording retained; later corrected-account turns progressed, and the final-runtime reopening result is recorded in the browser evidence. Historical question wording is retained as asked, so it can still mention a system subsequently corrected in an answer; it is not rewritten as a current fact. No new physical headset or acoustic fidelity claim is made.

See [verification](evidence/2026-09-19/conversation-v4-verification.json), [failed fast run](evidence/2026-09-19/conversation-v4-fast-rejected.json), [medium development run](evidence/2026-09-19/conversation-v4-medium-development.json), [rejected forced-focus experiment](evidence/2026-09-19/conversation-v4-forced-focus-rejected.json), [final critical regressions](evidence/2026-09-19/conversation-v4-critical.json) and [browser journey](evidence/2026-09-19/conversation-v4-browser.json).

These are development checks and agent inspection, not independent Human usefulness ratings or held-out G2 acceptance. Fifteen broad detail categories constrain exploration; the interviewer is not yet an unrestricted expert conversationalist. Exact source matching does not establish semantic entailment. Question usefulness, repeated model trials, long-session behaviour and latency still need evaluation. #1524 remains Active for conversational acceptance; #1526's held-out evaluation and the later Atlas adapter/integration remain outstanding.

## Try this iteration

Refresh `/interview` after the service update and start a new fictional interview, or resume a saved one. Give a concrete account with an unresolved step, then answer naturally rather than matching a script. Confirm transcript wording as before. Expect a visible thinking pause. If planning is deferred, the answer remains saved and **Ask next question** retries it. Check whether questions explore what is still missing without reopening details already supplied; corrections and **Finish draft** remain available.


## CI publication status

Commit `a96db343ec1a56efd5ea40e7e36ed2542290ca83` is verified on ADO main and the local service is updated. [ADO build 672](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_build/results?buildId=672) passed backend tests, Ruff and the frontend build, then failed **Mirror to GitHub**: GitHub rejected the pipeline's HTTPS credential. The pipeline reads its secret `GITHUB_PAT`; it does not use an SSH private key. The repository `.env` GitHub token was verified by a read-only API request as working with push access. Neither token is included in evidence.

Automatic approval review blocked copying that specific token into the existing ADO secret variable because explicit transfer authorisation was not yet recorded. Human approval has been requested. No credential change or rerun occurred. The full CI build is therefore **failed**, despite green application checks. This remains a synthetic prototype available locally, not a fully green release.

**20 September recovery:** the Human explicitly authorised the credential transfer. The existing pipeline secret was rotated without changing permissions or pipeline structure, and [ADO build 677](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_build/results?buildId=677) passed, including **Mirror to GitHub**. See the [v5 delivery record](15-thinking-and-comprehension-iteration.md); the paragraphs above remain the contemporaneous v4 failure history.
