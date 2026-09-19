# Research and technology options

**Primary-source desk research checked 19 September 2026.** No candidate voice model was installed or benchmarked during discovery. Published performance numbers are authors' results under their conditions, not measurements on the user's hardware. Exact package versions, weight revisions, voices and dependency licences must be recorded in the audition manifest before implementation selection.

## Conclusions

A modular speech pipeline best fits the need for inspectable claims, controlled questioning and governed publication. Natural interaction also requires endpoint detection, interruption handling, echo control, concise language and a respectful policy; changing TTS alone cannot deliver it. An end-to-end speech model is a future experiment after an inspectable baseline exists.

Use Kokoro as the lightweight reference and select one expressive challenger according to hardware: Chatterbox Turbo/Nano for an English trial or Qwen3-TTS 1.7B CustomVoice for instruction-controlled delivery where resources permit. Include VibeVoice Realtime only as a research comparison until its model-card intended-use language is reviewed. Keep an adapter so the winning model can change independently of Atlas.

## Local text to speech

| Candidate | Primary evidence and licence signal | Fit and limitation | Proposed disposition |
|---|---|---|---|
| Kokoro-82M v1.0 | [Author model card](https://huggingface.co/hexgrad/Kokoro-82M): 82M parameters, Apache-2.0 weights; pipeline yields audio segments | Small baseline with existing voices; no demonstrated conversational policy or arbitrary emotional control. Segment output is not proof of token-level low-latency streaming | First reference candidate; “Kika” is plausibly Kokoro but earlier board-game use is unverified |
| Chatterbox Turbo / Nano | [Maintainer repository](https://github.com/resemble-ai/chatterbox), [Turbo weights](https://huggingface.co/ResembleAI/chatterbox-turbo), [Nano weights](https://huggingface.co/ResembleAI/chatterbox-nano): MIT; 350M / 110M; paralinguistic tags | English-focused expressive candidates. Reference-voice rights, watermarking, cancellation and actual playback latency need checking. Nano's CPU speed claim is not our end-to-end result | Compare Turbo on suitable acceleration, Nano where CPU/memory constrains the trial |
| Qwen3-TTS | [Maintainer repository](https://github.com/QwenLM/Qwen3-TTS), [1.7B CustomVoice card](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice): Apache-2.0; 0.6B/1.7B family, ten languages | 1.7B CustomVoice offers instructed style and nine preset timbres. Do not assume the 0.6B variants offer the same instruction control. Published 97 ms synthesis claim excludes our complete conversation path; verify actual streaming API in the chosen runtime | Strong expressive challenger, subject to simultaneous ASR/LLM memory and latency |
| VibeVoice-Realtime-0.5B | [Microsoft model card](https://huggingface.co/microsoft/VibeVoice-Realtime-0.5B): MIT label, streaming text, roughly 300 ms hardware-dependent audible latency | English single-speaker output. Card also limits intended use to research and advises further work before real-world deployment; do not interpret the MIT label alone as deployment clearance | Research comparator, not default enterprise selection |
| Chatterbox Flash | [Maintainer repository](https://github.com/resemble-ai/chatterbox-flash): MIT, inference-only block-diffusion release with streaming and optional MLX backend | Interesting local/Apple route, but dependency compatibility and implementation maturity need separate evaluation | Watchlist; do not expand the first audition indefinitely |

Licence labels describe the inspected release, not a blanket statement covering voice recordings, transitive packages or later checkpoints. Use a supplied licensed synthetic/preset voice initially. Voice cloning is not needed. Retain any required attribution and watermarking. No paid TTS API, Anam call or browser cloud speech-recognition fallback is part of the new runtime.

**Selection method:** compare three voices/configurations at most in the first round, using the same question/challenge text. Score naturalness 25%, listening comfort 20%, pronunciation/fidelity 20%, warm latency and cancellation 20%, hardware footprint 10%, deployment/licence clarity 5%. These are proposed preference weights. Content fidelity, local operation, authorised voice use and interruption correctness are mandatory gates regardless of the weighted score. Do not rank the models from marketing claims.

## Recognition, turn detection and dialogue model

| Component | Evidence | Recommendation and experiment |
|---|---|---|
| whisper.cpp | [Maintainer repository](https://github.com/ggml-org/whisper.cpp) documents CPU, Apple Metal/Core ML, quantisation and streaming examples; MIT implementation | First ASR runtime candidate for Apple Silicon. Compare a smaller English model with a more accurate larger model. Sliding-window examples need transcript stabilisation; do not call them perfect streaming recognition |
| faster-whisper | [SYSTRAN repository](https://github.com/SYSTRAN/faster-whisper) uses CTranslate2, CPU/int8 or CUDA paths and VAD integration | Alternative for x86/NVIDIA. Its reported benchmark speeds are workload-specific. Apple acceleration is not interchangeable with CUDA |
| Qwen3-ASR 0.6B/1.7B | [Maintainer repository](https://github.com/QwenLM/Qwen3-ASR) documents multilingual recognition and vLLM streaming | Candidate if recognition quality warrants extra runtime complexity. Official streaming currently excludes returned timestamps and batching; create independent audio sequence/timing records and evaluate later alignment |
| Silero VAD | [Maintainer repository](https://github.com/snakers4/silero-vad) supplies local speech-activity detection under MIT | Detect speech presence; do not equate silence with completed meaning. Combine with pause tolerance, transcript stability and explicit controls |
| Local dialogue LLM | Existing Atlas Qwen2.5 7B baseline; [Qwen3-4B-Instruct-2507 card](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507) is Apache-2.0 and non-thinking | Compare a bounded interview prompt against a smaller non-thinking candidate. Keep Atlas's configured model unchanged. Pin quantisation and context, and measure concurrent resource contention |
| Structured generation | [Ollama structured-output documentation](https://docs.ollama.com/capabilities/structured-outputs) supports JSON schemas | Validate generated claim/action structures server-side. Schema-valid JSON does not prove factual correctness or permission |

ASR evaluation must include accents, hesitations, domain acronyms, numbers, dates, negation, silence, noise and self-corrections. Confirm high-impact uncertainty explicitly. Do not imply model confidence values are calibrated probabilities. Keep partial and final transcript revisions so a later correction cannot leave an obsolete “contradiction” active.

The Human subsequently confirmed Mac Studio M4 Max (16-core CPU, 40-core GPU, 64 GB unified memory). Parameter counts are not memory budgets: weights, quantisation, KV caches, audio buffers, model concurrency and Atlas load all matter. On a constrained machine, prefer one small live model and queue deeper reasoning after the interview. A local GPU server is an option only after the user confirms availability; no purchase is recommended before measured results.

## Audio transport and service framework

[Pipecat](https://github.com/pipecat-ai/pipecat) offers a local orchestration candidate. Its [Small WebRTC transport](https://docs.pipecat.ai/api-reference/server/services/transport/small-webrtc) is suitable to investigate for a browser-to-service session. Use only locally configured processors and audit defaults for cloud integrations. A small custom WebSocket/AudioWorklet path is a fallback if framework complexity outweighs the benefit; it requires explicit buffering, resampling, cancellation and backpressure.

[Self-hosted LiveKit](https://docs.livekit.io/transport/self-hosting/) is an alternative for later multi-party or networked media. It adds media-server operations and should not become a dependency merely to support one localhost participant. Cloud LiveKit/Daily services are not required by the recommendation.

Browser microphone access needs user permission and a secure context; localhost is treated specially. This affects later LAN deployment and HTTPS, rather than allowing a generic HTTP host to capture audio. [MDN getUserMedia](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia).

## Interview psychology and knowledge elicitation

The useful pattern is collaborative elicitation: obtain a free account, clarify meaning, introduce contrary evidence without accusation, and confirm the summary. The [College of Policing interviewing guidance](https://www.college.police.uk/app/investigation/investigative-interviewing/investigative-interviewing) describes planning, engagement, account/clarification/challenge, closure and evaluation, and recommends avoiding interruptions during an open account. This supports an explicit free-narrative mode before focused challenge. It does not justify importing a suspect-interrogation setting into an SME interview.

[Open-question guidance](https://www.college.police.uk/guidance/obtaining-initial-accounts/witnesses-own-words-and-open-questioning) and [rapport guidance](https://www.college.police.uk/guidance/obtaining-initial-accounts/rapport-building) support own-word accounts and meaningful two-way interaction. The rapport evidence includes substantial laboratory research, so transfer to AI-led workplace interviews remains an inference requiring user evaluation.

[Edmondson's original team study](https://dash.harvard.edu/entities/publication/13a7b031-0fdd-45ec-a7e0-2b80e2bc679f) associates psychological safety with learning behaviour in 51 work teams. It does not prove that friendly synthetic speech creates safety. Product implications proposed here are voluntary correction, explicit unknowns, accountable use restrictions and no individual performance ranking.

Reflective listening and open questions from [SAMHSA's TIP 35](https://library.samhsa.gov/sites/default/files/tip-35-pep19-02-01-003.pdf) inform paraphrase/confirmation, with an important boundary: the interviewer is gathering knowledge, not treating or persuading a person. The [Méndez Principles](https://www.apt.ch/our-prioritiesdignity-and-fairness-criminal-justice-system/principles-effective-interviewing) offer a further non-coercive information-gathering reference. Neither source establishes our product's effectiveness.

For tacit knowledge, use a concrete recent example, then ask what cues, exceptions, decisions, trade-offs and hand-offs mattered. This is a proposed application of cognitive task analysis, supported by the purpose described in the [MIT Press overview of Working Minds](https://mitpress.mit.edu/9780262033510/working-minds/). Published process policy, actual reported practice and desired future practice must remain separate claim types.

## Optional Perlego reading

**Follow-up:** three local PDFs were supplied after this desk research. Relevant sections have now been read; the [reading record](10-readiness-and-reading.md) identifies the actual editions, the partial SAGE export and policy refinements. The recommendations below preserve the original requested titles; do not confuse them with the supplied editions.

Public sources are sufficient for the first design decision. No paid access blocks G0. If available through the user's subscription, the highest-value follow-up is **Working Minds** (Crandall, Klein and Hoffman), focusing on eliciting expertise and decisions. Then **InterViews**, third edition (Brinkmann and Kvale), for interview craft and validation ([publisher](https://us2.sagepub.com/en-us/nam/node/57995/print)); and **Motivational Interviewing**, fourth edition (Miller and Rollnick), for reflective listening and autonomy ([publisher](https://cms.guilford.com/books/Motivational-Interviewing/Miller-Rollnick/9781462552795)).

At the initial desk-research stage, Perlego availability and full chapters had not been checked. Ask the user for reading notes or permitted relevant excerpts, not an unnecessary full-library export. An optional Human task and a follow-on research task are in the backlog. Do not cite these books as read in full.

## Privacy and participant trust

The earlier academic boundary excluded identifiable new interviews. Live voice can be personal data even when the process script is synthetic. Before involving other people, confirm participant information, purpose, data-controller responsibilities, lawful basis, access, recording choice, retention and deletion, with the appropriate organisational owner.

[ICO worker-monitoring guidance](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/employment/monitoring-workers/data-protection-and-monitoring-workers/) notes that employment consent is often unsuitable because of power imbalance and requires a DPIA for likely high-risk processing. Its [audio-monitoring guidance](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/employment/monitoring-workers/specific-data-protection-considerations-for-different-ways-or-methods-of-monitoring-workers/) calls for particular care with intrusive recording. The proposed product response is explicit session initiation, no passive workplace recording, raw-audio storage off by default and a real-data gate; this is not a completed legal assessment.

## Meeting channels and desk hardware

Teams is not simply a microphone toggle. Microsoft's [application-hosted media-bot requirements](https://learn.microsoft.com/en-us/microsoftteams/platform/bots/calls-and-meetings/requirements-considerations-application-hosted-media-bots) describe C#/.NET media components and production Windows Server hosting in Azure. This is a material operational difference from the local browser PoC and requires tenant/admin investigation before commitment.

The [Webex Browser SDK](https://developer.webex.com/meeting/docs/sdks/browser) exposes meeting audio/video capabilities. Platform real-time transcripts require an eligible paid assistant licence; they are not required for local ASR. A separate spike must check participant permissions, supported media access and tenant policies. Neither platform adapter is implemented or authorised to join meetings by this proposal.

Prefer purpose-designed open hardware over assuming an Amazon Echo can be reflashed. No supported Echo firmware-replacement path was established in this research; model-specific experimentation is not a delivery dependency. Two candidates for later evaluation are:

- [Home Assistant Voice Preview Edition](https://www.home-assistant.io/voice-pe/): documented open firmware, local audio processing, physical microphone power cut-off, speaker and status controls. It is an endpoint requiring a host; conversational full-duplex performance needs testing.
- [ReSpeaker XVF3800](https://wiki.seeedstudio.com/respeaker_xvf3800_introduction/): USB microphone-array and echo-processing route for a host computer. An [external speaker is required](https://wiki.seeedstudio.com/respeaker_xvf3800_faq/). Verify the exact variant, firmware and audio path before buying.

A desk device should expose listening, muted, processing and request-to-speak states with text/audio equivalents; a red light must not mean “the human is wrong.” Holographic projection stays an aspiration without a procurement or engineering commitment.

## Research limitations and next evidence

Desk research establishes viable options, not a winner. Remaining evidence is target-hardware latency under Atlas load; pronunciation and comfort preferences; interruption precision; semantic conflict false positives; publication durability; licensed deployment manifests; and pilot feedback. The backlog assigns each experiment and the decisions it informs. Refresh the shortlist at the implementation gate because model releases and SDK constraints can change.
