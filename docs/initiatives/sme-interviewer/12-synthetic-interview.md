# First complete synthetic interview

> **19 September 2026 — v4 follow-up:** the local-only conversation-state iteration is now available for synthetic Human trial. See [current release evidence and limits](14-local-conversation-iteration.md). The rejected configurations and earlier measurements below remain historical; they are not current acceptance results.

19 September 2026. The Human authorised this increment after selecting Voice B and confirming one headset transcription. The standalone interview now runs at `http://127.0.0.1:8767/interview`. This is an initial synthetic trial, not G2 acceptance or permission to publish organisational knowledge.

## Try it

1. Open **Interviewer** from the voice studio, or the address above. Use a fictional supplier-activation example and accept local transcript storage. Scope may remain unknown.
2. Start the interview. Voice B asks one question; type or select **Record an answer** using the headset. Select **Finish recording** within the visible three-minute limit. Recording interrupts playback.
3. Review the transcript, particularly names, numbers and negation. Select whether it describes practice, policy, a proposal, a hypothetical or uncertainty. Confirm the wording and save it before continuing.
4. Try **Pause session**, **Resume session** and **Correct wording**. Stop audio also switches off automatic speech; questions can continue as text. Saved sessions reopen paused without activating the microphone.
5. Select **Finish draft** to review the captured contributions and open points. Download Markdown or provenance JSON. **Revise this draft** reopens it for corrections and preserves the previous packet in history.

An unsaved editor prevents leaving, asking another question or finishing. A microphone result is saved provisionally and cannot feed planning or a finished draft until its wording is confirmed. The browser still cannot guarantee preservation of unsent text/audio when its tab or process is terminated.

## Delivered behaviour

| Component | Current implementation |
|---|---|
| Independent ledger | SQLite outside Atlas, ordered events, optimistic session/segment revisions, idempotent mutations, correction history and audio sequence references |
| Interruptions | Push-to-talk, Stop, Pause and late-result suppression; restart/disconnect recovery with explicit possible-gap notices |
| Evidence | One invented, pinned supplier guide with eligibility, version, scope, excerpt boundaries and hashes; changed/revoked packs block comparison and export |
| Dialogue | Free narration and sequence review first; local Qwen 2.5 14B assesses 14 individual details, then missing-detail questions reference current confirmed excerpts |
| Unknowns | Explicit uncertain wording gets a question allowing the point to remain open; no model output grants factual approval |
| Scope | Comparator questions require current nonempty evidence, an established matching region/route/date and a prior scope question; no automatic discrepancy determination |
| Review | Original confirmed contributions, contribution kinds, source revisions, evidence snapshot, unverified excerpts, unassessed slots, gaps and a canonical packet hash |
| Publication | No publication endpoint, graph mutation or automatic approval |

The model cannot supply executable tools or arbitrary spoken instructions. Its constrained schema limits question keys, coverage slots and segment IDs; a second check requires each quote to be an exact contiguous excerpt of a confirmed segment. Categorisation can still be wrong, so captured excerpts remain **unverified clues**, not completed factual checks. A model timeout, unavailable service or rejected response uses a checked guide question and leaves factual review pending.

Corrections and scope changes invalidate previous derived notes and any current packet. Pausing preserves the acknowledged account; resuming conservatively invalidates the previous analysis so it can be reassessed. Historic questions/results remain in the event ledger. Draft content is frozen at its recorded input revision; reopening retains the superseded packet in history.

## Runtime and data

Run `./services/sme_interviewer/start.sh` from the repository root. The service uses its existing isolated environment and selected B configuration. Subsequent dialogue requires the installed `qwen2.5:14b-instruct` model at `127.0.0.1:11434`; there is no hosted inference fallback, runtime model download or new root dependency.

Confirmed and provisional text, corrections, scope and packets are saved locally in `services/sme_interviewer/.runtime/interviews.sqlite` with owner-only file permissions. They persist until explicitly removed; there is no retention scheduler or deletion UI in this increment. Consent precedes creation. Use synthetic content only. Audio remains temporary under the speech service's existing cleanup policy; audio sequence references are provenance identifiers, not retained recordings. Confirmed text is sent to the **local** dialogue model. No transcript is uploaded to ADO or the wiki by the service.

The service caps saved sessions at 50, contributions at 30 per session, text at 6,000 characters per contribution, questions at 60 per session, and microphone recordings at 180 seconds. Planning uses at most the latest 12,000 confirmed text characters, up to 14 quoted observations, a 12-second model timeout and a 15-second planning deadline. Earlier details can therefore remain unassessed. One speech job and one planning job run at a time. It remains a loopback, single-operator prototype, without multi-user identity/RBAC or a remotely deployable security design.

## Verification and limitations

- Full isolated repository regression: **522 passed**. `KP_DATA_DIR` was set to a disposable temporary directory before importing Atlas. Existing Atlas sources and runtime stores were not used.
- The 72 focused speech/session tests also passed in the service’s isolated environment. Seven Node browser-control tests passed, including late audio creation, cancellation during cleanup, unsaved-text protection and competing microphone actions and Stop during a pending microphone permission prompt. Python checks cover revisions/concurrency, invalid-model fallback, correction invalidation, late model results, restart gaps, fixture revocation, escaped exports and absent publication.
- Repository Ruff, JavaScript syntax, and the existing Atlas TypeScript/production build passed. The existing Starlette/httpx deprecation and Vite chunk-size notices remain.
- Real browser journey: create, save two fictional contributions, block an unsaved finish, restart and reopen paused, correct wording to revision 2, obtain a locally selected question, pause/resume, finish and reopen a draft. [Browser console and live export checks](evidence/2026-09-19/interview-browser.json) record the completed journey.
- [Six exploratory local-model probes](evidence/2026-09-19/interview-evaluation.json): 6/6 returned valid local-model plans; all 30 structural/provenance checks passed. Warm request durations were **0.598–0.742 seconds**. Cases included a standard route, an emergency exception, uncertainty, a hypothetical, instruction injection and an empty evidence pack. These are development probes, not a held-out quality evaluation, precision/recall measurement or long-session benchmark.
- The first live unconstrained JSON response used an invalid observation category. It was rejected and visibly fell back. Constrained schema generation corrected that observed failure; exact-quote validation remains required.
- Voice B/headset selection and the earlier correct £15,000/not-£50,000 recognition are retained. The separate one-penny ASR error is **still unresolved**. Automatic acoustic endpointing, false-cutoff rates, noisy headset trials and acoustic barge-in remain pending under #1520. This release uses the explicit recording controls.

The question bank provides bounded adaptive selection, not unrestricted conversational generation. The source adapter contains a fictional guide only: it does not yet read approved Atlas evidence. No actual conflict adjudication, factual validation, owner approval, Atlas navigation integration or knowledge publication is delivered here.

## Delivery status and next evidence

#1522's standalone ledger requirements are implemented and verified, ready for Human review. #1523 and #1524 remain Active: the fixture contract and initial staged dialogue are delivered, with the real Atlas evidence adapter and broader conversational acceptance still outstanding. #1520 remains Active for the outstanding acoustic work. The optional Atlas page (#1525) and held-out staged evaluation (#1526) remain later work. No Human-owned gate was closed and no ADO Test Plans, Suites or Cases were created.

The next Human test is a short fictional headset interview: assess whether the questions follow the account naturally, corrections are comfortable, Voice B is clear, and the exported draft preserves the intended meaning. Use several contributions if an answer exceeds three minutes; leave uncertain details explicitly uncertain. This feedback informs the next refinement before real evidence or participants are introduced.


## Headset trial failure and recovery fix — 19 September 2026

The Human's first Chrome/Edge interview trial produced only “you” on two 30-second recordings and lost question replay after provisional saving. This is failed physical-capture evidence. The raw audio had already been removed, so its actual signal level and root capture cause cannot be established retrospectively.

The installed recognizer reproducibly returns **“you” for 30 seconds of generated digital silence**. The HTTP boundary now rejects recordings with no usable signal (peak below −50 dBFS or RMS below −65 dBFS). Near-silent leading/trailing edges are trimmed for recognition, retaining 250 ms padding. This is a conservative amplitude check, not speech detection or proof of intelligibility. Substantial noise can still pass; quiet legitimate speech can require increased input level. A result of two or fewer words from at least ten seconds of audio carries a visible review warning.

The interview now offers named microphone selection, the actual input device label, a live input meter, a visible elapsed-time counter and a warning in the last 30 seconds. Its recording cap is **three minutes**; the voice studio's short audition remains 30 seconds. WAV conversion selects the strongest input channel so opposite-phase stereo does not cancel the signal. The larger transcript field accepts up to 6,000 characters while the planner's overall context cap stays unchanged.

After recording, browser-local playback lets the contributor distinguish capture from recognition failure. That recording is retained only in the current tab until saving, replacement, leaving the editor/session, or closing the tab. It is not added to the durable session store. Stop pauses playback; cancelled capture is discarded. The server still removes its temporary recognition WAV. Coarse duration/level/trim measurements live in the transient job result without storing the source audio.

A provisional answer keeps its historical question available for replay. **Record again** can replace unchanged provisional wording without erasing the old attempt first; recognition failure preserves the previous wording. **Discard this attempt** removes only provisional content from the current draft and retains it in the ordered history. Confirmed contributions require correction rather than discard. Finishing remains disabled until provisional material is confirmed or discarded.

Verification: **527 isolated backend tests**, **77 speech-environment tests**, **10 Node capture/control tests**, Ruff, JS syntax and the Atlas frontend build passed. Browser inspection verified question replay/retry enabled for the retained Human attempt and enumerated headset/audio-interface choices, with a clean console. [Live synthetic audio evidence](evidence/2026-09-19/recording-fix.json) shows silence rejected before inference and a 41.699-second recording with speech after second 35 recognised correctly after trimming, including £15,000/not-£50,000 and before/not-after. No physical-microphone success is inferred from those synthetic checks. The requested next evidence is a ten-second headset recording with input-meter, playback and transcript comparison; #1520 remains Active pending that result and the wider acoustic criteria.


## Contextual follow-ups — 19 September 2026

The Human confirmed the recording fix works over multiple questions, but reported that follow-ups ignored the answers. The initial planner selected topics while the ledger always read a fixed bank question. Policy `synthetic-interview-v2` now assesses 14 specific details across up to 12,000 characters of current confirmed contributions. The model selects immutable source-sentence IDs; code checks their bounds and attribution before choosing an unanswered detail and building its spoken question. Provisional text remains excluded. Sentence splitting preserves decimal amounts; long excerpts end at sentence/word boundaries for playback.

For example, after “We recorded the decision in the ERP”, the next question can be “What changed in the supplier record when activation was authorised?” Ownership already supplied elsewhere is not asked again. Detail-level history prevents repeated prompts within a topic. Legacy broad-question sessions remain readable and retain their prior history. New contributions record the exact question ID, preventing replay from selecting a different follow-up with the same topic key. Corrections invalidate analysis and current-revision anchor checks reject stale plans.

Explicit unknowns remain open, with a bounded question about who or what could clarify them. They are labelled in the sidebar and retained as open points in the draft. Hypotheticals and proposals remain illustrative and do not satisfy factual-practice coverage. If planning times out or fails validation, the app says follow-up is pending and offers retry/review; it does not mask failure by repeating a generic topic prompt. The model cannot create tools or arbitrary question wording: speech is assembled from checked templates plus attributed participant excerpts. Semantic categorisation is still fallible and is not factual validation.

The chosen local dialogue model is now **Qwen 2.5 14B Instruct**, already installed on this Mac; no model download or hosted inference was added. The [compact 7B comparison](evidence/2026-09-19/contextual-7b-comparison.json) avoided repeating supplied details but wrongly counted decision criteria as covered and reviewed early. The [final 14B multi-turn probe](evidence/2026-09-19/contextual-multiturn.json) asked all five intentionally missing details without repeating the nine supplied details, then offered review. Six model turns took **2.542–3.002 seconds**; all 40 turn checks passed. The [six edge-case probes](evidence/2026-09-19/contextual-edge-cases.json) also returned validated local-model plans with all 30 structural checks passing. These are exploratory development scenarios, not held-out G2 acceptance or proof of general conversational quality. The earlier 7B source-copy and first cold 14B attempts failed validation/timing; compact source-ID selection replaced that approach.

The basic physical microphone retest is now positive. The separate one-penny recognition issue and wider acoustic measurements remain open under #1520. This iteration leaves capture and Voice B unchanged. #1524 remains Active for broader conversational acceptance and scoped evidence clarification; no Human gate is closed. Next Human check: refresh, reopen/resume or start a fresh fictional interview, describe several details at once, and assess whether follow-ups explore genuine gaps instead of asking for the same information.


Verification for this increment: **543 isolated backend tests**, **93 speech-environment tests**, **10 Node control tests**, Ruff, JavaScript syntax, diff whitespace checks and the Atlas frontend build passed. The [typed browser trial](evidence/2026-09-19/contextual-browser.json) verified contextual ERP/check-evidence questions, explicit unknown handling, draft preservation and layout with no console errors or warnings. The service was restarted with saved sessions retained. A sentence-boundary polish prevents spoken excerpts ending mid-word; automated regression includes decimal amounts and long answers.
