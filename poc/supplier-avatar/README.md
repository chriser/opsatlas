# Supplier Setup Process Assistant (DT602 PoC)

A local proof-of-concept talking avatar application for a DT602 research ethics
project. The assistant answers spoken questions about an **anonymised supplier
setup and supplier master data maintenance process**.

- **ElevenLabs Conversational AI** (pre-configured agent) handles the
  microphone, speech-to-text, RAG retrieval over the approved anonymised
  knowledge base, answer generation and voice synthesis.
- **Anam** (pre-configured custom avatar) handles avatar rendering and
  real-time lip-synced speech of the agent's responses.
- **This app** is the local glue: a small Express server plus a static
  browser page that connects the two services.

## Architecture

```
Browser (public/index.html, app.js)
  |  microphone audio            agent text responses
  |  <-- ElevenLabs SDK -->        --> Anam SDK (avatar speaks with lip sync)
  |
  |  /api/config                 which mode? (live / mock)
  |  /api/elevenlabs/signed-url  short-lived agent connection URL
  |  /api/anam/session-token     short-lived avatar stream token
  v
Express server (src/server.js)  <-- .env (API keys never reach the browser)
  |-- src/elevenlabs.js   ElevenLabs REST call (signed URL)
  |-- src/anam.js         Anam REST call (session token)
  `-- src/config.js       loads .env, decides live vs mock mode
```

## Single source of truth: ElevenLabs answers, Anam renders

- **ElevenLabs is the only answering and RAG source.** Its agent (configured
  with the approved anonymised knowledge base and guardrails) handles the
  microphone, speech-to-text, retrieval and answer generation.
- **Anam is used only for avatar rendering and speaking.** The Anam client is
  created with `disableInputAudio: true`, so the persona never receives the
  microphone and its own LLM/persona brain is never triggered. The avatar can
  only speak text this app explicitly sends it via `talk()`, which renders
  text verbatim without invoking Anam's reasoning.
- **The app deliberately waits for the ElevenLabs answer** before the avatar
  speaks it. A browser-side state machine
  (`idle -> listening -> waiting_for_elevenlabs -> speaking_answer`) enforces
  one answer pipeline and prevents overlapping avatar speech.
- **A short delay (roughly 3-5 seconds) is expected** after each question:
  RAG retrieval and answer generation happen before avatar rendering. During
  this window the status shows *"Checking approved process documentation"*
  and the avatar speaks one short holding phrase.
- **The waiting phrase is controlled locally** (hard-coded in
  `public/app.js`, see `WAITING_FILLER_PHRASE`); it is not an Anam-generated
  answer and never addresses the question itself. If it ever causes unwanted
  behaviour it can be disabled with `SPEAK_WAITING_FILLER = false`.
- **On an ElevenLabs error** the avatar does not invent a fallback; it states
  a fixed local phrase asking the user to try again.

Design notes:

- **Credential broker pattern**: API keys live only in `.env` on the server.
  The browser receives only short-lived credentials (a signed URL valid
  ~15 minutes; a one-session avatar token).
- **Single voice**: the ElevenLabs agent generates speech, but the app mutes
  it locally and the Anam avatar voices the answer text instead, so audio and
  lips stay in sync. Flip `MUTE_ELEVENLABS_AUDIO` in `public/app.js` to hear
  the ElevenLabs voice instead.
- **Stateful persona session**: Anam Lab exposes a *Persona ID* for both
  custom and stock characters. The server requests a session token with
  `personaConfig: { personaId }` (a stateful persona session), rather than
  the ephemeral runtime configuration (`avatarId`/`voiceId`/`llmId`), which
  remains available only as a legacy fallback via `ANAM_AVATAR_ID`.
- **Isolated integrations**: if either vendor changes its API, the only files
  to update are `src/elevenlabs.js`, `src/anam.js` and the marked
  "Integration settings" section at the top of `public/app.js`.
- **Mock mode**: with no credentials, the app still runs and plays a scripted
  Q&A so the interface can be demonstrated offline.

## Project structure

```
package.json        dependencies and start script
.env.example        template for credentials (copy to .env)
.gitignore          excludes node_modules and .env
src/server.js       Express server and API routes
src/config.js       environment loading, live/mock decision
src/elevenlabs.js   ElevenLabs signed-URL integration
src/anam.js         Anam session-token integration
public/index.html   page: title, avatar area, buttons, status, transcript
public/styles.css   styling
public/app.js       browser logic: SDK wiring, mock mode, transcript
```

## Setup (Windows PowerShell)

Requires Node.js 18 or newer.

```powershell
# 1. Install dependencies
npm.cmd install

# 2. Create your local credentials file (never committed)
Copy-Item .env.example .env
#    ...then edit .env and fill in the four credential values.

# 3. Start the server
npm.cmd start
```

Open http://127.0.0.1:5180 in Chrome or Edge.

- With **no credentials** in `.env`, the app starts in **mock mode** and says so.
- With **all four credentials** set, the app starts in **live mode**: press
  *Start Conversation*, allow microphone access, and speak.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `ELEVENLABS_API_KEY` | ElevenLabs account API key (server-side only) |
| `ELEVENLABS_AGENT_ID` | ID of the published Conversational AI agent |
| `ANAM_API_KEY` | Anam Lab API key (server-side only) |
| `ANAM_PERSONA_ID` | Persona ID of the character configured in Anam Lab |
| `ANAM_AVATAR_ID` | Optional legacy fallback, only used if no persona ID is set |
| `ANAM_VOICE_ID` | Optional: Anam voice (fallback mode only) |
| `PORT` | Local port, defaults to 5180 |

## Test checklist

Mock mode (no `.env` or empty values):

- [ ] `npm.cmd start` prints `Mode: MOCK` and lists the missing credentials.
- [ ] http://127.0.0.1:5180 loads and shows the title "Supplier Setup Process Assistant".
- [ ] A yellow banner explains mock mode and which credentials are missing.
- [ ] *Start Conversation* plays a scripted Q&A in the transcript.
- [ ] The status pill cycles Idle → Connecting → Listening → Assistant speaking.
- [ ] The placeholder avatar circle pulses while the mock assistant "speaks".
- [ ] *Stop Conversation* halts the script and returns the status to Idle.

Live mode (all credentials in `.env`):

- [ ] `npm.cmd start` prints `Mode: LIVE`.
- [ ] *Start Conversation* asks for microphone permission.
- [ ] The Anam avatar video appears in the avatar area.
- [ ] Speaking a question shows your transcript as a "You" message.
- [ ] After the question, the status shows "Checking approved process
      documentation" and the avatar says only the short holding phrase.
- [ ] The avatar does NOT start answering the question on its own while
      waiting (Anam input audio is disabled).
- [ ] The agent's answer appears as an "Assistant" message and the avatar
      speaks it with lip sync ("Speaking approved answer" status).
- [ ] The agent answers only from the anonymised knowledge base (try an
      off-topic question - it should decline rather than invent an answer).
- [ ] *Stop Conversation* ends the session and the avatar stream.
- [ ] DevTools console (F12) and the server terminal show step-by-step logs.

## Troubleshooting

- **"Mock mode" although .env exists** - restart the server after editing
  `.env`; values are read once at startup. Check for typos in variable names.
- **No microphone prompt** - use Chrome/Edge on `http://127.0.0.1:5180`
  (browsers treat 127.0.0.1 as a secure origin; other hostnames need HTTPS).
- **400 Bad Request from Anam when starting a session** - check that the ID
  you copied from Anam Lab is a **Persona ID** and that `.env` sets it as
  `ANAM_PERSONA_ID` (not `ANAM_AVATAR_ID`). Anam Lab exposes Persona IDs for
  created characters; raw avatar IDs only work in the legacy fallback mode.
- **Avatar connects but does not speak** - the Anam SDK method used to send
  text is in `avatarSay()` in `public/app.js`; check the browser console and
  the current Anam docs (https://anam.ai/docs) if the SDK surface changed.
- **Agent connection fails** - confirm the agent is published and the signed
  URL endpoint in `src/elevenlabs.js` matches the current ElevenLabs docs.

## Ethics and scope guardrails

The ElevenLabs agent is configured (server-side, in the ElevenLabs dashboard)
to answer only from the approved anonymised knowledge base, to refuse to
invent or fuzzy-match answers, to withhold real supplier/employee/system
names and commercial data, and to explain - but never approve or decide -
supplier onboarding steps. This application adds no knowledge of its own; it
only transports questions and answers.
