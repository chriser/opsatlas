// Frontend logic for the Supplier Setup Process Assistant PoC.
//
// Flow in LIVE mode:
//   1. Fetch /api/config to confirm credentials are present.
//   2. Start the Anam avatar stream (session token from our server).
//   3. Start the ElevenLabs conversation (signed URL from our server).
//      ElevenLabs handles: microphone, speech-to-text, RAG retrieval,
//      answer generation and voice synthesis. It is the ONLY answer source.
//   4. The app deliberately waits for the ElevenLabs final answer, then
//      forwards that text to the Anam avatar, which renders it with lip
//      sync. Anam's own microphone input and reasoning are disabled.
//
// Flow in MOCK mode: a scripted Q&A demonstrates the full interface
// without any external API calls.

// ---------------------------------------------------------------------------
// Integration settings (the parts most likely to need updating)
// ---------------------------------------------------------------------------

// Browser SDKs are loaded from a CDN at runtime, so no build step is needed.
const ELEVENLABS_SDK_URL = "https://esm.sh/@elevenlabs/client";
const ANAM_SDK_URL = "https://esm.sh/@anam-ai/js-sdk";

// The avatar speaks the agent's words with Anam's voice. The ElevenLabs
// agent also synthesises speech, so we mute it to avoid hearing the answer
// twice. Set to false to hear the ElevenLabs voice instead (avatar will
// still lip-sync, but you will hear both voices unless Anam's is silent).
const MUTE_ELEVENLABS_AUDIO = true;

// ElevenLabs is the ONLY answer source (RAG over the approved knowledge
// base). Anam is a renderer only: we disable its microphone input so its
// persona brain never hears the user and can never answer on its own.
// While ElevenLabs retrieves the answer (3-5 s), the app speaks ONE
// hard-coded, locally controlled filler phrase. It is sent via talk(),
// which renders text verbatim and does not invoke Anam's reasoning.
// If you ever observe the filler triggering an autonomous Anam response,
// set SPEAK_WAITING_FILLER to false: the UI waiting status still shows.
const SPEAK_WAITING_FILLER = true;
const WAITING_FILLER_PHRASE = "Let me check the approved process documentation.";
const WAITING_STATUS_TEXT = "Checking approved process documentation";
const RETRIEVAL_ERROR_PHRASE =
  "I could not retrieve an answer from the approved knowledge base. Please try again.";

// ---------------------------------------------------------------------------
// DOM references and UI helpers
// ---------------------------------------------------------------------------

const startBtn = document.getElementById("start-btn");
const stopBtn = document.getElementById("stop-btn");
const statusEl = document.getElementById("status-indicator");
const transcriptEl = document.getElementById("transcript");
const modeBanner = document.getElementById("mode-banner");
const avatarVideo = document.getElementById("avatar-video");
const avatarPlaceholder = document.getElementById("avatar-placeholder");
const avatarCircle = document.getElementById("avatar-circle");
const avatarPlaceholderText = document.getElementById("avatar-placeholder-text");

function setStatus(text, kind) {
  // kind: idle | connecting | listening | speaking | error
  statusEl.textContent = text;
  statusEl.className = `status-pill status-${kind}`;
  console.log(`[ui] Status: ${text}`);
}

function addMessage(role, text) {
  // role: "user" | "assistant" | "system"
  const div = document.createElement("div");
  div.className = `msg msg-${role}`;
  const labels = { user: "You", assistant: "Assistant", system: "System" };
  div.innerHTML = `<span class="who"></span>`;
  div.querySelector(".who").textContent = labels[role];
  div.appendChild(document.createTextNode(text));
  transcriptEl.appendChild(div);
  transcriptEl.scrollTop = transcriptEl.scrollHeight;
  console.log(`[transcript] ${role}: ${text}`);
}

function setButtons(running) {
  startBtn.disabled = running;
  stopBtn.disabled = !running;
}

// ---------------------------------------------------------------------------
// App state
// ---------------------------------------------------------------------------

let appMode = "mock"; // updated from /api/config
let conversation = null; // ElevenLabs conversation session
let anamClient = null; // Anam avatar client
let mockTimers = []; // pending timeouts in mock mode

// Conversation state machine. Exactly one state at a time:
//   idle | listening | waiting_for_elevenlabs | speaking_answer | error
// It exists to guarantee a single answer pipeline:
//   question -> waiting_for_elevenlabs (RAG) -> speaking_answer (Anam render)
let convState = "idle";
let fillerSpokenForCurrentQuestion = false;

function setState(next) {
  console.log(`[state] ${convState} -> ${next}`);
  convState = next;
  switch (next) {
    case "idle":
      setStatus("Idle", "idle");
      break;
    case "listening":
      setStatus("Listening", "listening");
      break;
    case "waiting_for_elevenlabs":
      setStatus(WAITING_STATUS_TEXT, "waiting");
      break;
    case "speaking_answer":
      setStatus("Speaking approved answer", "speaking");
      break;
    case "error":
      setStatus("Error", "error");
      break;
  }
}

// ---------------------------------------------------------------------------
// Live mode: Anam avatar
// ---------------------------------------------------------------------------

async function startAvatar() {
  addMessage("system", "Connecting to Anam avatar...");

  const tokenRes = await fetch("/api/anam/session-token", { method: "POST" });
  if (!tokenRes.ok) {
    throw new Error(`Avatar session token failed: ${(await tokenRes.json()).error}`);
  }
  const { sessionToken } = await tokenRes.json();

  const { createClient } = await import(ANAM_SDK_URL);

  // disableInputAudio is the critical setting: Anam never receives the
  // microphone, so its persona brain never hears a question and can never
  // answer independently. ElevenLabs alone listens and answers; Anam only
  // renders text we explicitly send via talk().
  anamClient = createClient(sessionToken, { disableInputAudio: true });
  console.log("[anam] Avatar renderer: Anam (input audio disabled - render-only).");
  console.log("[anam] Blocked Anam autonomous response: persona receives no microphone input.");

  // Belt-and-braces: also mute input if the SDK exposes it, in case a
  // future SDK version changes the default behaviour of the option above.
  if (typeof anamClient.muteInputAudio === "function") {
    try {
      anamClient.muteInputAudio();
    } catch (error) {
      console.warn("[anam] muteInputAudio not applicable:", error);
    }
  }

  // Streams avatar video (and its audio) into the <video> element via WebRTC.
  await anamClient.streamToVideoElement("avatar-video");

  avatarVideo.style.display = "block";
  avatarPlaceholder.classList.add("hidden");
  addMessage("system", "Avatar connected.");
  console.log("[anam] Avatar stream started.");
}

// Forward text to the avatar so it speaks it verbatim with lip sync.
// talk() is a render command, not a prompt: it does not invoke Anam's LLM.
// Calls are serialised through a promise chain so two talk commands can
// never be issued to Anam concurrently (no overlapping answers).
let talkChain = Promise.resolve();

function avatarSay(text) {
  if (!anamClient) return Promise.resolve();
  talkChain = talkChain.then(async () => {
    if (!anamClient) return; // stopped while queued
    try {
      if (typeof anamClient.talk === "function") {
        await anamClient.talk(text);
      } else if (typeof anamClient.createTalkMessageStream === "function") {
        // Older/streaming API variant: send the whole text as one final chunk.
        const stream = anamClient.createTalkMessageStream();
        stream.streamMessageChunk(text, true);
      } else {
        console.warn("[anam] No talk method found on the Anam client - check SDK docs.");
      }
    } catch (error) {
      console.error("[anam] Failed to send text to avatar:", error);
      addMessage("system", "Avatar lip-sync error (see console). Answer shown in transcript.");
    }
  });
  return talkChain;
}

function stopAvatar() {
  talkChain = Promise.resolve(); // drop any queued speech
  if (anamClient) {
    try {
      anamClient.stopStreaming();
    } catch (error) {
      console.warn("[anam] Error while stopping stream:", error);
    }
    anamClient = null;
  }
  avatarVideo.style.display = "none";
  avatarPlaceholder.classList.remove("hidden");
  console.log("[anam] Avatar stream stopped.");
}

// ---------------------------------------------------------------------------
// Live mode: ElevenLabs conversation
// ---------------------------------------------------------------------------

async function startConversationLive() {
  addMessage("system", "Requesting microphone access...");
  await navigator.mediaDevices.getUserMedia({ audio: true });

  addMessage("system", "Connecting to ElevenLabs agent...");
  const urlRes = await fetch("/api/elevenlabs/signed-url");
  if (!urlRes.ok) {
    throw new Error(`Signed URL failed: ${(await urlRes.json()).error}`);
  }
  const { signedUrl } = await urlRes.json();

  const { Conversation } = await import(ELEVENLABS_SDK_URL);

  conversation = await Conversation.startSession({
    signedUrl,
    connectionType: "websocket",

    onConnect: () => {
      addMessage("system", "Connected to agent. Ask a question about the supplier setup process.");
      console.log("[app] Voice/answer source: ElevenLabs");
      console.log("[app] Avatar renderer: Anam");
      setState("listening");
    },

    onDisconnect: () => {
      addMessage("system", "Agent disconnected.");
      console.log("[elevenlabs] Disconnected.");
    },

    // Transcripts and agent responses arrive here.
    // source is "user" (your speech transcript) or "ai" (agent answer).
    onMessage: ({ message, source }) => {
      console.log(`[elevenlabs] Message from ${source}:`, message);

      if (source === "user") {
        // The user finished a question. Enter the deliberate waiting state:
        // nothing is spoken until the ElevenLabs RAG answer arrives.
        console.log("[app] Question captured");
        console.log("[app] Waiting for ElevenLabs RAG answer");
        addMessage("user", message);

        if (convState === "waiting_for_elevenlabs" || convState === "speaking_answer") {
          // New question while a previous answer is still pending/playing.
          // We do not queue a second pipeline; the new question simply
          // becomes the pending one (ElevenLabs serialises turns itself).
          console.log("[app] New question while an answer was pending - previous turn superseded.");
        }
        setState("waiting_for_elevenlabs");
        addMessage("system", "Checking the approved process documentation...");

        // One short, locally hard-coded holding phrase per question. talk()
        // renders it verbatim; Anam does not generate or reason about it.
        if (SPEAK_WAITING_FILLER && !fillerSpokenForCurrentQuestion) {
          fillerSpokenForCurrentQuestion = true;
          console.log("[app] Speaking locally controlled filler phrase (not Anam-generated).");
          avatarSay(WAITING_FILLER_PHRASE);
        }
      } else {
        // The approved answer. This is the ONLY path to avatar speech.
        console.log("[app] ElevenLabs answer received");
        console.log("[app] Sending approved answer to Anam renderer");
        console.log("[app] Voice/answer source: ElevenLabs");
        addMessage("assistant", message);
        fillerSpokenForCurrentQuestion = false; // reset for the next question
        setState("speaking_answer");
        avatarSay(message);
      }
    },

    // mode.mode is "speaking" while the agent streams its (muted) audio,
    // "listening" otherwise. We use the return to "listening" as the signal
    // that the answer turn is over.
    onModeChange: (mode) => {
      console.log(`[elevenlabs] Mode: ${mode.mode}`);
      if (mode.mode === "listening" && convState === "speaking_answer") {
        setState("listening");
      }
      // While waiting_for_elevenlabs we deliberately keep the waiting
      // status; the answer text in onMessage moves us forward.
    },

    onError: (error) => {
      console.error("[elevenlabs] Error:", error);
      addMessage("system", RETRIEVAL_ERROR_PHRASE);
      setState("error");
      fillerSpokenForCurrentQuestion = false;
      // Fixed local phrase only - the avatar must never invent a fallback.
      avatarSay(RETRIEVAL_ERROR_PHRASE);
    },
  });

  if (MUTE_ELEVENLABS_AUDIO) {
    // The agent still does STT + RAG + answer + voice, but we silence its
    // audio locally because the Anam avatar voices the answer instead.
    await conversation.setVolume({ volume: 0 });
    console.log("[elevenlabs] Output muted (avatar provides the voice).");
  }
}

async function stopConversationLive() {
  if (conversation) {
    try {
      await conversation.endSession();
    } catch (error) {
      console.warn("[elevenlabs] Error while ending session:", error);
    }
    conversation = null;
  }
  stopAvatar();
}

// ---------------------------------------------------------------------------
// Mock mode: scripted demonstration, no external calls
// ---------------------------------------------------------------------------

const MOCK_SCRIPT = [
  {
    question: "What is the first step when a new supplier needs to be set up?",
    answer:
      "The process starts with a supplier setup request raised by the requesting " +
      "department. The request captures the business justification and the core " +
      "master data, and is then routed to the master data team for validation " +
      "before anything is created in the system.",
  },
  {
    question: "Who approves changes to supplier bank details?",
    answer:
      "Bank detail changes follow a four-eyes control: one master data officer " +
      "enters the change and a second, independent approver verifies it against " +
      "evidence supplied by the supplier before the change becomes active. I can " +
      "explain the control, but I cannot approve changes myself.",
  },
  {
    question: "What are the main risks in the current process?",
    answer:
      "The key risks identified are duplicate supplier records, unverified bank " +
      "detail changes, and incomplete handovers between requesting departments " +
      "and the master data team. Several design decisions on automation of the " +
      "validation step are still open.",
  },
];

function mockDelay(fn, ms) {
  mockTimers.push(setTimeout(fn, ms));
}

function startConversationMock() {
  addMessage(
    "system",
    "MOCK MODE: live credentials are not configured. The following exchange is scripted to demonstrate the interface."
  );
  setState("listening");
  avatarPlaceholderText.textContent = "Mock avatar (no live stream)";

  let t = 1200;
  for (const { question, answer } of MOCK_SCRIPT) {
    mockDelay(() => {
      console.log("[app] Question captured (mock)");
      addMessage("user", question);
      // Same deliberate waiting state as live mode: nothing is answered
      // until the (simulated) RAG retrieval completes.
      setState("waiting_for_elevenlabs");
      addMessage("system", "Checking the approved process documentation...");
    }, t);
    t += 2500; // simulated RAG retrieval delay
    mockDelay(() => {
      console.log("[app] ElevenLabs answer received (mock)");
      setState("speaking_answer");
      avatarCircle.classList.add("speaking");
      addMessage("assistant", answer);
    }, t);
    t += 4000;
    mockDelay(() => {
      setState("listening");
      avatarCircle.classList.remove("speaking");
    }, t);
    t += 800;
  }
  mockDelay(() => {
    addMessage("system", "End of scripted demonstration. Press Stop, or Start to replay.");
  }, t);
}

function stopConversationMock() {
  mockTimers.forEach(clearTimeout);
  mockTimers = [];
  avatarCircle.classList.remove("speaking");
  avatarPlaceholderText.textContent = "Avatar will appear here";
}

// ---------------------------------------------------------------------------
// Button wiring
// ---------------------------------------------------------------------------

startBtn.addEventListener("click", async () => {
  setButtons(true);
  setStatus("Connecting", "connecting");
  try {
    if (appMode === "live") {
      await startAvatar();
      await startConversationLive();
    } else {
      startConversationMock();
    }
  } catch (error) {
    console.error("[app] Failed to start conversation:", error);
    addMessage("system", `Failed to start: ${error.message}`);
    setState("error");
    await stopConversationLive();
    setButtons(false);
  }
});

stopBtn.addEventListener("click", async () => {
  if (appMode === "live") {
    await stopConversationLive();
  } else {
    stopConversationMock();
  }
  fillerSpokenForCurrentQuestion = false;
  addMessage("system", "Conversation stopped.");
  setState("idle");
  setButtons(false);
});

// ---------------------------------------------------------------------------
// Startup: ask the server which mode we are in
// ---------------------------------------------------------------------------

async function init() {
  try {
    const res = await fetch("/api/config");
    const cfg = await res.json();
    appMode = cfg.mode;
    console.log(`[app] Mode: ${appMode}`, cfg);

    if (appMode === "mock") {
      modeBanner.textContent =
        `Mock mode - missing credentials: ${cfg.missing.join(", ")}. ` +
        "Add them to .env and restart the server to go live.";
      modeBanner.classList.remove("hidden");
      addMessage("system", "App started in MOCK mode.");
    } else {
      addMessage("system", "App started in LIVE mode. Press Start Conversation.");
    }
  } catch (error) {
    console.error("[app] Could not reach the server:", error);
    modeBanner.textContent = "Could not reach the local server. Is it running?";
    modeBanner.classList.add("error");
    modeBanner.classList.remove("hidden");
    setStatus("Error", "error");
  }
}

init();
