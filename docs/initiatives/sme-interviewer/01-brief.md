# Structured product brief

**Source:** user's supplied concept transcript, received 19 September 2026, plus current task clarifications. The brief below organises the request without treating examples as commitments or treating aspirations as delivered capability.

## Purpose and users

OpsAtlas currently makes approved knowledge accessible. The interviewer adds a way to elicit knowledge that is missing, make tacit process understanding explicit, enrich existing evidence, and resolve conflicting accounts through an appropriate human authority.

The primary participant is a subject matter expert. A process or knowledge owner approves changes. A facilitator can prepare the subject and review the resulting packet. A second expert may answer a bounded follow-up or adjudicate a specific conflict. Initially the domain is business processes and the Enterprise Activity Model; other domains can use the service later through a replaceable knowledge adapter.

## Required outcomes

| ID | Requirement from the brief | Design response / delivery slice |
|---|---|---|
| R01 | Standalone service linked to Atlas; one additional Atlas page | Independent interview service, API adapter, feature-flagged page; E1 |
| R02 | Reuse Atlas knowledge and ontology | Pinned approved evidence, provenance and typed entity references; E1 |
| R03 | Interview intelligently, including when no prior knowledge exists | Coverage plan, open questions, targeted follow-ups and explicit unknowns; E1 |
| R04 | Listen, take notes and adapt while the SME speaks | Streaming transcript, revision-aware claims and topic coverage; E1 |
| R05 | Challenge contradictions and missing detail precisely | Check transcription and scope first, then evidence-based clarification; E1/E2 |
| R06 | Capture conditions and variants rather than force a false single answer | Scoped assertions with applicability, modality and dates; E2 |
| R07 | Respectful, eloquent, natural voice with appropriate warmth and humour | Voice audition plus conversation policy and contributor feedback; E1 |
| R08 | Allow timely, respectful interruption | User-controlled challenge mode, turn boundaries, cancellable playback; E1 |
| R09 | Time-bound sessions without pretending coverage is complete | Visible open topics, pause/resume, unresolved summary and follow-ups; E1/E2 |
| R10 | Identify who can answer questions the current SME cannot | Named role/owner suggestion, human-confirmed follow-up task; E2 |
| R11 | Enrich Atlas through a staged validation path | Separate claim ledger, review packet, approval and durable publication; E2 |
| R12 | Fast checks plus deeper offline review where needed | Live/break/background lanes with visible review status; E1/E2 |
| R13 | Support a second reviewer who resolves conflicts | Evidence case showing both accounts and their dates; E2 |
| R14 | No external inference or speech-service calls | Locally hosted speech/LLM components; offline runtime verification; E1 |
| R15 | Research the remembered local TTS model and alternatives | Kokoro as a plausible identification, not a confirmed match; audition shortlist; E0/E1 |
| R16 | Avoid judgement, exhaustion and fear of being trapped by an answer | Corrections, uncertainty, decline/pause, accurate retention explanation; E1/E3 |
| R17 | Explain value to the SME and give useful information back | Immediate structured recap, reusable process draft, cited evidence; E1/E2 |
| R18 | Later meeting companion that listens, answers and flags discrepancies | Separate deferred multi-party slice; E4 |
| R19 | Later desk device, microphone, speaker and visual status ring | Open hardware investigation after software proof; E4 |
| R20 | Optional avatar or projection in a later vision | Explicitly deferred; no dependency on first delivery; E4 |
| R21 | Thorough research, ADO wiki, decision history and backlog first | This discovery pack and linked ADO records; E0 |
| R22 | Review existing ADO against code; preserve working Atlas | Dated audit, protected baseline, isolated data and regression gates; E0–E3 |
| R23 | Changes committed and decisions inspectable | Repository documentation mirrored to wiki; evidence and handover; E0–E4 |
| R24 | Stop creating ADO UAT test cases | Automated checks and concise acceptance evidence in ordinary work items; all slices |
| R25 | Ask for meaningful choices, access and useful books | Decision register and Human-owned input tasks; E0 |
| R26 | Agree the approach before starting development | G0 approval gate; implementation work remains New; E0/E1 |

## First proof of concept proposed scope

A 15–20 minute browser interview about one synthetic process. The service prepares a topic map from approved Atlas evidence, hears a description, confirms uncertain names/numbers/negation, asks context-sensitive questions, identifies a planted discrepancy, respects a correction or interruption, and ends with a structured draft plus unresolved questions. It must also work with an empty evidence pack without inventing policy.

The first technical demonstration stops at a draft packet. The next slice proves approval, publication, rebuild survival and a cited Atlas answer from that approved contribution. This sequence makes voice behaviour testable before introducing writes to governed knowledge.

The initial default is English, one speaker, one session and a headset. These are planning assumptions pending Human answers, not limitations of the eventual product vision. Basic keyboard/text alternatives, captions and pause controls are part of the first experience.

## Explicitly deferred

Teams/Webex bots; group diarisation and overlapping speech; autonomous calendar/email messages; live confidential enterprise sources; enterprise rollout; wake-word always-on listening; hardware procurement or firmware work; holographic projection; avatar integration; voice cloning; broader industry templates. Future records preserve these ideas without scheduling or funding them.

The local-only requirement applies to interview inference, audio, transcripts and organisational evidence. Public research/model downloads are setup activities. ADO is the requested delivery record, not an inference service. Teams/Webex would introduce an external meeting transport and must be separately agreed even if inference remained local.

## Product principles

The system should identify itself as an AI interviewer. It may be warm without pretending to be a human. It should ask one useful question at a time, admit uncertainty and make correction easy. A pleasant voice does not establish credibility; provenance and fair treatment do.

An SME's confirmation means that the captured account represents their intended meaning. It is distinct from approval by an authorised knowledge owner. The product must never imply that clicking a transcript confirmation grants policy authority or that a spoken statement is irrevocable.

Avoid promises that statements can never be used against someone unless the organisation has an enforceable policy supporting that promise. Explain actual purpose, access and retention plainly. The system must not infer honesty, competence or emotional state from a person's voice.
