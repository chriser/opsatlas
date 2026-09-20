# Thinking and comprehension iteration — v5

20 September 2026 · #1524 · Release-ready synthetic prototype for Human trial; G2 conversational acceptance remains open.

The Human accepted the v4 direction, then identified two concrete gaps: an explicitly completed supplier activation was reopened as a question, and the roughly ten-second silent planning interval made the interviewer appear unresponsive. This increment addresses those observations while retaining entirely local inference, exact source disclosure, the independent question review and the unpublished-draft boundary.

## Behaviour

- A narrow deterministic pass recognises explicitly reported supplier outcomes and named or role-based decision owners. It applies only to confirmed reported-practice wording and rejects conditional, hypothetical and unknown constructions. These observations supplement the local model's extraction; they do not infer facts from policy, proposals or questions.
- A completed activation, release, cancellation or hold cannot be reopened with a direct question such as “Was the supplier activated?”. Follow-ups may still ask about a genuinely missing step, check or record before that known outcome.
- Low-reasoning output is normalised when it combines two questions or assumes that a record exists. The resulting wording uses the existing single-gap, neutral question bank and still passes the same structural, provenance and independent local-model review before speech.
- While planning, the page immediately displays animated dots and cycles through short, human-readable status phrases. With **Speak new questions** selected, Voice B plays one prepared phrase such as “Give me a moment. I am considering what you have just said.” The cue is pre-rendered and adds no model request. It stops before the checked question is spoken.
- Question writing now uses low reasoning. Coverage extraction and review already used low reasoning. The 45-second overall deadline and visible deferral remain in force.

## Measured local development result

Profiling the previous medium-reasoning path separated the cost into 2.806 seconds for extraction, 9.351 seconds for writing and 1.921 seconds for review, or 14.115 seconds in total. Writing was the dominant delay.

The final low-reasoning candidate completed all three critical synthetic development cases:

| Case | Result | Time |
|---|---|---:|
| Explicit activation and manager approval | Asked whether further checks occurred before activation; did not ask whether activation happened | 7.147 s |
| Supplier held for renewed certificate | Asked neutrally whether the decision was recorded and, if so, where | 7.649 s |
| Released exception | Asked whether additional checks occurred before release | 6.767 s |

These are three seeded development examples, not a held-out quality score. The local model and its review remain fallible. The deterministic pass deliberately covers only a small set of explicit supplier-process statements.

## Verification

- 617 repository Python tests passed with a disposable `KP_DATA_DIR`.
- 167 interviewer tests passed in the separate speech environment.
- 16 Node browser-control tests passed, including the visible thinking state and prepared Voice B cue.
- Ruff, JavaScript syntax, diff checks and the Atlas frontend production build passed. The existing Starlette/httpx/AnyIO deprecation notices and frontend chunk-size notice remain non-blocking.
- An isolated browser journey on port 8768 entered the Human's example wording, confirmed its sequence and observed the visual and spoken thinking cue. The next checked question was: “What other checks, if any, were carried out before the manager approved the supplier activation?” It did not reopen the known activation. The browser console had no warnings or errors.

See [verification](evidence/2026-09-20/conversation-v5-verification.json), [development scenarios](evidence/2026-09-20/conversation-v5-development.json), [browser journey](evidence/2026-09-20/conversation-v5-browser.json) and [pipeline credential recovery](evidence/2026-09-20/pipeline-677.json).

## Pipeline recovery

With the Human's explicit instruction, the working GitHub PAT from the repository `.env` was copied into the existing secret `GITHUB_PAT` variable on ADO pipeline definition 2. No permission or pipeline-structure change was made, and no credential value is recorded. A build of the then-current main commit, [ADO build 677](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_build/results?buildId=677), completed successfully, including **Mirror to GitHub**. The release commit receives its own CI verification after push.

## Remaining acceptance work

#1524 remains Active until the Human evaluates the revised flow across a broader fictional conversation. #1526 still owns held-out conversational evaluation. The real Atlas evidence adapter, Atlas navigation, multi-user authority and publication remain later work. No physical-headset recognition or acoustic claim changed in this increment, and no new Azure Test Plans, Test Suites or Test Cases were created.

Refresh `/interview` after the local service update. Existing sessions remain available. A new fictional session gives the cleanest comparison for whether an explicitly supplied outcome stays understood and whether the thinking cues make the local planning interval feel natural.
