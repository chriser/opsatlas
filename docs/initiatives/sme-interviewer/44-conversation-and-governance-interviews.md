# Conversation back, sales intent, and governance interviews with Tibi

**25 September 2026 · Built by Claude · Story #1727 (S154, conversation and sales intent) under F18; Feature #1726 (F19) with Stories #1728 (S155, governance interviews) and #1731 (S156, navigation and overlap passages) · Status: delivered for the Human's evaluation on branch `claude/tiberius-speed-safety`; nothing is merged to `main` until the Human accepts it.**

## Why

The Human's third headset session (15 turns; median end of speech to playback 1.41 s) raised three things:

1. **The small talk had gone.**
   - "How was your day so far?" was answered from product records: "I'm just here to answer product questions".
   - The Human liked a conversation that can drift off subject, provided it stays appropriate: no foul language and no controversial views.
   - They asked for this interaction material to be governed OpsAtlas data rather than hard-coded behaviour.
   - Politics ("Who is the US president?") was answered from stale model knowledge.
2. **The answers lacked the sales intent.**
   - Tibi should relate what the proof of concept shows to how an organisation such as a bank could use OpsAtlas.
   - That story should come from the Human through the interview workflow, not be hard-coded.
3. **A new flow: resolve governance issues by interview.**
   - OpsAtlas Governance lists compliance, consistency and correctness issues.
   - Tibi should take them in priority order, explain each one in enough detail for the Human to answer, and verify the answer against the sources immediately.
   - The answer is then saved for the Human to approve in the system.

## Conversation (S154)

**What went wrong:**
- The word "your" in "How was your day" matched the capability-question rule, so the turn was sent to product evidence.
- The conversation prompt also forbade any playful take on Tibi's "day".
- "If I want to use it for my own business, which is a bank, how would I use it?" was treated as chat.
- "You're not answering my question" then met a canned "That sounds good."

**Now:**
- **Small talk is conversation.**
  - "Busy in the best way, lots of good questions today. How's yours going, Chris?"
  - Tibi is honest that it is an AI and never invents a body or a personal life.
  - The chat may drift to everyday topics (sport, fitness, weekend, travel, food) and return to OpsAtlas when the person does.
- **Boundaries are decided before the model speaks.**
  - Politics, current officeholders, religion and crude requests get a single light decline, with a note that Tibi's knowledge of current events may be out of date: "I'll stay out of politics, and my knowledge of current events may be out of date anyway. Shall we talk about something else?"
  - A profanity guard stops any generated sentence containing swear words.
- **Repair.** "You're not answering my question" answers the earlier question again, from evidence, with a note that the first answer missed the point.
- **Prospect questions are product questions.** "How would my bank use it?" goes to the evidence layer.
- **The conversation style is governed data.**
  - Six conversation records join the workspace as pending: personality, greetings, everyday topics, topics Tibi keeps out of, repair, and the purpose of a sales conversation.
  - They are drafted from the Human's direction of 25 September (`corpus/owner-direction/2026-09-25-conversation-style.md`). They are enabled in Knowledge review → Conversation style.
  - Enabled records relevant to a message are passed to the conversation model as guidance. They are never product evidence and never an interview topic.
- **Checker fix.** A conditional answer ("a real deployment would use stronger security measures") now matches a record that says those measures are *needed*. It still never matches one that says a capability is *not provided*, so "would support single sign-on" stays blocked.

## Sales intent (S154)

- The evidence prompt now says this is a sales conversation. After the direct answer, and only where the records support it, Tibi relates the answer to the participant's organisation or to the path from proof of concept to a working solution.
- Live answer to "How would my bank use it?":

  > "For your bank, you'd need to move from the demo's anonymised data to using your own real data in a secure enterprise environment. That's planned rather than available today. OpsAtlas would help with new-starter onboarding and understanding complex business processes…"

- The story of how proof-of-concept capabilities become a working solution is to be captured from the Human.
  - The product interview now opens *Real deployment* and *Path to production* with that question: "Which capabilities from the proof of concept would carry straight over, and what would need to change?"
  - Answers follow the existing workflow: the wording is confirmed with the Human, proposed, then enabled.

## Governance interviews (S155)

**How it works:**
1. In the Tibi page, choose **Resolve governance issues** and a contributor.
2. Tibi summarises the open questions and starts when asked.
3. For each issue, Tibi explains what is wrong, using the exact passages and what the rest of the corpus already says, then asks for a decision.
4. Your answer is checked against the sources. Tibi reads back what it understood, with the result of the check, and asks whether to save it.
5. A confirmed answer is saved as **pending**.
6. **Knowledge review → Governance answers** shows your answer, the resolution and the verification. **Approve and close the issue** runs the platform's own `accept_issue` action, so the issue leaves OpsAtlas Governance with your answer as its record.

Tibi never approves anything and never edits a source. Curated records are hash-bound to the paper sections they cite, so an answer saying a source needs changing stays a follow-up for the Human.

**The agenda.**
- It is the platform Quick Scan over the sales workspace, ordered with correctness first, then consistency, then compliance.
- On the live workspace, 27 issues become 22 questions:
  - One question per acronym, not per source: RAG is asked once for its five sources.
  - The standard abbreviations (AI, CPU, GPU, GB, SDK, CI, UAT, README) are one question.
  - An issue that lists several acronyms closes only when every one of them has an approved answer.
- The first build takes 0.4–0.9 s. It is cached until sources or accepted issues change, and saving an answer does not re-run the scan.

**What Tibi explains, per issue:**

| Issue | What Tibi says |
|---|---|
| Duplicate | Which passages match, and whether the overlap is by design. All five on the live workspace are: "the record *Architecture and technology* cites that section as its evidence". |
| Undefined acronym | Where the acronym is used. It also gives any definition in the corpus ("DT603 Part A defines RAG as Retrieval-Augmented Generation"), or a phrase whose initials spell it: the paper writes "Ontology-Augmented Generation" but never "(OAG)". Otherwise it quotes the sentence that uses it. |
| Broken link | The link target, and why OpsAtlas treats it as broken. |
| Readability | How many sentences run over 40 words, with the first as an example. |

**Verification before read-back:**
- **Definitions.**
  - A corpus definition gives "That matches Appendix A".
  - A conflicting one gives "But the paper defines RAG as Retrieval-Augmented Generation. Which should I record: yours, or theirs?"
  - A differing phrase in use gives "But the sources talk about Ontology-Augmented Generation, which also spells OAG".
  - An expansion that does not spell the acronym is flagged.
- **Rewording** is checked against the original with the claim checker.
- **Links** are checked for a complete address.
- **Factual statements** in any answer are checked against the passages involved: "It is 95 percent accurate" gives "The sources do not state 95%".

**Voice commands:** skip, repeat, go back, how many are left, and stop. Tibi also answers "what does it say exactly?" by reading the passage.

**Speed:**
- Replies are streamed sentence by sentence. The read-back's first sentence is spoken while the sources are checked.
- In the live check, every turn's first sentence was ready within 10 ms, except the few that need the model to interpret a free-form answer (0.4–0.8 s, preceded by "Let me check that against the sources").

**Live check** (text only, on a disposable copy of the live workspace):

| Answer | What happened |
|---|---|
| "Subject matter experts." | Understood without a model call; "That fits how DT603 Part A, section 1 uses it." |
| "It stands for Open Answer Generation." | Challenged with Ontology-Augmented Generation. "Use the sources' one" saved Ontology-Augmented Generation. |
| "Retrieval-Augmented Generation." | "That matches Appendix A." |
| "That's from GOV.UK … it can stay as it is." | Recorded as fine as it is. |

On that copy, approving answers ran `accept_issue` in the OpsAtlas action log and the Governance count fell from 27 to 26. The RAG issue in sources that also list OAG and EAM stayed open until those were answered.

## Fourth evaluation: navigation and overlap passages (S156)

The Human's next session (30 turns; median end of speech to playback 1.42 s) found the chat much improved, but the governance interview easy to confuse:
- Several requests were recorded as resolutions, one with the verification "The sources do not state 3":
  - "Of one source, I need the second passage from the other source."
  - "No, no, go to question 3."
  - "In question 3, can you give me the full overlapping sentences?"
- Unclear replies at the confirm step ("Stay tuned") re-asked the issue question.
- Duplicates read only the first passage, not where the two documents overlap.

**Now:**
- **Navigation and requests come first.** Before anything is treated as an answer, Tibi checks for:
  - navigation: go to question N, go back, skip, start again, check again or repeat, and how many are left;
  - "hold on" or "stay tuned", which gets "Take your time";
  - a request for information, such as "where is the overlap?", "the second passage" or "what's the difference?".
  None of these is ever saved or verified. A question number counts as navigation only when moving ("go to", "back to") or to a different question, so "we haven't resolved question 3 yet" is not a jump.
- **Duplicates show where they overlap.**
  - The core finds the closest sentence pairs between the two passages.
  - Tibi reads the closest pair in the explanation, and two pairs on request. When the sentences are identical it says so once: "both say, word for word: Quick Scan identifies deterministic quality concerns…".
  - The Tibi page shows every overlapping pair, labelled by document.
  - On the live workspace this surfaces, for example, the paper's "A knowledge owner can register anonymised learning material…" beside the record's "A knowledge owner registers anonymised learning material…".
- **The confirm step.**
  - "Awesome", "great" and "perfect" count as yes.
  - "Not yet" and "we haven't resolved it" save nothing.
  - Anything unclear re-asks "Shall I save it as I read it back?".
  - The saved answer is the substantive one ("I use the same architecture across the documents…"), not the word that confirmed it.
- **Unclear answers get the choices** for that issue, for example: "You can say the overlap is intended, say one of them needs changing, or ask me to read both passages." A long explanation is summarised on read-back ("with your explanation as the note").
- **Meta-talk is not verified.** Only claim vocabulary, percentages and money are checked against the sources.
- **Chat:**
  - Tibi adopts a corrected mishearing ("not sprink, spring").
  - It no longer repeats guidance examples word for word.
  - The "missed the point" guidance is chosen only for real complaints, not for "Good question".
  - Refreshed topic keywords keep the record's approval, because keywords are not part of its approved wording.

Replaying the Human's own lines against a copy of the live workspace with the real model, every line behaved as intended.

**Speed guard.**
- With all 27 records enabled, chat turns had become 150–250 ms slower: the enabled conversation guidance was re-read on every turn.
- Chat turns are now pre-warmed while the participant is still speaking, as product questions already were.
- A 40-turn Higgs replay with all 27 records enabled then measured end of speech to first audio at a median of **1.49 s (p95 1.64 s)**, with no errors, within the budget.

| Measure | Before pre-warming | After |
|---|---|---|
| Chat first token, median | 600 ms (455 ms before the guidance was enabled) | 281 ms |
| Chat first audio, median | 1.55 s | 1.49 s |

- Product answers are unchanged per question, within about ±100 ms of run-to-run noise. The one exception is "How much would it cost us per year?" (123 → 248 ms to first token), whose evidence pack grew with the newly enabled records.
- Evidence: [latency-replay-40-all-records.json](evidence/2026-09-25/latency-replay-40-all-records.json).

## Measured

**Replay.** A 40-turn replay with the Higgs voice ran on a copy of the live workspace, with the conversation records still pending. End of speech to first audio had a median of **1.43 s (p95 1.73 s)**, within the budget (1.95 s / 3.1 s), and there were no errors.

| Measure | Median |
|---|---|
| This replay, all turns | 1.43 s |
| Conversation turns | 1.42 s |
| Product answers | 1.47 s |
| Previous delivery (43), all turns | 1.37 s |

The longer conversation prompt costs about 60 ms, within run-to-run noise. Conversation replies are livelier, for example "Chatting along nicely! How's your day going?" and "Sounds exhausting! How was your day in meetings?" Evidence: [latency-replay-40-conversation.json](evidence/2026-09-25/latency-replay-40-conversation.json).

**CI.**
- Build 20260925.8 failed on one new test: the governance agenda reached for the local embedding model, which CI does not have.
- The agenda now reads the embedding model when it scans, and runs without duplicate detection if the model is unavailable.
- Build 20260925.9 succeeded. Locally, 945 Python tests pass on 3.11 and 3.12, and 58 browser tests pass.

## For the Human

1. In Knowledge review, enable the **Conversation style** records you are happy with. If you haven't already, also enable the two records from S152: *Security controls in the proof of concept* and *Real deployment and the organisation's own data*.
2. To capture the sales story, choose **Contribute product knowledge** with the topic *Real deployment* or *Path to production*.
3. To try the governance interview, choose **Resolve governance issues**, then approve your answers in **Knowledge review → Governance answers**.
