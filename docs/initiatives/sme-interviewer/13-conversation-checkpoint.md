# Conversational interviewer — unreleased checkpoint

19 September 2026 · #1524 · **Not selected for rollout.**

The Human reported that the contextual iteration mostly repeated part of an answer before returning to scripted questions. This trial implemented generated follow-ups using the confirmed account and actual question history, then evaluated whether the local planner could reliably pursue the missing detail. The implementation works mechanically, but complete-turn quality failed. The working v2 service remains on `127.0.0.1:8767`, with application source restored to `c2b7f4bc4562532bfaf26a6cb3e427bd361ea54d`.

## Preserved implementation

The unreleased candidate is isolated at `/Users/chriser/.codex/worktrees/sme-conversation-trial/ai-knowledge-analytics-assistant`. Its files were copied and SHA-256 verified before restoring only this trial's changes in the main checkout. Unrelated work and existing interview sessions were retained. The temporary preview on port 8768 was stopped.

The candidate generates one short question, checks exact source excerpts/revisions, retains a brief unverified question plan, and applies a separate local-model review with one repair attempt. Rejected planning stays visibly pending. The interface exposes what a question draws on without reading those excerpts aloud. Draft exports retain the exact question alongside answers such as “No”; these remain participant accounts rather than inferred approved facts. Audio capture and Voice B were unchanged.

## What passed, and what did not

Candidate software verification passed: **584 isolated backend tests**, **134 tests in the speech environment**, **13 Node checks**, Ruff, JavaScript syntax, diff checks and the Atlas frontend build. These are candidate results, not new measurements of the restored v2 baseline. Full backend tests used disposable `KP_DATA_DIR` before imports. Existing dependency/build warnings remain.

The [isolated browser trial](evidence/2026-09-19/conversation-browser-checkpoint.json) verified a fictional interview, source disclosure, a short negative answer, and JSON/Markdown draft context, with no console warnings/errors. It also exposed a coverage regression: earlier supplied details became unassessed after a short answer. No new physical microphone, ASR fidelity or acoustic acceptance is claimed.

The combined deterministic guards and local reviewer passed [13 targeted calibration cases](evidence/2026-09-19/conversation-review-calibration.json). However, the [final broader development run](evidence/2026-09-19/conversation-final-development.json) still failed: among nine attempted turns, three remained pending, two accepted questions were rejected on agent inspection, three were considered acceptable, and one needed Human usefulness review. One accepted question asked “Who approves the finance approval that releases the supplier?” Another requested an approver already supplied in the hypothetical account. Structural provenance and a model's own review did not establish semantic correctness.

These scenarios were used during development and tuning. They are neither independent Human assessment nor held-out G2 evidence. A repeated successful attempt cannot replace the failed run. No model configuration was selected and no acceptance gate was passed.

## Local model findings

Tests ran on the Human's Mac Studio M4 Max with 64 GB unified memory and Ollama 0.34.2. See the [comparison](evidence/2026-09-19/conversation-model-comparison.json), [Qwen trial](evidence/2026-09-19/conversation-qwen35-rejected.json) and [initial GPT-OSS trial](evidence/2026-09-19/conversation-gptoss-initial.json).

- Qwen 3.5 35B-A3B produced unsupported assumptions and repeated details; sampled thinking plans took roughly 30–54 seconds. Mixed-model use also incurred reloads under the current desktop load. This does not establish a general hardware capacity limit.
- GPT-OSS 20B produced more natural wording but still confused requested actions with completed events, repeated known information, and sometimes passed its own unsuitable questions. The final candidate used low reasoning; further reasoning/review did not reliably resolve the quality gap.
- A focused DeepSeek R1 32B reviewer passed four probes, but the broader mixed-model trial still accepted unsupported approval premises at roughly 32–51 seconds per turn. Longer pauses alone did not qualify it.

The newly downloaded Qwen 3.5 35B-A3B and GPT-OSS 20B models remain installed locally but unselected. No hosted inference was used, no actual participant content was sent to another provider, and no Atlas knowledge was published.

## Decision and next work

#1524 remains Active. The immediate release blocker is conversational quality, with the coverage regression also requiring repair before a future rollout. More deterministic guards should not be presented as a general solution to understanding the account.

**Human decision, subsequent checkpoint review:** the Human rejected an OpenAI-hosted planner/comparison and reaffirmed entirely local operation. The proposed hosted experiment is withdrawn; no hosted inference occurred. The previous failed configurations do not establish that local operation is infeasible or that the Mac's capacity is insufficient.

The next local increment should address conversation state before another broad model search. Code inspection confirms that the candidate reconstructs coverage from a fresh model assessment on each turn. This is a plausible mechanism for the observed loss of coverage after a short answer, not a proven explanation for every unsuitable question. Preserve source-backed assessments across turns, explicitly invalidate them on corrections, link short answers to the exact question, and distinguish requested actions, completed events, unknowns and hypothetical accounts. Select the missing detail explicitly before asking the local model to phrase a question; evaluate whether this improves complete-turn quality without returning to repetitive scripted interviews. Question review remains fallible.

Human conversational acceptance and the later held-out #1526 evaluation remain outstanding. There is no external API dependency or unanswered cloud-permission question blocking local development.

## Interruption recovery audit

After the token-limit interruption, the subsequent audit confirmed main and ADO at documentation checkpoint `0a3dcc6`, the checkpoint and handover present in the Wiki, and #1524 still Active/owned by Codex. All 15 preserved candidate service/test files matched the saved SHA-256 manifest. The candidate remains uncommitted in its isolated worktree; its implementation has not been pushed or deployed. Main service/test source matches the working v2 baseline exactly. The interview page returned HTTP 200, Ollama listed the installed local models, and temporary preview port 8768 was stopped. Existing unrelated untracked files were left untouched.

The saved test logs confirm the 584/134 results above; these suites were not rerun for this documentation audit. No interrupted code edit or missing checkpoint publication was found. The remaining work is product quality and later integration/evaluation, not recovery from the token interruption.
