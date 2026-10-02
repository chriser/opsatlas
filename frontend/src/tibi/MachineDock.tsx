// How busy this Mac is, and what needs attention, always in view at the foot of the sidebar (OBS F7; the Human's
// request of 2 October 2026: "more GPU and Memory status into a sidebar; So it is always visible. all warnings,
// messages should appear in sidebar so we don't disrupt the page layout itself"). The details open beside the
// sidebar, over the page, and never push it down.
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { MachineReading } from "../api";
import { NOTICE_EVENT, type NoticeTone, type PageNotice } from "../notices";
import { COLOUR, MachineDetails, machineVerdict, useMachine, WORD, type Level } from "./Machine";
import { tibiVoice, type TibiView } from "./voice";

/** A message for the sidebar: what needs attention, said once, in place of an alert on the page. */
export interface SidebarNote {
  key: string;
  tone: NoticeTone;
  text: string;
}

const DURING = 3000; // ms between readings during a conversation with Tibi
const IDLE = 10_000; // and otherwise
const FADE = 8000; // ms a page's confirmation stays
const KEEP = 4; // page messages kept at once, the newest last

/** What pages said (notify): a confirmation fades, a warning stays until it is hidden. */
function usePageNotices(): [PageNotice[], (id: number) => void] {
  const [notices, setNotices] = useState<PageNotice[]>([]);
  useEffect(() => {
    const timers = new Set<number>();
    const onNotice = (event: Event) => {
      const notice = (event as CustomEvent<PageNotice>).detail;
      setNotices((now) => [...now.filter((n) => n.text !== notice.text), notice].slice(-KEEP));
      if (notice.tone === "good" || notice.tone === "info") {
        const timer = window.setTimeout(() => {
          timers.delete(timer);
          setNotices((now) => now.filter((n) => n.id !== notice.id));
        }, FADE);
        timers.add(timer);
      }
    };
    window.addEventListener(NOTICE_EVENT, onNotice);
    return () => {
      window.removeEventListener(NOTICE_EVENT, onNotice);
      for (const timer of timers) window.clearTimeout(timer);
    };
  }, []);
  return [notices, (id) => setNotices((now) => now.filter((n) => n.id !== id))];
}
const LOW_FREE = 20; // % of memory free below which the Mac starts swapping (services/opsatlas_sales/machine.py)

type Signals = Pick<TibiView, "phase" | "voiceHealth" | "quality">;
const pick = (view: TibiView): Signals => ({ phase: view.phase, voiceHealth: view.voiceHealth, quality: view.quality });

/** What the sidebar needs of Tibi's voice: whether a conversation is on, how the last reply's voice kept up, and the
 * voice's own notice. It renders again only when one of them changes. */
function useVoiceSignals(): Signals {
  const [signals, setSignals] = useState<Signals>(() => pick(tibiVoice().view));
  useEffect(
    () =>
      tibiVoice().subscribe((view) =>
        setSignals((now) => (now.phase === view.phase && now.voiceHealth === view.voiceHealth && now.quality === view.quality ? now : pick(view))),
      ),
    [],
  );
  return signals;
}

function memoryTone(memory: NonNullable<MachineReading["memory"]>): Level {
  if (memory.free_pct < LOW_FREE && memory.swapping) return "strained";
  if (memory.free_pct < LOW_FREE || memory.pressure !== "normal") return "busy";
  return "ok";
}

/** The messages and the meters, pinned below the menu. ``machine``: whether this person may read the Mac's load
 * (it comes with Tibi). */
export function SidebarDock({ notes, machine }: { notes: SidebarNote[]; machine: boolean }) {
  const voice = useVoiceSignals();
  const talking = voice.phase === "starting" || voice.phase === "live" || voice.phase === "paused";
  const reading = useMachine(talking ? DURING : IDLE, machine);
  const [open, setOpen] = useState(false);
  const [dismissed, setDismissed] = useState<Record<string, string>>({});
  const [pageNotices, dropNotice] = usePageNotices();
  const toggle = useRef<HTMLButtonElement>(null);
  const verdict = machineVerdict(reading, voice.voiceHealth);
  const available = Boolean(machine && reading?.available && reading.gpu);

  // During a conversation Tibi's own voice fills the graphics processor, so "busy" is said only before one starts.
  const all: (SidebarNote & { mark: string })[] = [
    ...notes.map((n) => ({ ...n, mark: n.text })),
    ...(verdict.advice && (verdict.level === "strained" || (verdict.level === "busy" && !talking))
      ? [{ key: "machine", tone: verdict.level === "strained" ? ("danger" as const) : ("warn" as const), text: verdict.advice, mark: verdict.level }]
      : []),
    ...(voice.quality ? [{ key: "voice-quality", tone: "warn" as const, text: voice.quality, mark: voice.quality }] : []),
    ...pageNotices.map((n) => ({ key: `page-${n.id}`, tone: n.tone, text: n.text, mark: n.text })),
  ];
  const shown = all.filter((n) => dismissed[n.key] !== n.mark);
  const hide = (note: SidebarNote & { mark: string }) => {
    if (note.key.startsWith("page-")) dropNotice(Number(note.key.slice(5)));
    else setDismissed((d) => ({ ...d, [note.key]: note.mark }));
  };

  return (
    <div className="sidebar-dock">
      {shown.length ? (
        <ul className="sidebar-notes" aria-live="polite" aria-label="Messages">
          {shown.map((note) => (
            <li key={note.key} className={`sidebar-note sidebar-note--${note.tone}`} role={note.tone === "danger" ? "alert" : undefined}>
              <span className="sidebar-note-text">{note.text}</span>
              <button
                type="button"
                className="sidebar-note-close"
                aria-label="Hide this message"
                title="Hide until it changes"
                onClick={() => hide(note)}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      {available && reading?.gpu ? (
        <button
          ref={toggle}
          type="button"
          className={`sidebar-machine sidebar-machine--${verdict.level}`}
          aria-expanded={open}
          title="How busy this Mac is, and how Tibi's voice is keeping up"
          onClick={() => setOpen(!open)}
        >
          <span className="sidebar-machine-head">
            <span className={`sidebar-machine-light sidebar-machine-light--${verdict.level}`} aria-hidden="true" />
            <b>Mac {WORD[verdict.level]}</b>
            <span className="sidebar-machine-more">{open ? "Hide" : "Details"}</span>
          </span>
          <span className="sidebar-machine-meter">
            <span className="sidebar-machine-what">GPU</span>
            <span className="sidebar-machine-bar" aria-hidden="true">
              {reading.gpu.users
                .filter((u) => u.share > 0)
                .map((u) => (
                  <span key={u.group} style={{ width: `${u.share}%`, background: COLOUR[u.group] }} />
                ))}
            </span>
            <span className="sidebar-machine-value">{reading.gpu.busy}%</span>
          </span>
          {reading.memory ? (
            <span className="sidebar-machine-meter">
              <span className="sidebar-machine-what">Memory</span>
              <span className="sidebar-machine-bar" aria-hidden="true">
                <span className={`sidebar-machine-used sidebar-machine-used--${memoryTone(reading.memory)}`} style={{ width: `${100 - reading.memory.free_pct}%` }} />
              </span>
              <span className="sidebar-machine-value">
                {reading.memory.free_pct}% free{reading.memory.swapping ? " · swapping" : ""}
              </span>
            </span>
          ) : null}
        </button>
      ) : null}
      {open && available ? (
        <MachineFlyout reading={reading} voice={voice.voiceHealth} toggle={toggle} onClose={() => setOpen(false)} />
      ) : null}
    </div>
  );
}

/** The details, beside the sidebar and over the page: Esc, a click elsewhere or the close button puts them away. */
function MachineFlyout({ reading, voice, toggle, onClose }: {
  reading: MachineReading | null;
  voice: TibiView["voiceHealth"];
  toggle: React.RefObject<HTMLButtonElement | null>;
  onClose: () => void;
}) {
  const panel = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    const onDown = (event: MouseEvent) => {
      const target = event.target as Node;
      if (!panel.current?.contains(target) && !toggle.current?.contains(target)) onClose();
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onDown);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onDown);
    };
  }, [onClose, toggle]);
  return createPortal(
    <div ref={panel} className="machine-flyout" role="dialog" aria-label="How busy this Mac is">
      <div className="machine-flyout-head">
        <b>How busy this Mac is</b>
        <button type="button" className="text-button" onClick={onClose}>
          Close
        </button>
      </div>
      <MachineDetails reading={reading} voice={voice} />
    </div>,
    document.body,
  );
}
