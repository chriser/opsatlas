# Publication and handover

**Initial publication: 19 September 2026. Follow-up: Human accepted G0 and supplied hardware/books/voice preference; isolated E1 is authorised. The first [speech prototype](11-prototype.md) is now delivered with Human Voice B selection; see its measured scope and remaining work.**

The delivery-state narrative below preserves the initial publication checkpoint. Its unanswered-G0 statements are superseded by the follow-up acceptance record.

## Canonical locations

- [Dedicated SME Interviewer wiki](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_wiki/wikis/AI-Knowledge-and-Analytics-Assistant.wiki?pagePath=%2FSME-Interviewer): overview plus ten subject pages after the readiness update, mirroring this repository pack.
- [Research and agreement Epic #1500](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1500).
- [G0 Human design/scope decision #1507](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1507).
- [Publication evidence Story #1506](https://dev.azure.com/chriser/ai-knowledge-and-analytics-assistant/_workitems/edit/1506): delivered commit identifier, pushed-main confirmation and verification evidence.
- [Full backlog](08-backlog.md), [planning manifest](backlog.json) and [published identifiers](ado-links.json).

The repository owns the versioned design text; ADO owns live workflow state and review discussion. Record accepted decisions in both the decision register and the relevant ADO gate. Later changes to either copy must reconcile the other rather than silently diverging.

## Delivery scope

The design pack captures the user brief, Atlas/ADO audit, primary-source research, proposed service contracts, conversation experience, evaluation gates, non-regression rulebook, ADRs and open questions. The two final DT603 documents informed the baseline; their embedded assignment wording is reference material, not a new instruction or operational approval.

The backlog contains 52 records with hierarchy, estimates, ownership, criteria and applicable predecessor links. Discovery Stories #1502, #1504, #1505 and #1506 may be Resolved after publication verification, but remain subject to Human acceptance. Epic #1500 remains Active while G0 is unanswered. No historical delivery item is reopened, no implementation item is started and no new ADO test-management artifacts are created.

Dated reconciliation notes were added to Project Overview, Module Status, Model and Voice Decisions, Evidence Index, Testing and Evaluation, and Definition of Done. They retain earlier text as history and point readers to the current audit. The shared Agent Handover Log records this delivery and next ownership. Investigation of historical links is complete in #1514; no matching rollback PR was found and #1289 returned 404. Their disposition remains unresolved. That Task remains Active with zero remaining investigation work, awaiting Human closure; Tasks have no Resolved state.

## Verification evidence and limits

- Authenticated access succeeded with the updated repository-root PAT. The stale project-name setting was corrected locally; no credential is included in the repo or wiki.
- Baseline `c7e6ff7` matched `origin/main` before this work. Offline backend regression: **450 passed**, one existing Starlette/httpx warning. Repository Ruff: **passed**.
- Publication verification reads all 52 new work items back and checks types, parents, estimates, owners, acceptance criteria and dependency links; all ten new wiki pages are read back against the repository text after link conversion. Earlier content on the reconciled wiki pages is preserved.
- Documentation links, manifest structure, dependency acyclicity, staged-file scope and credential exclusions are checked before commit. Application code, runtime data and model configuration are outside this change. Pre-existing untracked research/evidence files remain uncommitted.
- No local voice model was installed or benchmarked, no real interview was run, and the accepted historical 621-run RAG/OAG benchmark was not repeated. A frontend build/browser run is not needed for this documentation-only delivery. CI results are separate from the local test evidence above.

## Next owner and decision

Human reviews [the recommendation](README.md#accepted-direction-for-the-isolated-trial) and [decision register](07-decisions.md), then records the permitted G0 scope in #1507. The immediate inputs are machine/RAM/GPU, first channel, pilot process/owner and voice preferences. The proposed default is browser/headset, one English SME, synthetic process data and a staged draft before publication. These defaults remain proposals.

Codex starts no implementation until that decision is recorded. Later work must follow the [non-regression rulebook](06-evaluation-and-delivery.md#non-regression-rulebook), keep review completeness visible, and obtain the separate publication and real-participant gate decisions.
