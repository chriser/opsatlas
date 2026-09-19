# G0 acceptance, hardware and supplied reading

**19 September 2026, follow-up to the initial design publication.** The Human said they were happy with the design agreement and supplied the target hardware and three reading files. This records G0 acceptance for the initial isolated synthetic trial. G1 voice/model selection and the later publication and real-participant gates remain evidence-based decisions.

## Ready to begin the isolated trial

The accepted starting scope is the documented standalone local service, browser/headset, one English-speaking SME, synthetic supplier-activation fixture, and a staged review packet. The initial operator is the user; a real organisational process/owner is needed before the later pilot, not before the synthetic experiment. Raw audio remains transient by default. No new participant recruitment, enterprise-data ingestion or automatic Atlas publication is implied by this agreement.

Target supplied by the Human: **Mac Studio, M4 Max, 16-core CPU, 40-core GPU, 64 GB unified memory**. This is a credible target for evaluating the shortlisted small local speech models and a quantised dialogue model; concurrent latency and memory pressure must still be measured. Do not equate parameter count with total runtime memory or make a real-time guarantee from the specification alone.

Start with the Apple-compatible recognition path, Kokoro as the lightweight voice reference, and one expressive challenger from the existing shortlist. Limit the audition to three configurations. Benchmark the pipeline together with Atlas rather than choosing the largest model that fits in memory. Existing Atlas model/provider settings remain protected.

The setup story verifies host identity, macOS/runtime compatibility, free storage, available acceleration, microphone permission and the chosen audio device. The current workspace reports macOS 26.6.2, about 213 GiB free storage and an Ollama executable. Sandboxed CPU/memory queries were unavailable; the Mac Studio specification above is user-supplied, not independently measured. No model was downloaded or hardware benchmark run in this readiness update.

The Human selected a **British English female voice**. Use clear, warm professional delivery with no cloning. The remaining setup detail is the microphone/headset; warmth, pacing and the particular voice are compared in the audition. These do not block environment setup; the listening comparison resolves voice selection. The eventual real process/owner and participant controls remain G4 work.

## What was supplied and actually read

PDF page references below are one-based file pages. Files are local references in `books/`; neither source PDFs nor extracted text are committed or uploaded to the wiki. This is a focused reading, not a claim to have read every page of every book.

| File | Verified material | Reading used here |
|---|---|---|
| `working-minds-a-practitioners-guide-to-cognitive-task-analysis-bradford-books_compress.pdf` | Crandall, Klein and Hoffman, *Working Minds* (MIT Press, 2006), 347 PDF pages | Chapter 5, especially PDF pp. 84–89, 91–93, 95, 97–98 (printed pp. 69–74, 76–78, 80, 82–83) |
| `motivational-interviewing.pdf` | Miller and Rollnick, *Motivational Interviewing: Preparing People for Change*, **second edition**, 2002, 449 PDF pages; not the recommended fourth edition | Collaboration/autonomy and empathy, PDF pp. 55, 57–58; question–answer traps pp. 76–77; reflection and summaries pp. 90–91, 94–95 |
| `doing-interviews-2e.pdf` | Brinkmann and Kvale, *Doing Interviews*, second edition; SAGE export dated 2019, copyright 2018, **45-page extract**. Different title from *InterViews*, third edition | Front matter and chapter 1; particularly PDF pp. 25, 28–29. Chapters 2–12 appear in the contents but their chapter text is absent |

The missing *Doing Interviews* chapters on conducting, quality, transcription and validation would be useful later. They are optional additional reading, not a reason to delay G1. Do not attribute advice from those absent chapters or from MI's fourth edition to these supplied files.

## Translation into interview behaviour

The following are product adaptations, not evidence that a voice AI inherits the effectiveness of trained human interviewers.

| Reading observation | Product adaptation and rationale | Evaluation case |
|---|---|---|
| *Working Minds*, chapter 5, uses successive passes through a concrete incident: initial account, timeline, deeper decision probes and optional hypotheticals | Begin with a specific example; let the SME correct the event sequence before probing cues, goals, available information, alternatives and hand-offs. This sharpens the existing example-based policy | SME corrects event order; the new timeline replaces the old interpretation and invalidates dependent claims |
| The same chapter distinguishes what happened in the incident from general procedures and counterfactual questions | Tag actual account, policy, proposal and hypothetical separately. A “what if” answer never becomes evidence that an event occurred | An imagined exception stays hypothetical and cannot silently enter approved process facts |
| *Motivational Interviewing*, pp. 55, 57–58, separates respectful understanding from endorsement and stresses collaboration/autonomy | Acknowledge the contributor without affirming the truth of a claim. Do not use conversational persuasion to obtain consent or force agreement with existing Atlas evidence | SME declines or disputes a comparator; preserve the unresolved case and offer correction or deferral |
| MI pp. 76–77 and 90–95 explain question–answer traps, reflective responses and summaries | Alternate purposeful questions with faithful paraphrase and room to elaborate. Avoid formulaic question chains and excessive praise. Do not copy a clinical reflection/question ratio into a rigid product metric | Repeated short answers prompt a simpler reflection/open invitation; a mistaken paraphrase is corrected without defensiveness |
| *Doing Interviews*, chapter 1, links useful knowledge to preparation, active follow-up, context and ethical care | Prepare a bounded coverage plan; keep the SME's wording, the model's interpretation and owner approval distinguishable. A pleasant conversation alone is not validation | The system retains an accurate account even when its initial process interpretation changes |

The 20-minute prototype is an abbreviated application of these ideas. The full Critical Decision Method described in *Working Minds* can take around two hours and uses trained interviewers. We do not claim to implement or validate that complete method. The interviewer is not a therapist and does not use behaviour-change persuasion as its objective.

These refinements are recorded in [conversation policy v0.2](05-interview-experience.md). They preserve the approved architecture and become evaluation examples under Stories #1524 and #1526; they are not new implementation delivered in this update.

## Codex configuration recommendation

For engineering this system, use **Astra High** as a starting default; reserve **Astra Extra High** for difficult architectural trade-offs, concurrency/recovery bugs and deep integration review. Use Medium for bounded routine work, or evaluate Sol for clearly scoped implementation when usage efficiency matters. This is an engineering recommendation, not a measured cost-per-success result for this repository. No Codex setting was changed automatically.

OpenAI describes [Astra](https://developers.openai.com/api/docs/models/gpt-6-astra) as its most capable model. Its [reasoning guidance](https://developers.openai.com/api/docs/guides/reasoning) says lower effort favours speed/token efficiency and recommends Extra High where evaluation demonstrates enough quality benefit. [Model comparison](https://developers.openai.com/api/docs/models/compare) lists lower API token prices for Sol, but API prices do not establish Codex subscription usage multipliers or total task cost. Compare accepted changes, rework and time, not token price alone.

Codex model selection concerns the development assistant. OpsAtlas Interviewer's runtime continues to use local models under the agreed architecture.
