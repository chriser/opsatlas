import { useEffect, useState } from "react";
import { getTibiRecords, type TibiRecord, type TibiStatus } from "./api";
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

/** Talk with Tibi, native in the control panel; Tibi itself runs as its own service behind /services/tibi. */
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
  // What you said shows until it lands in the transcript below.
  const heard = [...view.transcript].reverse().find((line) => line.role === "user")?.content;
  const partial = view.partial && view.partial !== heard ? view.partial : "";

  function send(event: React.FormEvent) {
    event.preventDefault();
    voice.sendText(message);
    setMessage("");
  }

  return (
    <div className="view-stack">
      <div className="page-intro">
        <h1>Talk with Tibi</h1>
        <p>
          Chat, contribute product knowledge or resolve governance issues, by voice or by typing. Product answers are checked
          against approved OpsAtlas evidence; what Tibi captures waits for your approval.
        </p>
      </div>

      {status && !status.available ? (
        <div className="panel">
          <p className="muted-text" style={{ margin: 0, color: "var(--red)" }}>
            The Tibi service is not running. Start it with scripts/start-tiberius-sales.sh, then reload this page.
          </p>
        </div>
      ) : null}

      <div className="tibi-layout">
        <div className="view-stack">
          <div className="panel">
            <div className="panel-heading">
              <div>
                <h2>Session</h2>
                <p className="muted-text">
                  {enabled} product records enabled for answers ·{" "}
                  <button type="button" className="text-button" onClick={() => onOpenKnowledge()}>
                    Tibi knowledge
                  </button>
                </p>
              </div>
              <span className="status-pill">{view.state}</span>
            </div>

            {!active ? (
              <>
                <div className="tibi-form">
                  <label className="field-label">
                    Mode
                    <select value={form.mode} onChange={(e) => setForm({ ...form, mode: e.target.value as TibiMode })}>
                      {MODES.map(([value, label]) => (
                        <option key={value} value={value}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="field-label">
                    Contributor
                    <select value={form.contributor} onChange={(e) => setForm({ ...form, contributor: e.target.value })}>
                      <option>Chris</option>
                      <option>Dan</option>
                    </select>
                  </label>
                  {form.mode === "interview" ? (
                    <label className="field-label">
                      Topic
                      <select value={form.topic} onChange={(e) => setForm({ ...form, topic: e.target.value })}>
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
                    <select value={form.voice} onChange={(e) => setForm({ ...form, voice: e.target.value })}>
                      <option value="higgs">Higgs · male</option>
                      <option value="higgs_female">Higgs · female</option>
                    </select>
                  </label>
                  <label className="field-label">
                    Input
                    <select
                      value={form.typed ? "typed" : "voice"}
                      onChange={(e) => setForm({ ...form, typed: e.target.value === "typed" })}
                    >
                      <option value="voice">Voice</option>
                      <option value="typed">Typing (Tibi still speaks)</option>
                    </select>
                  </label>
                </div>
                <div className="tibi-actions">
                  <button
                    type="button"
                    className="primary-button"
                    disabled={status?.available === false}
                    onClick={() => void voice.start({ ...form })}
                  >
                    {form.mode === "governance"
                      ? "Start governance interview"
                      : form.mode === "interview"
                        ? "Start product interview"
                        : "Start with Tibi"}
                  </button>
                </div>
              </>
            ) : (
              <div className="tibi-actions">
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
              </div>
            )}
            {view.notice ? <p className="muted-text tibi-notice">{view.notice}</p> : null}
          </div>

          <div className="panel">
            <div className="panel-heading">
              <div>
                <h2>Conversation</h2>
                <p className="muted-text">{view.microphone || "You can interrupt Tibi, or say pause, at any time."}</p>
              </div>
            </div>
            <div className="tibi-reply" aria-live="polite">
              <span className="tibi-speaker">Tibi</span>
              {view.thinking ? <span className="tibi-thinking">Thinking…</span> : null}
              <p>{view.reply || (active ? "…" : "Start a session to talk with Tibi.")}</p>
            </div>
            {partial ? (
              <p className="tibi-partial">
                <span className="tibi-speaker">You</span> {partial}
              </p>
            ) : null}
            {[view.quality, view.feedback, view.boundary].filter(Boolean).map((note) => (
              <p key={note} className="muted-text">
                {note}
              </p>
            ))}
            <form className="tibi-type" onSubmit={send}>
              <input
                value={message}
                maxLength={1200}
                placeholder={form.mode === "governance" ? "Your answer to Tibi's question…" : "Type a message to Tibi…"}
                disabled={view.phase !== "live"}
                onChange={(e) => setMessage(e.target.value)}
              />
              <button type="submit" className="secondary-button" disabled={view.phase !== "live" || !message.trim()}>
                Send
              </button>
            </form>
            {view.transcript.length ? (
              <div className="tibi-transcript">
                {view.transcript.map((line, n) => (
                  <p key={n}>
                    <b>{line.role === "user" ? "You" : "Tibi"}:</b> {line.content}
                  </p>
                ))}
              </div>
            ) : null}
          </div>
        </div>

        <div className="view-stack">
          <AudioDevices view={view} />
          <Evidence view={view} onOpenKnowledge={onOpenKnowledge} />
        </div>
      </div>
    </div>
  );
}

function AudioDevices({ view }: { view: TibiView }) {
  const voice = tibiVoice();
  return (
    <div className="panel">
      <div className="panel-heading">
        <div>
          <h2>Audio devices</h2>
          <p className="muted-text">Tibi remembers your choice. Until you choose, it prefers a Jabra headset.</p>
        </div>
      </div>
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
    </div>
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
    <div className="panel">
      <div className="panel-heading">
        <div>
          <h2>{governance ? "The issue" : "Evidence for this answer"}</h2>
          <p className="muted-text">{note}</p>
        </div>
      </div>
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
    </div>
  );
}
