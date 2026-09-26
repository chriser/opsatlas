import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { getTibiRecords, type TibiRecord, type TibiStatus } from "./api";
import type { StageState } from "./tibi/Spirit";
import { tibiVoice, type TibiMode, type TibiView } from "./tibi/voice";

export type { TibiMode } from "./tibi/voice";

const MODES: [TibiMode, string][] = [
  ["recall", "Chat with Tibi"],
  ["interview", "Contribute product knowledge"],
  ["governance", "Resolve governance issues"],
];

const GROUNDING: Record<string, string> = {
  grounded_synthesis: "Checked sentence by sentence against these approved records before it was spoken.",
  approved_spoken: "Human-approved spoken wording for this record.",
  approved_fallback: "The generated wording went beyond the records, so the approved record wording was spoken instead.",
  clarification: "Tibi asked which area you mean before answering.",
  workspace_guidance: "Workspace instructions · no product claim.",
  general_model_knowledge: "General model knowledge · not verified against OpsAtlas.",
  conversation: "Conversation · no product claim.",
};

function useTibiVoice(): TibiView {
  const [view, setView] = useState<TibiView>(tibiVoice().view);
  useEffect(() => tibiVoice().subscribe(setView), []);
  return view;
}

const Spirit = lazy(() => import("./tibi/Spirit"));

function stageState(view: TibiView): StageState {
  if (view.phase === "starting") return "starting";
  if (view.phase === "paused" || view.phase === "closed") return "paused";
  if (view.phase !== "live") return "idle";
  if (view.state.startsWith("Speaking")) return "speaking";
  if (view.thinking) return "thinking";
  return "listening";
}

function remembered(key: string, fallback: boolean): boolean {
  try {
    const value = localStorage.getItem(key);
    return value === null ? fallback : value === "1";
  } catch {
    return fallback;
  }
}

function remember(key: string, value: boolean) {
  try {
    localStorage.setItem(key, value ? "1" : "0");
  } catch {
    // A convenience only.
  }
}

/** Talk with Tibi (OBS F5): Tibi and the conversation at the centre; settings, devices and evidence at the side.
 *  Tibi itself runs as its own service behind /services/tibi. */
export function TibiPage({
  status,
  mode,
  onOpenKnowledge,
}: {
  status: TibiStatus | null;
  mode: TibiMode;
  onOpenKnowledge: (record?: string) => void;
}) {
  const view = useTibiVoice();
  const voice = tibiVoice();
  const [form, setForm] = useState({ mode, contributor: "Chris", topic: "", voice: "higgs", typed: false });
  const [records, setRecords] = useState<TibiRecord[]>([]);
  const [message, setMessage] = useState("");
  const [side, setSide] = useState(() => remembered("tibi-side-open", true));
  const [animation, setAnimation] = useState(() => remembered("tibi-animation", true));
  const transcriptEnd = useRef<HTMLDivElement>(null);

  useEffect(() => setForm((current) => ({ ...current, mode })), [mode]);
  useEffect(() => {
    getTibiRecords()
      .then((data) => {
        setRecords(data.records);
        setForm((current) => ({
          ...current,
          topic: current.topic || data.records.find((r) => !r.provenance && r.kind !== "conversation")?.id || "",
        }));
      })
      .catch(() => setRecords([]));
  }, []);

  const topics = records.filter((r) => !r.provenance && r.kind !== "conversation");
  const enabled = records.filter((r) => r.eligible && r.kind !== "conversation").length;
  const active = view.phase === "starting" || view.phase === "live" || view.phase === "paused";
  // What you said shows until it lands in the transcript.
  const heard = [...view.transcript].reverse().find((line) => line.role === "user")?.content;
  const partial = view.partial && view.partial !== heard ? view.partial : "";
  const lastTibi = [...view.transcript].reverse().find((line) => line.role === "assistant")?.content;
  const speakingNow = view.reply && view.reply !== lastTibi && active ? view.reply : "";
  const stage = stageState(view);
  const engine = status?.service?.engine;

  useEffect(() => {
    transcriptEnd.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [view.transcript.length, speakingNow, partial]);

  function send(event: React.FormEvent) {
    event.preventDefault();
    voice.sendText(message);
    setMessage("");
  }

  const startLabel =
    form.mode === "governance" ? "Start governance interview" : form.mode === "interview" ? "Start product interview" : "Start with Tibi";

  return (
    <div className={`tibi-room${side ? " tibi-room--side" : ""}`}>
      <section className="tibi-stage-column">
        <header className="tibi-stage-head">
          <div>
            <h1>Talk with Tibi</h1>
            <p className="muted-text">
              {MODES.find(([key]) => key === (active ? view.mode : form.mode))?.[1]}
              {engine ? <span className="tibi-engine" title={`Engine fingerprint ${engine.fingerprint}`}> · engine {engine.version}</span> : null}
            </p>
          </div>
          <div className="tibi-stage-head-actions">
            <span className={`status-pill tibi-state tibi-state--${stage}`}>{view.state}</span>
            <button type="button" className="secondary-button" aria-expanded={side} onClick={() => { setSide(!side); remember("tibi-side-open", !side); }}>
              {side ? "Hide settings" : "Settings"}
            </button>
          </div>
        </header>

        {status && !status.available ? (
          <p className="tibi-alert">Tibi is not running. Use Restart services under Status, then start again.</p>
        ) : status?.busy && !active ? (
          <p className="tibi-alert tibi-alert--soft">{status.busy}</p>
        ) : null}

        <div className="tibi-stage">
          {animation ? (
            <Suspense fallback={<div className="tibi-spirit" />}>
              <Spirit state={stage} levels={() => voice.levels()} />
            </Suspense>
          ) : (
            <div className={`tibi-spirit tibi-spirit--${stage}`} aria-hidden="true" />
          )}
          <div className="tibi-stage-caption" aria-live="polite">
            {view.thinking ? "Thinking…" : view.notice || (active ? "" : "Press start when you are ready.")}
          </div>
        </div>

        <div className="tibi-controls">
          {!active ? (
            <button type="button" className="primary-button tibi-start" disabled={status?.available === false} onClick={() => void voice.start({ ...form })}>
              {startLabel}
            </button>
          ) : (
            <>
              {view.phase === "paused" ? (
                <button type="button" className="primary-button" onClick={() => void voice.resume()}>
                  Resume
                </button>
              ) : (
                <button type="button" className="secondary-button" disabled={view.phase === "starting"} onClick={() => voice.pause()}>
                  Pause
                </button>
              )}
              {!view.typed && view.phase === "live" ? (
                <button type="button" className="secondary-button" onClick={() => voice.finishAnswer()}>
                  I've finished
                </button>
              ) : null}
              <button type="button" className="secondary-button" onClick={() => voice.end()}>
                End conversation
              </button>
            </>
          )}
        </div>

        <div className="tibi-conversation">
          {view.transcript.length === 0 && !speakingNow && !partial ? (
            <p className="tibi-empty">
              {active ? "Say hello. You can interrupt Tibi, or say pause, at any time." : "Your conversation with Tibi appears here."}
            </p>
          ) : null}
          {view.transcript.map((line, n) => (
            <div key={n} className={`tibi-line tibi-line--${line.role === "user" ? "you" : "tibi"}`}>
              <span className="tibi-who">{line.role === "user" ? "You" : "Tibi"}</span>
              <p>{line.content}</p>
            </div>
          ))}
          {speakingNow ? (
            <div className="tibi-line tibi-line--tibi tibi-line--live">
              <span className="tibi-who">Tibi</span>
              <p>{speakingNow}</p>
            </div>
          ) : null}
          {partial ? (
            <div className="tibi-line tibi-line--you tibi-line--live">
              <span className="tibi-who">You</span>
              <p>{partial}</p>
            </div>
          ) : null}
          {[view.quality, view.feedback, view.boundary].filter(Boolean).map((note) => (
            <p key={note} className="tibi-aside">
              {note}
            </p>
          ))}
          <div ref={transcriptEnd} />
        </div>

        <form className="tibi-type" onSubmit={send}>
          <input
            value={message}
            maxLength={1200}
            placeholder={view.phase !== "live" ? "Start a conversation to type to Tibi" : form.mode === "governance" ? "Your answer to Tibi's question…" : "Type a message to Tibi…"}
            disabled={view.phase !== "live"}
            onChange={(e) => setMessage(e.target.value)}
          />
          <button type="submit" className="secondary-button" disabled={view.phase !== "live" || !message.trim()}>
            Send
          </button>
        </form>
      </section>

      {side ? (
        <aside className="tibi-side" aria-label="Tibi settings">
          <section className="tibi-side-section">
            <h2>Session</h2>
            <label className="field-label">
              Mode
              <select value={form.mode} disabled={active} onChange={(e) => setForm({ ...form, mode: e.target.value as TibiMode })}>
                {MODES.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label className="field-label">
              Contributor
              <select value={form.contributor} disabled={active} onChange={(e) => setForm({ ...form, contributor: e.target.value })}>
                <option>Chris</option>
                <option>Dan</option>
              </select>
            </label>
            {form.mode === "interview" ? (
              <label className="field-label">
                Topic
                <select value={form.topic} disabled={active} onChange={(e) => setForm({ ...form, topic: e.target.value })}>
                  {topics.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.title}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            <label className="field-label">
              Tibi's voice
              <select value={form.voice} disabled={active} onChange={(e) => setForm({ ...form, voice: e.target.value })}>
                <option value="higgs">Higgs · male</option>
                <option value="higgs_female">Higgs · female</option>
              </select>
            </label>
            <label className="field-label">
              Input
              <select value={form.typed ? "typed" : "voice"} disabled={active} onChange={(e) => setForm({ ...form, typed: e.target.value === "typed" })}>
                <option value="voice">Voice</option>
                <option value="typed">Typing (Tibi still speaks)</option>
              </select>
            </label>
            <label className="cm-check">
              <input type="checkbox" checked={animation} onChange={(e) => { setAnimation(e.target.checked); remember("tibi-animation", e.target.checked); }} />
              Animation
            </label>
            <p className="muted-text tibi-side-note">
              {enabled} product records enabled for answers ·{" "}
              <button type="button" className="text-button" onClick={() => onOpenKnowledge()}>
                Tibi knowledge
              </button>
            </p>
          </section>
          <AudioDevices view={view} />
          <Evidence view={view} onOpenKnowledge={onOpenKnowledge} />
        </aside>
      ) : null}
    </div>
  );
}

function AudioDevices({ view }: { view: TibiView }) {
  const voice = tibiVoice();
  return (
    <section className="tibi-side-section">
      <h2>Audio devices</h2>
      <p className="muted-text tibi-side-note">Tibi remembers your choice. Until you choose, it prefers a Jabra headset.</p>
      <div className="tibi-devices">
        <label className="field-label">
          Microphone
          <select value={view.microphoneId} onChange={(e) => voice.chooseMicrophone(e.target.value)}>
            <option value="">Browser default</option>
            {view.microphones.map((d) => (
              <option key={d.id} value={d.id}>
                {d.label || "Microphone"}
              </option>
            ))}
          </select>
        </label>
        <label className="field-label">
          Speaker / headphones
          <select value={view.speakerId} disabled={!view.speakerSelectable} onChange={(e) => void voice.selectSpeaker(e.target.value)}>
            <option value="">System default</option>
            {view.speakers.map((d) => (
              <option key={d.id} value={d.id}>
                {d.label || "Speaker"}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="tibi-actions">
        {view.namesHidden ? (
          <button type="button" className="secondary-button" onClick={() => void voice.showDeviceNames().catch(() => undefined)}>
            Show device names
          </button>
        ) : null}
        <button type="button" className="secondary-button" onClick={() => void voice.refreshDevices()}>
          Refresh devices
        </button>
        <button type="button" className="secondary-button" onClick={() => void voice.testSpeaker()}>
          Test speaker
        </button>
      </div>
      <p className="muted-text">{view.speakerStatus}</p>
      {view.phase === "live" && !view.typed ? (
        <label className="field-label">
          Microphone level
          <meter className="tibi-level" min={0} max={100} value={view.level} />
        </label>
      ) : null}
    </section>
  );
}

function Evidence({ view, onOpenKnowledge }: { view: TibiView; onOpenKnowledge: (record?: string) => void }) {
  const details = view.details;
  const governance = Boolean(details?.grounding?.startsWith("governance"));
  const position = details?.governance;
  const note =
    view.mode === "interview"
      ? "Your captured wording is saved. Check it and propose it in Tibi knowledge."
      : governance
        ? `Governance interview${position?.total ? ` · question ${Math.min((position.position ?? 0) + 1, position.total)} of ${position.total}` : ""}. Answers are checked against the sources and wait for your approval on the Governance page.`
        : details?.grounding
          ? GROUNDING[details.grounding] ?? ""
          : "Evidence for each answer appears here.";
  return (
    <section className="tibi-side-section">
      <h2>{governance ? "The issue" : "What Tibi used"}</h2>
      <p className="muted-text tibi-side-note">{note}</p>
      <div className="result-list" style={{ gap: 10 }}>
        {(details?.evidence ?? []).map((row, n) => (
          <div className="result-card" key={`${row.id}-${n}`}>
            <div className="result-head">
              <b>{row.title}</b>
              {row.status ? <span className="status-pill">{row.status}</span> : null}
            </div>
            <p className="result-cite">{row.text}</p>
            {!governance ? (
              <button type="button" className="text-button" onClick={() => onOpenKnowledge(row.id)}>
                Open in Tibi knowledge
              </button>
            ) : null}
          </div>
        ))}
      </div>
      {view.check ? <p className="muted-text">{view.check}</p> : null}
    </section>
  );
}
