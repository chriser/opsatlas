import { useEffect, useState } from "react";
import { getMachine, type MachineReading, type MachineUser } from "../api";
import type { TibiView } from "./voice";

// How busy this Mac is, on the Talk with Tibi page (TIBI E2; the Human's request of 1 October 2026: "some kind of
// indicator on how busy the computer is, or performant the voice is"). Tibi's voice is generated on the graphics
// processor every local model shares; when another app's model runs beside it, the voice breaks up.

const EVERY = 3000; // ms between readings while the page is shown
type Level = "ok" | "busy" | "strained";
const RANK: Record<Level, number> = { ok: 0, busy: 1, strained: 2 };
const TONE: Record<Level, string> = { ok: "good", busy: "warn", strained: "danger" };
const WORD: Record<Level, string> = { ok: "quiet", busy: "busy", strained: "strained" };
const COLOUR: Record<MachineUser["group"], string> = {
  other_models: "#dc2626",
  models: "#6366f1",
  voice: "#d90066",
  screen: "#94a3b8",
  other: "#cbd5e1",
};
type VoiceHealth = TibiView["voiceHealth"];

/** A reading every few seconds while the page is shown (none while it is hidden). */
export function useMachine(): MachineReading | null {
  const [reading, setReading] = useState<MachineReading | null>(null);
  useEffect(() => {
    let stopped = false;
    let timer = 0;
    const tick = async () => {
      if (!document.hidden) {
        const next = await getMachine().catch(() => null);
        if (!stopped) setReading(next);
      }
      if (!stopped) timer = window.setTimeout(tick, EVERY);
    };
    void tick();
    return () => {
      stopped = true;
      window.clearTimeout(timer);
    };
  }, []);
  return reading;
}

/** How the voice did with the last reply: written only (too late), gaps while playing, or generated too slowly. */
function voiceVerdict(voice: VoiceHealth): [Level, string] {
  if (!voice) return ["ok", ""];
  if (voice.late) return ["strained", "Tibi's last reply was written only: its voice was not ready in time."];
  if (voice.gaps >= 3 || (voice.speed !== null && voice.speed < 1))
    return ["strained", `Tibi's voice broke up in the last reply${voice.gaps ? ` (${voice.gaps} gaps)` : ""}: it was generated slower than it plays.`];
  if (voice.gaps || (voice.speed !== null && voice.speed < 1.15))
    return ["busy", "Tibi's voice only just kept up in the last reply."];
  return ["ok", ""];
}

/** The level and the advice to show: the machine's, or the voice's when that is worse. */
export function machineVerdict(reading: MachineReading | null, voice: VoiceHealth): { level: Level; advice: string } {
  const machine: [Level, string] = reading?.available && reading.level ? [reading.level, reading.advice ?? ""] : ["ok", ""];
  const spoken = voiceVerdict(voice);
  const [level, advice] = RANK[spoken[0]] > RANK[machine[0]] ? spoken : machine;
  return { level, advice: advice || spoken[1] };
}

function voiceLine(voice: VoiceHealth): string {
  if (!voice) return "Not measured yet: it shows after Tibi's next reply.";
  if (voice.late) return "The last reply was written only: the voice was not ready in time.";
  const speed = voice.speed !== null ? `generated at ${voice.speed.toFixed(2)}× real time` : "speed not reported";
  const gaps = voice.gaps ? `${voice.gaps} gap${voice.gaps === 1 ? "" : "s"} while playing` : "no gaps";
  return `Last reply: ${speed}, ${gaps}.`;
}

/** The pill by Tibi's state; its details open below the page header. */
export function MachinePill({ reading, voice, open, onToggle }: {
  reading: MachineReading | null;
  voice: VoiceHealth;
  open: boolean;
  onToggle: () => void;
}) {
  if (!reading?.available) return null;
  const { level } = machineVerdict(reading, voice);
  return (
    <button
      type="button"
      className={`status-pill status-pill--${TONE[level]} tibi-machine-pill`}
      aria-expanded={open}
      title="How busy this Mac is, and how Tibi's voice is keeping up"
      onClick={onToggle}
    >
      Mac {WORD[level]} · GPU {reading.gpu?.busy ?? 0}%
    </button>
  );
}

export function MachineDetails({ reading, voice }: { reading: MachineReading | null; voice: VoiceHealth }) {
  if (!reading?.available || !reading.gpu) return null;
  const { advice } = machineVerdict(reading, voice);
  const busy = reading.gpu.users.filter((u) => u.share > 0);
  const memory = reading.memory;
  return (
    <section className="tibi-machine" aria-label="How busy this Mac is">
      {advice ? <p className="tibi-machine-advice">{advice}</p> : null}
      <div className="tibi-machine-row">
        <span className="tibi-machine-what">Graphics processor</span>
        <span>
          {reading.gpu.busy}% busy over the last {reading.window ?? 0} s
          <span className="tibi-machine-bar" aria-hidden="true">
            {busy.map((u) => (
              <span key={u.group} style={{ width: `${u.share}%`, background: COLOUR[u.group] }} />
            ))}
          </span>
          <span className="tibi-machine-users">
            {reading.gpu.users.map((u) => (
              <span key={u.group}>
                <i style={{ background: COLOUR[u.group] }} aria-hidden="true" />
                {u.label} {u.share}%
                {u.models?.length ? ` · ${u.models.join(", ")}` : ""}
                {u.gb ? ` · holds ${u.gb} GB` : ""}
              </span>
            ))}
          </span>
        </span>
      </div>
      <div className="tibi-machine-row">
        <span className="tibi-machine-what">Tibi's voice</span>
        <span>
          {voiceLine(voice)} It keeps up while it is generated faster than it plays (above 1×); below that, playback
          runs out and the voice breaks up.
        </span>
      </div>
      {memory ? (
        <div className="tibi-machine-row">
          <span className="tibi-machine-what">Memory</span>
          <span>
            {memory.free_pct}% free of {memory.total_gb} GB · pressure {memory.pressure}
            {memory.swap_used_gb !== null ? ` · ${memory.swap_used_gb} GB swapped out` : ""}
            {memory.swapping ? " · swapping now" : ""}
          </span>
        </div>
      ) : null}
      {reading.cpu ? (
        <div className="tibi-machine-row">
          <span className="tibi-machine-what">Processors</span>
          <span>
            {reading.cpu.busy}% busy (load {reading.cpu.load} on {reading.cpu.cores} cores)
          </span>
        </div>
      ) : null}
      <div className="tibi-machine-row">
        <span className="tibi-machine-what">Loaded models</span>
        <span>
          {reading.models === null || reading.models === undefined
            ? "OpsAtlas's model server did not answer."
            : reading.models.length
              ? reading.models.map((m) => `${m.role ? `${m.role}: ` : ""}${m.name}, ${m.gb} GB`).join(" · ")
              : "None loaded now."}
        </span>
      </div>
    </section>
  );
}
