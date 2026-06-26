# Local Avatar Render Service Spike

Date: 2026-06-25

Status: Parked on 2026-06-26. Human decision: do not continue the local avatar renderer investment now because expected research/build/compute cost is higher than the AnamLab licence path.

## Goal

Replace the current Anam render dependency with a local, API-driven avatar service that can speak validated answer text using a locally cloned voice and a locally rendered human avatar.

The service must only own voice synthesis, lip/head/face motion generation, and media delivery. It must not own retrieval, answer generation, validation, refusals, citations, follow-up logic, or agent behaviour.

## Why this is a separate service

The existing Avatar Lab work deliberately treats Anam as a render-only surface. The open-source replacement should preserve that boundary:

- The main app remains the answer authority through the existing grounded answer flow.
- The local avatar service receives text that has already passed the canonical answer path.
- The local avatar service never accepts a raw user question as input.
- Refusals, citation markers, and validated answer wording must not be rewritten by the avatar service.
- When the local service is unavailable, Avatar Lab should show a clear unavailable state rather than falling back to an unvalidated answer path.

This follows the same local-service pattern as `services/process_diagram`: a separately runnable FastAPI service, local-only by default, health checked, deterministic at the API boundary, and optional from the main app perspective.

## Non-goals

- Build a new agent environment.
- Replace `AnswerService`.
- Add a second RAG, LLM, memory, or tool-calling path inside the avatar service.
- Use Anam, ElevenLabs, or another external SaaS as a production dependency for render or TTS.
- Commit user voice samples, model weights, generated voice profiles, or rendered private media to git.
- Treat Anam Cara 3 as a reusable local asset unless its export and licence rights are explicitly confirmed.

## Recommended Stack

### Service shell

- Python FastAPI service under `services/avatar_render`.
- Local-only default bind address, for example `127.0.0.1`.
- `GET /health` for dependency and model readiness.
- Docker profile for CUDA/NVIDIA machines once the first spike works.
- Local data directory such as `data/avatar/`, excluded from git, for voice profiles, avatar source assets, generated audio, rendered clips, and benchmark outputs.

### TTS and voice cloning

First candidate: OpenVoice.

OpenVoice is a strong first spike candidate because it supports tone colour cloning, style control, multi-lingual use, and its README states that V1 and V2 are MIT licensed and free for commercial and research use.

Second candidate: F5-TTS.

F5-TTS looks strong for quality and performance work. Its repository includes Triton/TensorRT-LLM runtime notes and reports low real-time factor on an L20 GPU. However, the README states that while code is MIT, pretrained models are CC-BY-NC because of the Emilia training data. That means it is useful for a technical benchmark, but not acceptable for production without a model/licence replacement decision.

Optional candidate: XTTS/Coqui-family stacks only after licence and maintenance checks. These should not be the first production choice unless the current licence and model terms fit the project.

### Avatar rendering

First candidate: MuseTalk 1.5.

MuseTalk is the right first rendering spike because it is explicitly built for audio-driven lip sync, supports real-time inference in its own pipeline, and publishes training/inference code plus model weights. Its README reports 30fps+ on an NVIDIA Tesla V100 and documents real-time inference commands.

Important limitation: MuseTalk is mainly a lip-sync/inpainting renderer over a face region. It is not automatically a complete Anam equivalent for head motion, eye motion, idle expression, gesture timing, or broader facial mimic control. The spike must measure whether MuseTalk alone feels alive enough, or whether it needs an additional motion layer.

Companion candidate: LivePortrait or a faster derivative.

LivePortrait is useful to investigate for head pose, eye/expression retargeting, idle motion, and reusable motion templates. It should be treated as a companion layer rather than the first lip-sync renderer. Licence and dependency review is required because some related face-analysis models can carry separate restrictions.

### Media transport

Spike transport: aiortc.

`aiortc` gives Python-native WebRTC audio/video/data channels and is a good fit for a local FastAPI-adjacent prototype where generated frames are streamed to the browser.

Production transport candidate: LiveKit.

LiveKit is better if we need multi-client rooms, reconnect behaviour, TURN/STUN, production observability, or future hosted deployment. For a local single-user Avatar Lab replacement, it is probably more infrastructure than the first spike needs.

## Proposed Service Boundary

The main app continues to handle the user question:

1. User asks a question in Avatar Lab.
2. Main app calls the canonical answer path.
3. Main app receives validated answer, citations, refusal state, and `rendered_text`.
4. Main app sends only the approved speech payload to the local avatar service.
5. Local avatar service produces audio/video media and completion events.
6. Avatar Lab displays the local rendered avatar and keeps the transcript/citations from the main app.

The avatar service receives a payload shaped like:

```json
{
  "speech_id": "avatar-2026-06-25-001",
  "text": "Validated text to speak, with citation markers preserved if present.",
  "style": "natural",
  "voice_profile_id": "chriser-local-v1",
  "avatar_profile_id": "default-local-avatar",
  "metadata": {
    "source": "knowledge-assistant",
    "answer_id": "optional-main-app-answer-id"
  }
}
```

It must not receive:

```json
{
  "question": "What should I do next?",
  "documents": ["..."],
  "conversation_history": ["..."]
}
```

## Draft API

### Health and model readiness

- `GET /health`
- `GET /models`

`/health` should include whether the TTS model, renderer model, FFmpeg, GPU/runtime, and local asset directories are available.

### Voice profiles

- `POST /voice/profiles`
- `GET /voice/profiles`
- `DELETE /voice/profiles/{profile_id}`

Voice enrollment should require explicit local action and store all samples/profile artefacts under ignored local data paths. The API should record consent metadata and sample provenance, but should not send any samples outside the machine.

### TTS

- `POST /tts/synthesize`

Returns either a completed WAV artifact or stream/chunk metadata. The response should include duration and any available word/phoneme timing metadata.

### Offline render

- `POST /avatar/render`
- `GET /avatar/render/{job_id}`
- `GET /artifacts/{artifact_id}`

This is the lowest-risk first proof because it lets us measure quality, latency, lip sync, GPU memory, and file output before debugging WebRTC.

### Realtime session

- `POST /avatar/sessions`
- `POST /avatar/sessions/{session_id}/speak`
- `POST /avatar/webrtc/offer`
- `DELETE /avatar/sessions/{session_id}`

The realtime API should return explicit lifecycle events:

- `queued`
- `tts_started`
- `tts_completed`
- `render_started`
- `first_frame`
- `speech_started`
- `speech_completed`
- `render_completed`
- `failed`

This gives Avatar Lab a better completion signal than the current vendor-event workaround.

## Spike Plan

### Spike 1: API and safety contract

Deliverables:

- FastAPI skeleton under `services/avatar_render`.
- `/health`, `/models`, and OpenAPI docs.
- Pydantic request/response models for speech-only payloads.
- Tests proving the service rejects raw question-shaped requests.
- Main-app integration note showing that Avatar Lab only sends `rendered_text`.

Acceptance:

- The avatar service has no RAG, LLM, search, tool-calling, or document-ingestion dependency.
- The API contract makes the render-only boundary visible.

### Spike 2: MuseTalk local renderer benchmark

Deliverables:

- Local MuseTalk runner wrapper.
- One user-owned avatar source clip or static avatar profile.
- Benchmark report for first-frame time, total render time, fps, VRAM, CPU/GPU use, and output quality.
- Output artifacts kept in ignored local data.

Acceptance:

- We know whether MuseTalk can hit at least 24-25fps on the target local hardware.
- We know whether MuseTalk alone covers enough facial movement for Avatar Lab, or whether a head/eye/expression layer is required.

### Spike 3: Local TTS voice profile benchmark

Deliverables:

- OpenVoice wrapper for local voice profile creation and synthesis.
- Same text rendered with Natural and Formal Avatar Lab styles.
- Latency and quality notes.
- Licence check captured beside the benchmark.

Acceptance:

- We know sample length/quality requirements for the user's own voice.
- We know whether OpenVoice is good enough for the first local service.
- F5-TTS is either parked as research-only because of pretrained model terms or moved forward only with a compliant model plan.

### Spike 4: End-to-end local render proof

Deliverables:

- Main app calls canonical answer service.
- Local avatar service renders the approved speech text.
- Avatar Lab displays a local rendered output in a preview mode.
- Citations/refusals remain owned by the main app transcript.

Acceptance:

- No answer content is generated or changed by the avatar service.
- A local answer can be spoken and rendered without Anam.
- Failure states are clear when the local service is stopped or model assets are missing.

### Spike 5: WebRTC realtime proof

Deliverables:

- aiortc session endpoint.
- Browser receives synchronized audio/video from the local service.
- Speech lifecycle events replace timer-only completion logic where possible.

Acceptance:

- Browser playback is stable for a normal answer length.
- Audio/video sync is acceptable.
- The service reports real completion, not only estimated duration.

## ADO-Ready Backlog Proposal

Feature: Local avatar render microservice spike.

User Story: Define local avatar API and safety contract.

- Task: Create `services/avatar_render` FastAPI skeleton.
- Task: Add health/model-readiness contract.
- Task: Add request validation that only accepts approved speech text.
- Task: Document main-app integration boundary.
- Test Case: Raw user-question payload is rejected by the avatar service.

User Story: Benchmark MuseTalk as the first local render engine.

- Task: Install and run MuseTalk 1.5 in an isolated local environment.
- Task: Prepare a user-owned avatar asset.
- Task: Measure fps, first-frame latency, render latency, VRAM, and quality.
- Task: Capture limitations for eyes, head motion, identity preservation, and jitter.
- Test Case: One validated answer is rendered into an artifact without Anam.

User Story: Benchmark local own-voice TTS.

- Task: Enroll an OpenVoice profile from local voice samples.
- Task: Synthesize Natural and Formal style answer text.
- Task: Measure synthesis latency and subjective similarity.
- Task: Record licence and consent controls.
- Test Case: No voice samples or generated profiles are committed to git.

User Story: Prove end-to-end local Avatar Lab playback.

- Task: Add a local provider option beside Anam in configuration.
- Task: Call the local avatar service with `rendered_text` only.
- Task: Display unavailable/model-missing states.
- Task: Preserve transcript citations and refusals in the main app.
- Test Case: Avatar playback cannot bypass canonical answer validation.

User Story: Prove realtime WebRTC playback.

- Task: Add aiortc offer/session endpoint.
- Task: Stream generated audio/video to the browser.
- Task: Emit lifecycle events for first frame and speech completion.
- Test Case: Avatar Lab receives a real completion event for a spoken response.

## Key Risks

- MuseTalk may only solve lip sync. Full Anam-like behaviour may need LivePortrait-style motion, a curated idle loop, or another expression/pose layer.
- Real-time performance probably depends on CUDA/NVIDIA hardware. Apple Silicon support may be much slower and should be measured, not assumed.
- F5-TTS pretrained models are not production-safe for commercial use under the current README licence statement.
- Voice cloning introduces consent, biometric, and misuse risk. The service needs explicit local enrollment and no automatic sample reuse.
- Model weights and generated artifacts can be large. They should stay outside git and be downloaded or prepared locally.
- Avatar identity quality depends heavily on the source asset. A low-quality avatar clip will make the whole service look worse regardless of model choice.

## Recommendation

Proceed with MuseTalk plus OpenVoice as the first local stack:

1. Build the FastAPI shell and render-only API contract.
2. Benchmark offline TTS plus MuseTalk render first.
3. Add WebRTC only after the local audio/video quality and latency are understood.
4. Add a motion/eye/head layer only if MuseTalk alone fails the quality bar.

This is the shortest path to replacing the Anam render dependency while staying aligned with the current ADO/Wiki architecture decisions.

## Research Sources

- [MuseTalk GitHub](https://github.com/TMElyralab/MuseTalk): real-time lip-sync renderer; README reports 30fps+ on NVIDIA Tesla V100, real-time inference commands, MIT code, commercially available trained model, and known limitations around resolution, identity preservation, and jitter.
- [MuseTalk technical report](https://arxiv.org/abs/2410.10122): technical background for the MuseTalk model family.
- [OpenVoice GitHub](https://github.com/myshell-ai/OpenVoice): tone cloning, style control, zero-shot cross-lingual voice cloning, MIT licence, and commercial/research use statement.
- [F5-TTS GitHub](https://github.com/SWivid/F5-TTS): high-quality TTS candidate with Triton/TensorRT-LLM runtime notes; README states pretrained models are CC-BY-NC.
- [aiortc GitHub](https://github.com/aiortc/aiortc): Python asyncio WebRTC/ORTC implementation with audio, video, and data channels; BSD licence.
- [LiveKit GitHub](https://github.com/livekit/livekit): open-source WebRTC server for scalable realtime audio/video/data; Apache-2.0 licence.
- [LivePortrait GitHub](https://github.com/KlingAIResearch/LivePortrait): portrait animation and motion template candidate for head/eye/expression motion if MuseTalk alone is insufficient.
