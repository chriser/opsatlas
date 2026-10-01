import { Fragment, lazy, Suspense, useEffect, useRef, useState } from "react";
import {
  getActiveSpace,
  getTibiRecords,
  deleteProcessInterview,
  listProcessInterviews,
  listSpaces,
  SPACES_CHANGED,
  type ProcessInterviewSummary,
  type Space,
  type TibiRecord,
  type TibiStatus,
} from "./api";
import { InterviewMap } from "./tibi/InterviewMap";
import { MachineDetails, MachinePill, machineVerdict, useMachine } from "./tibi/Machine";
import { StepPanel } from "./tibi/StepPanel";
import type { StageState } from "./tibi/Spirit";
import { tibiVoice, type TibiMode, type TibiView } from "./tibi/voice";

export type { TibiMode } from "./tibi/voice";

const MODES: [TibiMode, string][] = [
  ["recall", "Chat with Tibi"],
  ["interview", "Contribute product knowledge"],
  ["governance", "Resolve governance issues"],
  ["rehearsal", "Sales rehearsal"],
  ["process", "Interview about a process"],
];

// What Tibi is doing with what it hears in a rehearsal: shown on the stage, so everyone in the room knows.
const HEARING: Record<string, string> = {
  observing: "Listening to the meeting · not kept",
  listening_for_name: "Listening for “Tibi” · not kept",
  addressed: "Listening for your request",
  answering: "Tibi is answering",
  muted: "Muted · not listening",
};

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
  if (view.rehearsal) {
    // A rehearsal is calm while Tibi only observes; it comes alive when asked.
    if (view.rehearsal.state === "muted") return "paused";
    if (view.rehearsal.state === "addressed") return "listening";
    if (view.rehearsal.state === "answering") return "thinking";
    return "idle";
  }
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
  const [form, setForm] = useState({
    mode,
    contributor: "Chris",
    topic: "",
    voice: "higgs",
    typed: false,
    customer: "",
    listenForName: false,
    keepTranscript: false,
    space: "",
  });
  // Process interviews (TIBI E5): the organisation spaces, this space's interviews to continue, and a step's comment.
  const [organisations, setOrganisations] = useState<Space[]>([]);
  const [interviews, setInterviews] = useState<ProcessInterviewSummary[]>([]);
  const [stepOn, setStepOn] = useState<string | null>(null);
  const [records, setRecords] = useState<TibiRecord[]>([]);
  const [message, setMessage] = useState("");
  const [side, setSide] = useState(() => remembered("tibi-side-open", true));
  const [animation, setAnimation] = useState(() => remembered("tibi-animation", true));
  const machine = useMachine();
  const [machineOpen, setMachineOpen] = useState(() => remembered("tibi-machine-open", false));
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

  useEffect(() => {
    const load = () =>
      listSpaces()
        .then(({ spaces }) => {
          const orgs = spaces.filter((s) => s.kind === "organisation" && s.status === "active");
          setOrganisations(orgs);
          setForm((current) => ({
            ...current,
            space: orgs.some((o) => o.id === current.space) ? current.space : (orgs.find((o) => o.id === getActiveSpace()) ?? orgs[0])?.id ?? "",
          }));
        })
        .catch(() => setOrganisations([]));
    void load();
    window.addEventListener(SPACES_CHANGED, load);
    return () => window.removeEventListener(SPACES_CHANGED, load);
  }, []);
  const processMode = form.mode === "process";
  // The list refreshes when the space changes, when an interview pauses or ends, and after a delete.
  const [listed, setListed] = useState(0);
  const [deleteError, setDeleteError] = useState("");
  useEffect(() => {
    if (!processMode || !form.space) return setInterviews([]);
    listProcessInterviews(form.space)
      .then((data) => setInterviews(data.interviews))
      .catch(() => setInterviews([]));
  }, [processMode, form.space, view.phase, listed]);
  async function removeInterview(i: ProcessInterviewSummary) {
    const what = `${i.participant || "Someone"}${i.processes.length ? ` · ${i.processes.map((p) => p.name || "unnamed").join(", ")}` : ""}`;
    if (!window.confirm(`Delete the interview with ${what}? Its notes, map and transcript are removed for good. Processes already saved to the space stay.`)) return;
    setDeleteError("");
    try {
      await deleteProcessInterview(i.id);
    } catch (error) {
      setDeleteError(error instanceof Error ? error.message : "The interview could not be deleted.");
    }
    setListed((n) => n + 1);
  }
  const organisation = organisations.find((o) => o.id === form.space);


  const topics = records.filter((r) => !r.provenance && r.kind !== "conversation");
  const enabled = records.filter((r) => r.eligible && r.kind !== "conversation").length;
  const active = view.phase === "starting" || view.phase === "live" || view.phase === "paused";
  // What you said shows until it lands in the transcript.
  const heard = [...view.transcript].reverse().find((line) => line.role === "user")?.content;
  const partial = view.partial && view.partial !== heard ? view.partial : "";
  const lastTibi = [...view.transcript].reverse().find((line) => line.role === "assistant")?.content;
  const speakingNow = view.reply && view.reply !== lastTibi && active ? view.reply : "";
  const stage = stageState(view);
  const verdict = machineVerdict(machine, view.voiceHealth);
  const engine = status?.service?.engine;

  useEffect(() => {
    transcriptEnd.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [view.transcript.length, view.meeting.length, speakingNow, partial]);

  const rehearsing = active && view.mode === "rehearsal";
  // Rehearsal shortcuts: T asks Tibi, Esc cancels the request, M mutes. Never while typing in a field.
  useEffect(() => {
    if (!rehearsing) return;
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target && (target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName))) return;
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      if (event.key === "t" || event.key === "T") {
        event.preventDefault();
        voice.askTibi();
      } else if (event.key === "Escape") {
        voice.cancelRequest();
      } else if (event.key === "m" || event.key === "M") {
        event.preventDefault();
        voice.setMuted(!tibiVoice().view.muted);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [rehearsing, voice]);

  function send(event: React.FormEvent) {
    event.preventDefault();
    if (rehearsing) voice.sendRehearsalLine(message, false);
    else voice.sendText(message);
    setMessage("");
  }

  function askTyped() {
    voice.sendRehearsalLine(message, true);
    setMessage("");
  }

  // The meeting lines heard after transcript line i, for a rehearsal's timeline.
  const heardAfter = (i: number) =>
    view.meeting
      .filter((line) => line.after === i)
      .map((line, n) => (
        <div key={`m-${i}-${n}`} className="tibi-line tibi-line--meeting">
          <span className="tibi-who">Meeting{line.kept ? "" : " · not kept"}</span>
          <p>{line.text}</p>
        </div>
      ));

  const startLabel =
    form.mode === "process"
      ? `Start process interview${organisation ? ` · ${organisation.name}` : ""}`
      : form.mode === "governance"
      ? "Start governance interview"
      : form.mode === "interview"
        ? "Start product interview"
        : form.mode === "rehearsal"
          ? "Start sales rehearsal"
          : "Start with Tibi";

  const interviewing = (active && view.mode === "process") || (!active && processMode && Boolean(view.processModel));
  const mapSpace = view.space || form.space;
  return (
    <div className={`tibi-room${side ? " tibi-room--side" : ""}${interviewing ? " tibi-room--process" : ""}`}>
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
            <MachinePill
              reading={machine}
              voice={view.voiceHealth}
              open={machineOpen}
              onToggle={() => {
                setMachineOpen(!machineOpen);
                remember("tibi-machine-open", !machineOpen);
              }}
            />
            <span className={`status-pill tibi-state tibi-state--${stage}`}>{view.state}</span>
            <button type="button" className="secondary-button" aria-expanded={side} onClick={() => { setSide(!side); remember("tibi-side-open", !side); }}>
              {side ? "Hide settings" : "Settings"}
            </button>
          </div>
        </header>

        {machineOpen ? <MachineDetails reading={machine} voice={view.voiceHealth} /> : null}

        {status && !status.available ? (
          <p className="tibi-alert">Tibi is not running. Use Restart services under Status, then start again.</p>
        ) : status?.busy && !active ? (
          <p className="tibi-alert tibi-alert--soft">{status.busy}</p>
        ) : !machineOpen && verdict.advice && (verdict.level === "strained" || (verdict.level === "busy" && !active)) ? (
          // The voice at risk, said on the stage; before a start, also a model of another app's that could disturb it.
          <p className={`tibi-alert${verdict.level === "busy" ? " tibi-alert--soft" : ""}`}>{verdict.advice}</p>
        ) : null}

        <div className="tibi-stage">
          {animation ? (
            <Suspense fallback={<div className="tibi-spirit" />}>
              <Spirit state={stage} levels={() => voice.levels()} />
            </Suspense>
          ) : (
            <div className={`tibi-spirit tibi-spirit--${stage}`} aria-hidden="true" />
          )}
          {rehearsing && view.rehearsal ? (
            <div className={`tibi-hearing tibi-hearing--${view.rehearsal.state}`} role="status" aria-live="polite">
              <span className="tibi-hearing-dot" aria-hidden="true" />
              {HEARING[view.rehearsal.state] ?? view.rehearsal.message}
              {view.rehearsal.keepTranscript ? <span className="tibi-hearing-kept">Transcript kept</span> : null}
            </div>
          ) : null}
          <div className="tibi-stage-caption" aria-live="polite">
            {view.thinking ? "Thinking…" : rehearsing && view.rehearsal ? view.rehearsal.message : view.notice || (active ? "" : "Press start when you are ready.")}
          </div>
        </div>

        <div className="tibi-controls">
          {!active ? (
            <button
              type="button"
              className="primary-button tibi-start"
              disabled={status?.available === false || (processMode && !form.space)}
              title={processMode && !form.space ? "Create an organisation space in Governance Review first" : undefined}
              onClick={() => void voice.start({ ...form, spaceName: organisation?.name ?? "" })}
            >
              {startLabel}
            </button>
          ) : (
            <>
              {rehearsing && view.phase === "live" ? (
                <>
                  {view.rehearsal?.state === "addressed" ? (
                    <button type="button" className="secondary-button" onClick={() => voice.cancelRequest()} title="Esc">
                      Cancel request <kbd>Esc</kbd>
                    </button>
                  ) : (
                    <button type="button" className="primary-button tibi-ask" onClick={() => voice.askTibi()} title="T">
                      Ask Tibi <kbd>T</kbd>
                    </button>
                  )}
                  {!view.typed ? (
                    <button
                      type="button"
                      className={view.muted ? "primary-button" : "secondary-button"}
                      onClick={() => voice.setMuted(!view.muted)}
                      title="M"
                    >
                      {view.muted ? "Unmute" : "Mute"} <kbd>M</kbd>
                    </button>
                  ) : null}
                </>
              ) : null}
              {view.phase === "paused" ? (
                <button type="button" className="primary-button" onClick={() => void voice.resume()}>
                  Resume
                </button>
              ) : (
                <button type="button" className="secondary-button" disabled={view.phase === "starting"} onClick={() => voice.pause()}>
                  Pause
                </button>
              )}
              {!view.typed && view.phase === "live" && !rehearsing ? (
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
          {view.transcript.length === 0 && view.meeting.length === 0 && !speakingNow && !partial ? (
            <p className="tibi-empty">
              {rehearsing
                ? "Start your pitch. Tibi listens and helps only when you ask."
                : active
                  ? "Say hello. You can interrupt Tibi, or say pause, at any time."
                  : "Your conversation with Tibi appears here."}
            </p>
          ) : null}
          {view.transcript.map((line, n) => (
            <Fragment key={n}>
              {heardAfter(n)}
              <div className={`tibi-line tibi-line--${line.role === "user" ? "you" : "tibi"}`}>
                <span className="tibi-who">{line.role === "user" ? (view.mode === "rehearsal" ? "You asked Tibi" : "You") : "Tibi"}</span>
                <p>{line.content}</p>
              </div>
            </Fragment>
          ))}
          {heardAfter(view.transcript.length)}
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
            maxLength={processMode ? 8000 : 1200}
            placeholder={view.phase !== "live" ? "Start a conversation to type to Tibi" : form.mode === "governance" || form.mode === "process" ? "Your answer to Tibi's question…" : "Type a message to Tibi…"}
            disabled={view.phase !== "live"}
            onChange={(e) => setMessage(e.target.value)}
          />
          <button type="submit" className="secondary-button" disabled={view.phase !== "live" || !message.trim()}>
            {rehearsing ? "Add to meeting" : "Send"}
          </button>
          {rehearsing ? (
            <button type="button" className="primary-button" disabled={view.phase !== "live" || !message.trim()} onClick={askTyped}>
              Ask Tibi
            </button>
          ) : null}
        </form>
      </section>

      {interviewing ? (
        <section className="tibi-map-column">
          <InterviewMap
            space={mapSpace}
            model={view.processModel}
            onStep={(id) => setStepOn(id)}
            narrating={view.narrating}
          />
          {stepOn && view.processModel ? (
            <StepPanel
              model={view.processModel}
              stepId={stepOn}
              live={view.phase === "live"}
              onEdit={(change) => voice.processEdit(change)}
              onComment={(text) => {
                const label = view.processModel?.processes.flatMap((p) => p.steps).find((st) => st.id === stepOn)?.label ?? "this step";
                voice.sendText(`About the step "${label}": ${text}`);
              }}
              onClose={() => setStepOn(null)}
            />
          ) : null}
          <p className="imap-footer">
            {view.notes === "working" ? "Tibi is noting your last answer…" : view.notes === "failed" ? "The last answer could not be noted; it is kept and will be retried." : "Everything is saved as you go."}
            {view.sessionId ? (
              <button type="button" className="text-button" onClick={() => (window.location.hash = `#process-review:${view.sessionId}`)}>
                Review what was captured
              </button>
            ) : null}
          </p>
        </section>
      ) : null}

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
            {form.mode === "rehearsal" ? (
              <>
                <label className="field-label">
                  Customer (optional)
                  <input
                    value={form.customer}
                    maxLength={200}
                    disabled={active}
                    placeholder="e.g. regional bank, head of operations"
                    onChange={(e) => setForm({ ...form, customer: e.target.value })}
                  />
                </label>
                <label className="cm-check">
                  <input
                    type="checkbox"
                    checked={rehearsing && view.rehearsal ? view.rehearsal.listenForName : form.listenForName}
                    onChange={(e) => {
                      setForm({ ...form, listenForName: e.target.checked });
                      if (rehearsing) voice.setRehearsalOptions({ listenForName: e.target.checked });
                    }}
                  />
                  Listen for “Tibi”
                </label>
                <label className="cm-check">
                  <input
                    type="checkbox"
                    checked={rehearsing && view.rehearsal ? view.rehearsal.keepTranscript : form.keepTranscript}
                    onChange={(e) => {
                      setForm({ ...form, keepTranscript: e.target.checked });
                      if (rehearsing) voice.setRehearsalOptions({ keepTranscript: e.target.checked });
                    }}
                  />
                  Keep a meeting transcript
                </label>
                <p className="muted-text tibi-side-note">
                  What is kept: your requests to Tibi and its replies, in the Conversation Log; the customer description, with the
                  rehearsal; and the meeting's own lines only if you keep a transcript, from the moment you switch it on (switching it off
                  keeps what was already saved). Customer remarks never become product knowledge.
                </p>
              </>
            ) : null}
            {processMode ? (
              <>
                <label className="field-label">
                  Organisation
                  <select value={form.space} disabled={active} onChange={(e) => setForm({ ...form, space: e.target.value })}>
                    {organisations.length ? null : <option value="">No organisation spaces yet</option>}
                    {organisations.map((o) => (
                      <option key={o.id} value={o.id}>
                        {o.name}
                      </option>
                    ))}
                  </select>
                </label>
                <p className="muted-text tibi-side-note">
                  Tibi asks who you are and which processes you would like to describe, then walks through each one with you. What you
                  say is saved in {organisation?.name ?? "the organisation's space"} as you go, for you to review with its map. Made-up or
                  anonymised information only.
                </p>
                {interviews.length ? (
                  <div className="tibi-continue">
                    <b>Interviews in {organisation?.name}</b>
                    {interviews.slice(0, 8).map((i) => (
                      <div key={i.id} className="tibi-continue-row">
                        <span>
                          {i.participant || "Someone"}
                          {i.processes.length ? ` · ${i.processes.map((p) => p.name || "unnamed").join(", ")}` : ""}
                          <small>
                            {i.processes.reduce((n, p) => n + p.steps, 0)} steps{i.open ? ` · ${i.open} to check` : ""} ·{" "}
                            {i.status === "active" ? "open" : i.status} · {new Date(i.updated_at).toLocaleString()}
                          </small>
                        </span>
                        <span className="tibi-continue-actions">
                          <button
                            type="button"
                            className="secondary-button"
                            disabled={active}
                            onClick={() => void voice.start({ ...form, mode: "process", spaceName: organisation?.name ?? "", resumeId: i.id })}
                          >
                            Continue
                          </button>
                          <button type="button" className="text-button" onClick={() => (window.location.hash = `#process-review:${i.id}`)}>
                            Review
                          </button>
                          <button type="button" className="text-button danger-text" disabled={active} onClick={() => void removeInterview(i)}>
                            Delete
                          </button>
                        </span>
                      </div>
                    ))}
                    {deleteError ? <p className="tibi-continue-error" role="alert">{deleteError}</p> : null}
                  </div>
                ) : null}
              </>
            ) : (
              <label className="field-label">
                Contributor
                <select value={form.contributor} disabled={active} onChange={(e) => setForm({ ...form, contributor: e.target.value })}>
                  <option>Chris</option>
                  <option>Dan</option>
                </select>
              </label>
            )}
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
    view.mode === "process"
      ? "A process interview: Tibi only asks and listens. What you say goes onto the process map, for you to review."
      : view.mode === "interview"
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
