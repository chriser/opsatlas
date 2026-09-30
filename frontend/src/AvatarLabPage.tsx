import { useCallback, useEffect, useRef, useState } from "react";
import {
  askTibiText,
  closeTibiText,
  createAvatarSessionToken,
  getAvatarConfig,
  getTibiStatus,
  openTibiText,
  TibiServiceError,
  type AvatarConfig,
  type TibiStatus,
  type TibiTextTurn,
} from "./api";

// The Anam browser library is bundled from npm at a pinned version (package.json), not fetched from a CDN at run
// time (ARCH F3). It is imported only when the avatar starts, so the optional avatar stays out of the main bundle.
const ERROR_PHRASE = "Sorry, I couldn't prepare an answer just then. Could you ask again?";
const AVATAR_SPEECH_EVENTS = [
  "talkEnd",
  "talk:end",
  "speechEnd",
  "speech:end",
  "messageEnd",
  "message:end",
];
const AVATAR_WORD_MS = 390;
const AVATAR_MIN_SPEECH_MS = 1200;
const AVATAR_MAX_SPEECH_MS = 120000;
const AVATAR_MAIN_ANSWER_SETTLE_MS = 3500;

type AvatarStatus = "idle" | "connecting" | "ready" | "checking" | "loading" | "speaking" | "error";
type MessageRole = "system" | "user" | "assistant";

interface TranscriptMessage {
  role: MessageRole;
  text: string;
  turn?: TibiTextTurn;
}

// How Tibi reached an answer, in words (DSME S2).
const ROUTES: Record<string, string> = {
  product: "Product answer",
  self: "About Tibi",
  conversation: "Conversation",
  general: "General knowledge",
  clarify: "Clarifying question",
  workspace: "Workspace guidance",
  evidence_changed: "Evidence changed",
};
const GROUNDING: Record<string, string> = {
  grounded_synthesis: "Checked against enabled records",
  approved_spoken: "Approved spoken wording",
  approved_fallback: "Approved record wording",
  no_approved_evidence: "No enabled record covers this",
  evidence_unavailable: "Records unavailable",
  general_model_knowledge: "General knowledge, not product evidence",
  conversation: "Conversation only, no product claims",
  clarification: "Asks which area you mean",
  workspace_guidance: "Fixed workspace guidance",
  evidence_changed: "Asked to repeat the question",
};

function statusLabel(status: AvatarStatus): string {
  const labels: Record<AvatarStatus, string> = {
    idle: "Idle",
    connecting: "Connecting avatar",
    ready: "Ready",
    checking: "Tibi is answering",
    loading: "Loading Tibi's model",
    speaking: "Speaking",
    error: "Error",
  };
  return labels[status];
}

function roleLabel(role: MessageRole): string {
  return role === "assistant" ? "Digital SME" : role === "user" ? "You" : "System";
}

function seconds(ms: number | null | undefined): string {
  return typeof ms === "number" ? `${(ms / 1000).toFixed(1)} s` : "—";
}

function estimateAvatarSpeechMs(text: string): number {
  const wordCount = text.split(/\s+/).filter(Boolean).length;
  return Math.min(AVATAR_MAX_SPEECH_MS, Math.max(AVATAR_MIN_SPEECH_MS, wordCount * AVATAR_WORD_MS));
}

function waitForAvatarSpeechCompletion(
  client: any,
  timeoutMs: number,
  options: { eventSettleMs?: number; listenForSpeechEvents?: boolean } = {},
): Promise<void> {
  return new Promise((resolve) => {
    let finished = false;
    let eventSettleTimer: number | null = null;
    const eventSettleMs = options.eventSettleMs ?? 0;
    const listenForSpeechEvents = options.listenForSpeechEvents ?? true;
    const cleanup: (() => void)[] = [];
    const finish = () => {
      if (finished) return;
      finished = true;
      cleanup.forEach((fn) => fn());
      resolve();
    };
    const scheduleEventFinish = () => {
      if (finished || eventSettleTimer !== null) return;
      if (!eventSettleMs) {
        finish();
        return;
      }
      eventSettleTimer = window.setTimeout(finish, eventSettleMs);
      cleanup.push(() => {
        if (eventSettleTimer !== null) window.clearTimeout(eventSettleTimer);
      });
    };
    const timer = window.setTimeout(finish, timeoutMs);
    cleanup.push(() => window.clearTimeout(timer));

    if (listenForSpeechEvents) {
      for (const eventName of AVATAR_SPEECH_EVENTS) {
        if (typeof client?.addEventListener === "function") {
          client.addEventListener(eventName, scheduleEventFinish);
          cleanup.push(() => client.removeEventListener?.(eventName, scheduleEventFinish));
        }
        if (typeof client?.on === "function") {
          client.on(eventName, scheduleEventFinish);
          cleanup.push(() => {
            if (typeof client.off === "function") client.off(eventName, scheduleEventFinish);
            else if (typeof client.removeListener === "function") client.removeListener(eventName, scheduleEventFinish);
          });
        }
        if (typeof client?.once === "function") {
          client.once(eventName, scheduleEventFinish);
        }
      }
    }
  });
}

const OPENING: TranscriptMessage = {
  role: "system",
  text: "Ask anything you would ask Tibi. Tibi's engine answers, and the Digital SME avatar speaks the checked reply.",
};

/** The Digital SME: Tibi's answers, spoken by the Anam avatar (DSME S2). Anam renders only; it never hears or answers. */
export function AvatarLabPage() {
  const [config, setConfig] = useState<AvatarConfig | null>(null);
  const [configLoaded, setConfigLoaded] = useState(false);
  const [configError, setConfigError] = useState<string | null>(null);
  const [tibi, setTibi] = useState<TibiStatus | null | undefined>(undefined);
  const [status, setStatus] = useState<AvatarStatus>("idle");
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<TranscriptMessage[]>([OPENING]);
  const [latest, setLatest] = useState<TibiTextTurn | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const avatarRef = useRef<any>(null);
  const talkChain = useRef(Promise.resolve());
  const transcriptRef = useRef<HTMLDivElement | null>(null);
  // Tibi's conversation for this page: follow-ups ("Why is that?") are answered in context.
  const conversation = useRef<Promise<string> | null>(null);

  function conversationId(fresh = false): Promise<string> {
    if (fresh || !conversation.current) {
      const opening = openTibiText().then((opened) => opened.id);
      opening.catch(() => {
        if (conversation.current === opening) conversation.current = null;
      });
      conversation.current = opening;
    }
    return conversation.current;
  }

  function endConversation() {
    const current = conversation.current;
    conversation.current = null;
    current?.then((id) => closeTibiText(id)).catch(() => undefined);
  }

  useEffect(() => {
    getAvatarConfig()
      .then((value) => {
        setConfig(value);
        setConfigError(null);
      })
      .catch((err) => {
        setConfig(null);
        setConfigError(err instanceof Error ? err.message : "Could not load avatar configuration.");
      })
      .finally(() => setConfigLoaded(true));
    getTibiStatus()
      .then((value) => {
        setTibi(value);
        // Start Tibi's conversation now, so its model is warm by the first question.
        if (value?.available) void conversationId().catch(() => undefined);
      })
      .catch(() => setTibi(null));
    return () => {
      stopAvatarClient();
      endConversation();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const transcript = transcriptRef.current;
    if (!transcript) return;
    transcript.scrollTo({ top: transcript.scrollHeight, behavior: "smooth" });
  }, [messages.length]);

  function addMessage(role: MessageRole, text: string, turn?: TibiTextTurn) {
    setMessages((current) => [...current, { role, text, turn }]);
  }

  const avatarSay = useCallback(async (text: string, options: { eventSettleMs?: number; listenForSpeechEvents?: boolean; extraWaitMs?: number } = {}) => {
    const client = avatarRef.current;
    if (!client) return;
    talkChain.current = talkChain.current.then(async () => {
      const active = avatarRef.current;
      if (!active) return;
      setStatus("speaking");
      const completion = waitForAvatarSpeechCompletion(active, estimateAvatarSpeechMs(text) + (options.extraWaitMs ?? 0), {
        eventSettleMs: options.eventSettleMs ?? 0,
        listenForSpeechEvents: options.listenForSpeechEvents ?? true,
      });
      if (typeof active.talk === "function") {
        await active.talk(text);
      } else if (typeof active.createTalkMessageStream === "function") {
        const stream = active.createTalkMessageStream();
        stream.streamMessageChunk(text, true);
      }
      await completion;
      setStatus("ready");
    });
    await talkChain.current;
  }, []);

  async function startAvatar() {
    setBusy(true);
    setError(null);
    setStatus("connecting");
    addMessage("system", "Connecting to the Digital SME avatar…");
    try {
      const sessionToken = await createAvatarSessionToken();
      const { createClient } = await import("@anam-ai/js-sdk");
      const client = createClient(sessionToken, { disableInputAudio: true });
      if (typeof client.muteInputAudio === "function") {
        client.muteInputAudio();
      }
      avatarRef.current = client;
      await client.streamToVideoElement("avatar-lab-video");
      addMessage("system", "Avatar connected. It speaks Tibi's replies; it does not listen.");
      setStatus("ready");
    } catch (err) {
      stopAvatar();
      const message = err instanceof Error ? err.message : "Avatar connection failed.";
      setError(message);
      addMessage("system", message);
      setStatus("error");
    } finally {
      setBusy(false);
    }
  }

  function stopAvatarClient() {
    talkChain.current = Promise.resolve();
    if (avatarRef.current) {
      try {
        avatarRef.current.stopStreaming?.();
      } catch {
        // Stopping is best-effort; the UI still clears the local client.
      }
      avatarRef.current = null;
    }
  }

  function stopAvatar() {
    stopAvatarClient();
    setStatus("idle");
  }

  function newConversation() {
    endConversation();
    setMessages([OPENING]);
    setLatest(null);
    setError(null);
    void conversationId().catch(() => undefined);
  }

  /** Ask Tibi's engine; a conversation that ended (idle, or Tibi restarted) is started again once. */
  async function ask(text: string): Promise<TibiTextTurn> {
    try {
      return await askTibiText(await conversationId(), text);
    } catch (err) {
      if (err instanceof TibiServiceError && err.status === 404) {
        addMessage("system", "The earlier conversation had ended, so this starts a new one.");
        return askTibiText(await conversationId(true), text);
      }
      throw err;
    }
  }

  async function onAsk(event: React.FormEvent) {
    event.preventDefault();
    if (!question.trim() || busy) return;
    const asked = question.trim();
    setQuestion("");
    setBusy(true);
    setError(null);
    setStatus("checking");
    addMessage("user", asked);
    // The first answer after a while waits for the local model to load: say so rather than look stuck.
    const slow = window.setTimeout(() => setStatus((current) => (current === "checking" ? "loading" : current)), 4000);
    try {
      const turn = await ask(asked);
      window.clearTimeout(slow);
      setLatest(turn);
      addMessage("assistant", turn.reply, turn);
      await avatarSay(turn.reply, { extraWaitMs: AVATAR_MAIN_ANSWER_SETTLE_MS, listenForSpeechEvents: false });
      if (!avatarRef.current) setStatus("idle");
    } catch (err) {
      window.clearTimeout(slow);
      const message = err instanceof Error ? err.message : "Tibi could not answer.";
      setError(message);
      addMessage("system", message);
      await avatarSay(ERROR_PHRASE);
      setStatus(avatarRef.current ? "ready" : "error");
    } finally {
      setBusy(false);
    }
  }

  const configured = Boolean(config?.configured);
  const connected = Boolean(avatarRef.current);
  const tibiDown = tibi === null || (tibi !== undefined && !tibi.available);
  const engine = tibi?.service?.engine;

  return (
    <div className="view-stack">
      <div className="page-intro">
        <h1>Ask Digital SME</h1>
        <p>
          The same answers as Tibi, spoken by the Digital SME avatar. Tibi's engine answers every question, with the same routing, enabled
          records and checks as its voice; the avatar only speaks the reply.
        </p>
      </div>

      <div className="avatar-lab-grid">
        <div className="panel">
          <div className="panel-heading">
            <div>
              <h2>Digital SME</h2>
              <p className="muted-text">Anam renders the avatar. Its microphone stays off; only Tibi's checked reply is sent to it.</p>
            </div>
            <span className={`status-pill avatar-status-${status}`}>{statusLabel(status)}</span>
          </div>
          {!configLoaded ? (
            <div className="result-card" style={{ marginBottom: 12 }}>
              <div className="result-head"><b>Checking Anam configuration</b></div>
              <p className="result-cite">Loading backend avatar settings...</p>
            </div>
          ) : configError ? (
            <div className="result-card" style={{ marginBottom: 12 }}>
              <div className="result-head"><b>Avatar configuration unavailable</b></div>
              <p className="result-cite">{configError}</p>
            </div>
          ) : !configured ? (
            <div className="result-card" style={{ marginBottom: 12 }}>
              <div className="result-head"><b>Anam not configured</b></div>
              <p className="result-cite">Add {config?.missing.join(" and ") || "ANAM_API_KEY and ANAM_PERSONA_ID"} to the backend environment, then restart.</p>
            </div>
          ) : null}
          <div className="avatar-video-frame">
            <video id="avatar-lab-video" autoPlay playsInline />
            {!connected ? (
              <div className="avatar-placeholder">
                <div className="avatar-orb">Kris</div>
                <p>{configured ? "Digital SME" : "Avatar will appear here"}</p>
              </div>
            ) : null}
          </div>
          <div className="avatar-controls">
            <span className={`avatar-engine${tibiDown ? " avatar-engine--down" : ""}`}>
              {tibi === undefined
                ? "Checking Tibi…"
                : tibiDown
                  ? "Tibi is not running: use Restart services under Status"
                  : `Tibi engine ${engine?.version ?? ""}`}
            </span>
            <button type="button" className="primary-button" disabled={!configured || connected || busy} onClick={startAvatar}>
              {busy && status === "connecting" ? "Connecting..." : "Start Avatar"}
            </button>
            <button type="button" className="secondary-button" disabled={!connected} onClick={stopAvatar}>
              Stop Avatar
            </button>
          </div>
          {error ? <p className="muted-text" style={{ color: "var(--red)", marginTop: 12 }}>{error}</p> : null}
        </div>

        <div className="panel">
          <div className="panel-heading">
            <div>
              <h2>Conversation</h2>
              <p className="muted-text">One conversation with Tibi, so follow-up questions work. It is in the Conversation Log as Digital SME.</p>
            </div>
            <button type="button" className="text-button" disabled={busy} onClick={newConversation}>
              New conversation
            </button>
          </div>
          <div className="avatar-transcript" ref={transcriptRef}>
            {messages.map((message, index) => (
              <div className={`avatar-message avatar-message-${message.role}`} key={`${message.role}-${index}`}>
                <span>{roleLabel(message.role)}</span>
                <p>{message.text}</p>
                {message.turn ? (
                  <small className="avatar-message-meta">
                    {ROUTES[message.turn.route] ?? message.turn.route}
                    {message.turn.records.length ? ` · ${message.turn.records.length} record${message.turn.records.length === 1 ? "" : "s"}` : ""}
                    {` · ${seconds(message.turn.total_ms)}`}
                  </small>
                ) : null}
              </div>
            ))}
          </div>
          <form className="search-row" onSubmit={onAsk} style={{ marginTop: 12 }}>
            <input
              className="search-input"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Ask what you would ask Tibi, for example: What is OpsAtlas?"
            />
            <button type="submit" className="primary-button" disabled={busy || !question.trim() || tibiDown}>
              {busy && status !== "connecting" ? "Answering..." : "Ask"}
            </button>
          </form>
        </div>
      </div>

      {latest ? (
        <div className="panel avatar-latest-response-panel">
          <div className="panel-heading">
            <div>
              <h2>How Tibi answered</h2>
              <p className="muted-text">
                {ROUTES[latest.route] ?? latest.route} · {GROUNDING[latest.grounding ?? ""] ?? latest.grounding ?? "—"} · engine {latest.engine.version}
              </p>
            </div>
            <span className="status-pill">
              first words {seconds(latest.reasoning_ms)} · reply {seconds(latest.total_ms)}
            </span>
          </div>
          {latest.route_reasons.length ? (
            <p className="muted-text">Why this route: {latest.route_reasons.join("; ")}</p>
          ) : null}
          {latest.records.length ? (
            <div className="result-list" style={{ marginTop: 10 }}>
              {latest.records.map((record) => (
                <div className="result-card" key={record.id}>
                  <div className="result-head">
                    <a className="table-link" href={`#tibi-knowledge:${record.id}`}>
                      {record.title}
                    </a>
                    <span className="status-pill">{record.status}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="muted-text">No product records were needed for this reply.</p>
          )}
        </div>
      ) : null}
    </div>
  );
}
