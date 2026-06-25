# Local Avatar Render Service

Independent FastAPI microservice boundary for local Avatar Lab rendering and voice synthesis.

This service is deliberately render-only. It does not call the main assistant API, perform retrieval,
generate answers, rewrite answers, inspect source documents, run tools, or act as an agent. The main
Knowledge Assistant must call its canonical answer flow first, then send only approved speech text to
this service.

## Current status

Spike 1 implements the API and safety contract only:

- health and model readiness endpoints
- speech-only Pydantic request models
- rejection of raw question, document, prompt, message and conversation-history payloads
- explicit unavailable responses for TTS and rendering until local models are installed
- local data path reporting for future voice profiles, avatar assets and render artifacts
- offline benchmark readiness and manifest generation for the next OpenVoice/MuseTalk slice

MuseTalk, OpenVoice and WebRTC are not wired yet.

## Run Locally

From the repository root:

```bash
.venv/bin/python -m uvicorn services.avatar_render.app:app --host 127.0.0.1 --port 5400 --reload
```

Health check:

```bash
curl http://127.0.0.1:5400/health
```

Model readiness:

```bash
curl http://127.0.0.1:5400/models
```

OpenAPI docs:

```text
http://127.0.0.1:5400/docs
```

## Offline benchmark

The benchmark endpoint creates a local manifest under `data/avatar/benchmarks/` and confirms whether
the machine has enough local configuration to run OpenVoice and MuseTalk commands.

Readiness-only run:

```bash
curl -X POST http://127.0.0.1:5400/benchmarks/offline \
  -H "Content-Type: application/json" \
  -d '{
    "speech_id": "avatar-benchmark-001",
    "text": "Supplier setup requires due diligence checks before onboarding [1].",
    "style": "natural",
    "voice_profile_id": "chriser-local-v1",
    "avatar_profile_id": "default-local-avatar",
    "render_mode": "offline",
    "run_commands": false
  }'
```

To execute local model commands later, configure command templates in the service environment and
explicitly allow execution:

```bash
export AVATAR_BENCHMARK_ALLOW_EXECUTE=1
export OPENVOICE_REPO_DIR=/absolute/local/OpenVoice
export OPENVOICE_CHECKPOINTS_DIR=/absolute/local/OpenVoice/checkpoints_v2
export MUSETALK_REPO_DIR=/absolute/local/MuseTalk
export AVATAR_TTS_COMMAND='.venv/bin/python -m services.avatar_render.runtime_wrappers.openvoice_tts --text-file {text_path} --voice-profile-id {voice_profile_id} --data-root {data_root} --output {audio_path}'
export AVATAR_RENDER_COMMAND='.venv/bin/python -m services.avatar_render.runtime_wrappers.musetalk_render --audio {audio_path} --avatar-profile-id {avatar_profile_id} --data-root {data_root} --output {video_path}'
```

Supported template variables:

- `{text_path}`
- `{audio_path}`
- `{video_path}`
- `{data_root}`
- `{run_dir}`
- `{speech_id}`
- `{style}`
- `{voice_profile_id}`
- `{avatar_profile_id}`

## Runtime wrapper profiles

The built-in wrappers are thin adapters around local external checkouts. They do not download
models, commit assets, or call external services.

OpenVoice voice profiles live outside git under:

```text
data/avatar/voice_profiles/{voice_profile_id}.json
```

Example:

```json
{
  "reference_audio_path": "/absolute/local/avatar-assets/voice/chriser-reference.wav",
  "language": "EN_NEWEST",
  "speaker_key": "en-newest",
  "speed": 1.0
}
```

MuseTalk avatar profiles live outside git under:

```text
data/avatar/avatar_profiles/{avatar_profile_id}.json
```

Example:

```json
{
  "source_video_path": "/absolute/local/avatar-assets/video/chriser-avatar-source.mp4",
  "version": "v1.5",
  "mode": "normal",
  "bbox_shift": 0
}
```

The wrappers expect these local runtime checkouts:

- OpenVoice V2 installed from `myshell-ai/OpenVoice`, with checkpoints under `checkpoints_v2`.
- MeloTTS installed in the same Python environment as OpenVoice.
- MuseTalk 1.5 installed from `TMElyralab/MuseTalk`, with weights arranged under `models` as the project documents.
- ffmpeg available on PATH, or `MUSETALK_FFMPEG_PATH` set where the MuseTalk runtime requires it.

Minimal local setup checklist:

```bash
# Outside this repository, in a local models/runtime area:
git clone https://github.com/myshell-ai/OpenVoice.git /absolute/local/OpenVoice
git clone https://github.com/TMElyralab/MuseTalk.git /absolute/local/MuseTalk
```

Then, following the upstream projects:

1. Install OpenVoice in its own Python environment and install MeloTTS.
2. Download OpenVoice V2 checkpoints into `/absolute/local/OpenVoice/checkpoints_v2`.
3. Install MuseTalk in its own compatible Python/CUDA environment.
4. Run MuseTalk's weight download script or place the documented weights under `/absolute/local/MuseTalk/models`.
5. Create the local voice/avatar profile JSON files under `AVATAR_RENDER_DATA_DIR`.
6. Run `/benchmarks/offline` first with `"run_commands": false`, then with `"run_commands": true` only after the readiness report is clean.

## Local data

By default the service reports `data/avatar` as its local data root. The whole `data/` directory is
already git-ignored in this project.

To use another path:

```bash
AVATAR_RENDER_DATA_DIR=/absolute/local/path .venv/bin/python -m uvicorn services.avatar_render.app:app --host 127.0.0.1 --port 5400
```

Use this override when running inside a restricted sandbox or when the default `data/` directory is
not writable by the service process.

Do not commit voice samples, cloned voice profiles, avatar source assets, model weights, rendered
clips or benchmark outputs.

## Speech-only render contract

Valid shape:

```bash
curl -X POST http://127.0.0.1:5400/avatar/render \
  -H "Content-Type: application/json" \
  -d '{
    "speech_id": "avatar-demo-001",
    "text": "Supplier setup requires due diligence checks before onboarding [1].",
    "style": "natural",
    "voice_profile_id": "chriser-local-v1",
    "avatar_profile_id": "default-local-avatar",
    "render_mode": "offline",
    "metadata": {
      "source": "knowledge-assistant",
      "answer_id": "demo-answer"
    }
  }'
```

In Spike 1 this returns `503 renderer_not_configured` because MuseTalk is not wired yet. That is
expected. The request still proves the boundary: approved speech text can enter the service, but the
service cannot answer a question.

Rejected shape:

```json
{
  "question": "How do I set up a supplier?",
  "documents": ["..."],
  "conversation_history": ["..."]
}
```

Raw questions and source material must stay in the main app's canonical validated answer flow.

## Next integration step

The next build slice is the offline model benchmark:

1. Install OpenVoice in an isolated local/runtime environment.
2. Install MuseTalk 1.5 in an isolated local/runtime environment.
3. Generate a local WAV from approved speech text.
4. Render an MP4 from the WAV and a user-owned avatar asset.
5. Measure first-frame time, render time, fps, VRAM, quality, identity drift and jitter.
