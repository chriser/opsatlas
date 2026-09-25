// Per-turn latency milestones on the page's monotonic clock; null means not observed.
// The same record the Tibi service stores for every turn (see services/sme_interviewer/web/timing.js).

const MARKS = [
  "capture_start",
  "speech_end",
  "endpoint",
  "encoded",
  "asr_requested",
  "final_transcript",
  "confirmation_start",
  "confirmed",
  "plan_requested",
  "first_token",
  "question_ready",
  "tts_requested",
  "audio_ready",
  "first_audio",
  "playback_start",
] as const;

export type Mark = (typeof MARKS)[number];

const PAGE_ID = crypto.randomUUID();

export class TurnTiming {
  origin: number;
  data: {
    version: number;
    id: string;
    page_id: string;
    generation_id: string;
    revision: number;
    sequence: number;
    source: string;
    runtime: string;
    endpoint_kind: string;
    status: string;
    marks: Record<Mark, number | null>;
  };

  constructor(
    private sessionId: string,
    revision: number,
    source: string,
    private send: (sessionId: string, data: unknown) => void,
  ) {
    this.origin = performance.now();
    this.data = {
      version: 1,
      id: crypto.randomUUID(),
      page_id: PAGE_ID,
      generation_id: crypto.randomUUID(),
      revision,
      sequence: 0,
      source,
      runtime: "unknown",
      endpoint_kind: "none",
      status: "open",
      marks: Object.fromEntries(MARKS.map((key) => [key, null])) as Record<Mark, number | null>,
    };
  }

  mark(key: Mark) {
    if (this.data.status !== "open" || this.data.marks[key] !== null) return;
    this.data.marks[key] = Math.round((performance.now() - this.origin) * 1000) / 1000;
    this.flush();
  }

  finish(status: string) {
    if (this.data.status !== "open") return;
    this.data.status = status;
    this.flush();
  }

  flush() {
    this.data.sequence++;
    this.send(this.sessionId, JSON.parse(JSON.stringify(this.data)));
  }
}
