import { useEffect, useRef, useState } from "react";
import {
  askAvatarQuestion,
  createAvatarSessionToken,
  getAvatarConfig,
  resolveProcessDiagram,
  type AvatarAnswerResponse,
  type AvatarConfig,
  type AvatarStyleMode,
  type ProcessDiagramContext,
} from "./api";
import { Markdown } from "./Markdown";
import { ProcessDiagramPanel } from "./ProcessDiagramPanel";

const ANAM_SDK_URL = "https://esm.sh/@anam-ai/js-sdk";
const WAITING_PHRASE = "Let me check the approved knowledge base.";
const ERROR_PHRASE = "I could not retrieve an answer from the approved knowledge base. Please try again.";

type AvatarStatus = "idle" | "connecting" | "ready" | "checking" | "speaking" | "error";
type MessageRole = "system" | "user" | "assistant";

interface TranscriptMessage {
  role: MessageRole;
  text: string;
  style?: AvatarStyleMode;
  confidence?: string;
  citationCount?: number;
  refused?: boolean;
}

function statusLabel(status: AvatarStatus): string {
  const labels: Record<AvatarStatus, string> = {
    idle: "Idle",
    connecting: "Connecting avatar",
    ready: "Ready",
    checking: "Checking approved knowledge",
    speaking: "Speaking approved answer",
    error: "Error",
  };
  return labels[status];
}

function roleLabel(role: MessageRole): string {
  return role === "assistant" ? "Assistant" : role === "user" ? "You" : "System";
}

function styleLabel(style: AvatarStyleMode): string {
  return style === "natural" ? "Natural spoken" : "Formal";
}

function citationLabel(count: number): string {
  return `${count} citation${count === 1 ? "" : "s"}`;
}

export function AvatarLabPage() {
  const [config, setConfig] = useState<AvatarConfig | null>(null);
  const [configLoaded, setConfigLoaded] = useState(false);
  const [configError, setConfigError] = useState<string | null>(null);
  const [status, setStatus] = useState<AvatarStatus>("idle");
  const [question, setQuestion] = useState("");
  const [style, setStyle] = useState<AvatarStyleMode>("formal");
  const [messages, setMessages] = useState<TranscriptMessage[]>([
    { role: "system", text: "Avatar Lab uses Anam only as a video renderer. Answers come from the Knowledge Assistant." },
  ]);
  const [latest, setLatest] = useState<AvatarAnswerResponse | null>(null);
  const [diagram, setDiagram] = useState<ProcessDiagramContext | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [diagramBusy, setDiagramBusy] = useState(false);
  const avatarRef = useRef<any>(null);
  const talkChain = useRef(Promise.resolve());

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
    return () => {
      stopAvatarClient();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function addMessage(role: MessageRole, text: string, metadata: Omit<TranscriptMessage, "role" | "text"> = {}) {
    setMessages((current) => [...current, { role, text, ...metadata }]);
  }

  async function avatarSay(text: string) {
    const client = avatarRef.current;
    if (!client) return;
    talkChain.current = talkChain.current.then(async () => {
      const active = avatarRef.current;
      if (!active) return;
      setStatus("speaking");
      if (typeof active.talk === "function") {
        await active.talk(text);
      } else if (typeof active.createTalkMessageStream === "function") {
        const stream = active.createTalkMessageStream();
        stream.streamMessageChunk(text, true);
      }
      setStatus("ready");
    });
    await talkChain.current;
  }

  async function startAvatar() {
    setBusy(true);
    setError(null);
    setStatus("connecting");
    addMessage("system", "Connecting to Anam avatar...");
    try {
      const sessionToken = await createAvatarSessionToken();
      const { createClient } = await import(/* @vite-ignore */ ANAM_SDK_URL);
      const client = createClient(sessionToken, { disableInputAudio: true });
      if (typeof client.muteInputAudio === "function") {
        client.muteInputAudio();
      }
      avatarRef.current = client;
      await client.streamToVideoElement("avatar-lab-video");
      addMessage("system", "Avatar connected. Anam input audio is disabled.");
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

  async function onAsk(event: React.FormEvent) {
    event.preventDefault();
    if (!question.trim() || busy) return;
    const asked = question.trim();
    setQuestion("");
    setBusy(true);
    setDiagram(null);
    setError(null);
    setLatest(null);
    setStatus("checking");
    addMessage("user", asked);
    addMessage("system", "Checking the approved knowledge base...");
    if (avatarRef.current) {
      void avatarSay(WAITING_PHRASE);
    }
    try {
      const response = await askAvatarQuestion(asked, style);
      setLatest(response);
      setDiagramBusy(true);
      addMessage("assistant", response.rendered_text, {
        style: response.style,
        confidence: response.answer.confidence,
        citationCount: response.answer.citations.length,
        refused: response.answer.refused,
      });
      const diagramPromise = resolveProcessDiagram(asked, response.answer.citations)
        .then((value) => setDiagram(value))
        .catch((err) => setDiagram({
          status: "unavailable",
          message: err instanceof Error ? err.message : "Could not load process map.",
          process_id: "",
          process_name: "",
          source_title: "",
          service_url: "",
          chart: null,
          svg: "",
        }))
        .finally(() => setDiagramBusy(false));
      await avatarSay(response.rendered_text);
      await diagramPromise;
      if (!avatarRef.current) setStatus("idle");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Ask request failed.";
      setError(message);
      setDiagram(null);
      addMessage("system", ERROR_PHRASE);
      await avatarSay(ERROR_PHRASE);
      setStatus("error");
    } finally {
      setBusy(false);
    }
  }

  const configured = Boolean(config?.configured);
  const connected = Boolean(avatarRef.current);

  return (
    <div className="view-stack">
      <div className="page-intro">
        <h1>Avatar Lab</h1>
        <p>Internal test page for rendering grounded assistant answers through Anam video.</p>
      </div>

      <div className="avatar-lab-grid">
        <div className="panel">
          <div className="panel-heading">
            <div>
              <h2>Avatar renderer</h2>
              <p className="muted-text">
                Anam input audio stays disabled; only final assistant text is sent to the avatar.
              </p>
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
                <div className="avatar-orb">AI</div>
                <p>{configured ? `Persona ${config?.persona_id_hint}` : "Avatar will appear here"}</p>
              </div>
            ) : null}
          </div>
          <div className="avatar-controls">
            <label className="field-label avatar-style-control">
              Style
              <select value={style} disabled={busy} onChange={(event) => setStyle(event.target.value as AvatarStyleMode)}>
                <option value="formal">Formal</option>
                <option value="natural">Natural spoken</option>
              </select>
            </label>
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
              <h2>Transcript</h2>
              <p className="muted-text">Typed questions use the same `/api/ask` path as the Ask page.</p>
            </div>
          </div>
          <div className="avatar-transcript">
            {messages.map((message, index) => (
              <div className={`avatar-message avatar-message-${message.role}`} key={`${message.role}-${index}`}>
                <span>{roleLabel(message.role)}</span>
                <p>{message.text}</p>
                {message.style ? (
                  <small className="avatar-message-meta">
                    {styleLabel(message.style)}
                    {message.refused ? " · refused" : message.confidence ? ` · ${message.confidence}` : ""}
                    {typeof message.citationCount === "number" ? ` · ${citationLabel(message.citationCount)}` : ""}
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
              placeholder="Ask a process question for the avatar to speak..."
            />
            <button type="submit" className="primary-button" disabled={busy || !question.trim()}>
              {busy && status !== "connecting" ? "Checking..." : "Ask"}
            </button>
          </form>
        </div>
      </div>

      {latest ? (
        <div className="answer-diagram-grid">
          <div className="panel">
            <div className="panel-heading">
              <div>
                <h2>Latest avatar response</h2>
                <p className="muted-text">{styleLabel(latest.style)} · {citationLabel(latest.answer.citations.length)}</p>
              </div>
              <span className={`status-pill${latest.answer.refused ? " status-pill--warn" : " status-pill--good"}`}>
                {latest.answer.refused ? "refused" : latest.answer.confidence}
              </span>
            </div>
            <div className={`answer-card${latest.answer.refused ? " answer-card--refused" : ""}`}>
              <div className="answer-text"><Markdown text={latest.rendered_text} /></div>
            </div>
            <p className="muted-text" style={{ marginTop: 10 }}>
              mode: <b>{latest.answer.mode}</b>
              {latest.answer.grounding && latest.answer.grounding !== "n/a" ? <> · grounding: <b>{latest.answer.grounding}</b> ({Math.round(latest.answer.grounding_score * 100)}%)</> : null}
              {latest.answer.faithfulness && latest.answer.faithfulness !== "n/a" ? <> · faithfulness: <b>{latest.answer.faithfulness.replace("_", " ")}</b></> : null}
            </p>
            {latest.answer.citations.length ? (
              <div className="result-list" style={{ marginTop: 10 }}>
                {latest.answer.citations.map((citation, index) => (
                  <div className="result-card" key={`${citation.source_id}-${citation.ordinal}-${index}`}>
                    <div className="result-head">
                      <b>{citation.heading}</b>
                      <span className="status-pill">section {citation.ordinal}</span>
                    </div>
                    <p className="result-cite">{citation.source_title}</p>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
          <ProcessDiagramPanel diagram={diagram} loading={diagramBusy} title="Avatar process map" />
        </div>
      ) : null}
    </div>
  );
}
