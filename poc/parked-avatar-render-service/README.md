# Parked Local Avatar Render Service Experiment

Status: parked on 2026-06-26 by Human decision.

This folder preserves the local OpenVoice/MuseTalk avatar-render service spike for future reference only. It is intentionally outside the active `services/` and `tests/` trees so normal application development, pytest runs and service startup paths are not affected.

Why parked:

- The cost and research effort to approach AnamLab-like avatar performance is currently higher than continuing with the AnamLab licence.
- MuseTalk was judged unsuitable as the primary renderer for AnamLab-like realtime facial motion because it is mainly a lip-sync component and still needs CUDA/NVIDIA infrastructure plus additional head/eye/expression motion work.
- Generated avatar media, user-owned images, voice samples, model checkpoints and runtime clones must remain outside git.

Contents:

- `services/avatar_render/` - parked FastAPI service shell, benchmark harness and runtime wrappers.
- `tests/` - parked regression tests for the service shell and wrappers. These are not part of the default project test suite.
- `docs/local-avatar-render-service-spike.md` - historical spike proposal and benchmark notes.

To revive later, move the service back under the active `services/` tree, move/enable the tests deliberately, refresh renderer research, and reopen the parked ADO items instead of quietly depending on this code from the main app.
