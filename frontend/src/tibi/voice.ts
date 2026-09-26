// Talk with Tibi, natively in the control panel: the browser side of Tibi's voice loop.
//
// Captures the microphone at 16 kHz through an AudioWorklet, streams it to the Tibi service over its live
// socket (through the OpsAtlas gateway), and plays Tibi's streamed speech with barge-in: speaking over Tibi
// starts a new turn and discards the old audio. The same protocol as the Tibi service's reference client
// (services/sme_interviewer/web/conversation.js), for chat, product interviews and governance interviews.
//
// One client for the page's lifetime, outside React: a conversation keeps going while you look at another
// page (for example the Governance page during a governance interview).

import { record } from "../activity";
import { getTibiServiceToken, signInToken, tibiServicePost } from "../api";
import { TurnTiming } from "./timing";

export type TibiMode = "recall" | "interview" | "governance" | "rehearsal";

/** Sales rehearsal (TIBI E3): what Tibi is doing with what it hears, shown so everyone in the room knows. */
export interface RehearsalState {
  state: "observing" | "listening_for_name" | "addressed" | "answering" | "muted";
  message: string;
  listenForName: boolean;
  keepTranscript: boolean;
}

export interface TibiEvidenceRow {
  id: string;
  title: string;
  text: string;
  status?: string;
}

export interface TibiReplyDetails {
  route?: string;
  grounding?: string;
  evidence: TibiEvidenceRow[];
  governance?: { position: number | null; total: number } | null;
}

export interface DeviceOption {
  id: string;
  label: string;
}

export interface TibiView {
  phase: "idle" | "starting" | "live" | "paused" | "closed";
  state: string;
  notice: string;
  thinking: boolean;
  reply: string;
  partial: string;
  level: number;
  transcript: { role: string; content: string }[];
  details: TibiReplyDetails | null;
  check: string;
  quality: string;
  feedback: string;
  boundary: string;
  microphone: string;
  typed: boolean;
  mode: TibiMode;
  microphones: DeviceOption[];
  speakers: DeviceOption[];
  microphoneId: string;
  speakerId: string;
  speakerStatus: string;
  namesHidden: boolean;
  speakerSelectable: boolean;
  rehearsal: RehearsalState | null;
  /** Meeting lines heard in a rehearsal, each placed after the transcript line it followed. */
  meeting: { text: string; after: number; kept: boolean }[];
  muted: boolean;
}

export interface StartOptions {
  mode: TibiMode;
  contributor: string;
  topic: string;
  voice: string;
  typed: boolean;
  customer?: string;
  listenForName?: boolean;
  keepTranscript?: boolean;
}

type SinkContext = AudioContext & { setSinkId?: (id: string) => Promise<void>; sinkId?: string };
type Message = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
interface Session {
  id: string;
  revision: number;
  social_transcript?: { role: string; content: string }[];
  social_dialogue?: { role: string; content: string }[];
}

const SAVED = { microphone: "tibi.microphone", speaker: "tibi.speaker" };
const remembered = {
  get(key: string): string | null {
    try {
      return localStorage.getItem(key);
    } catch {
      return null;
    }
  },
  set(key: string, value: string) {
    try {
      localStorage.setItem(key, value);
    } catch {
      /* private browsing: the choice lasts for this page only */
    }
  },
};

/** The device to use: the one in use if still present, else the one last chosen, else a Jabra headset. */
function choose(options: DeviceOption[], key: string, current: string): string {
  if (current && options.some((o) => o.id === current)) return current;
  const saved = remembered.get(key);
  if (saved !== null) return options.find((o) => o.label === saved)?.id ?? "";
  const jabra =
    options.find((o) => /jabra/i.test(o.label) && /bluetooth/i.test(o.label)) ?? options.find((o) => /jabra/i.test(o.label));
  return jabra?.id ?? "";
}

function checkText(check: { status: string; question?: string }): string {
  if (check.status === "possible_conflict") return `Evidence check — a question for review: ${check.question ?? ""}`;
  if (check.status === "consistent") return "The evidence check found no mismatch; it is not factual approval.";
  if (check.status === "unavailable") return "The background evidence check was unavailable.";
  return "The background check found no evidence either way.";
}

const INITIAL: TibiView = {
  phase: "idle",
  state: "Ready",
  notice: "",
  thinking: false,
  reply: "",
  partial: "",
  level: 0,
  transcript: [],
  details: null,
  check: "",
  quality: "",
  feedback: "",
  boundary: "",
  microphone: "",
  typed: false,
  mode: "recall",
  rehearsal: null,
  meeting: [],
  muted: false,
  microphones: [],
  speakers: [],
  microphoneId: "",
  speakerId: "",
  speakerStatus: "Tibi uses your system default output.",
  namesHidden: false,
  speakerSelectable: typeof (AudioContext.prototype as SinkContext).setSinkId === "function",
};

export class TibiVoice {
  view: TibiView = INITIAL;
  private listeners = new Set<(view: TibiView) => void>();
  private session: Session | null = null;
  private socket: WebSocket | null = null;
  private context: SinkContext | null = null;
  private processor: AudioWorkletNode | null = null;
  private input: MediaStreamAudioSourceNode | null = null;
  private stream: MediaStream | null = null;
  // Levels for the stage animation: Tibi's voice as it plays, and the microphone (OBS S13).
  private tibiMeter: AnalyserNode | null = null;
  private micMeter: AnalyserNode | null = null;
  private meterData = new Float32Array(1024);
  private spectrum = new Uint8Array(512);
  private startedAt = 0;
  private slowStart: number | null = null;
  private captureReady = false;
  private enabled = false;
  private generation = "";
  private sequence = 0;
  private frames = 0;
  private cuePlaying = false;
  private timingGeneration: string | null = null;
  private trace: TurnTiming | null = null;
  private streamStart = 0;
  private speechDone = false;
  private audioDrained = true;
  private acceptAudio = true;
  private epoch = 0;

  constructor() {
    navigator.mediaDevices?.addEventListener?.("devicechange", () => void this.refreshDevices());
    window.addEventListener("pagehide", () => this.shutdown("abandoned"));
    void this.refreshDevices();
  }

  subscribe(listener: (view: TibiView) => void): () => void {
    this.listeners.add(listener);
    listener(this.view);
    return () => {
      this.listeners.delete(listener);
    };
  }

  private set(patch: Partial<TibiView>) {
    this.view = { ...this.view, ...patch };
    for (const listener of this.listeners) listener(this.view);
  }

  // ---- devices ------------------------------------------------------------------------

  /** Device names appear only once the browser has microphone permission. */
  async refreshDevices() {
    const devices = (await navigator.mediaDevices?.enumerateDevices?.().catch(() => [])) ?? [];
    const list = (kind: MediaDeviceKind) =>
      devices.filter((d) => d.kind === kind && d.deviceId && d.deviceId !== "default").map((d) => ({ id: d.deviceId, label: d.label }));
    const microphones = list("audioinput");
    const speakers = list("audiooutput");
    const namesHidden = devices.some((d) => (d.kind === "audioinput" || d.kind === "audiooutput") && !d.label);
    const microphoneId = choose(microphones, SAVED.microphone, this.view.microphoneId);
    const speakerId = choose(speakers, SAVED.speaker, this.view.speakerId);
    this.set({ microphones, speakers, namesHidden, microphoneId });
    if (speakerId !== this.view.speakerId || !this.view.speakerStatus.startsWith("Output")) await this.selectSpeaker(speakerId, false);
  }

  async showDeviceNames() {
    const permission = await navigator.mediaDevices.getUserMedia({ audio: true });
    permission.getTracks().forEach((track) => track.stop());
    await this.refreshDevices();
  }

  chooseMicrophone(id: string) {
    remembered.set(SAVED.microphone, this.view.microphones.find((m) => m.id === id)?.label ?? "");
    this.set({
      microphoneId: id,
      notice: this.view.phase === "live" && !this.view.typed ? "The new microphone is used from the next Resume." : this.view.notice,
    });
  }

  async selectSpeaker(id: string, remember = true) {
    const label = this.view.speakers.find((s) => s.id === id)?.label || "System default";
    if (remember) remembered.set(SAVED.speaker, id ? label : "");
    try {
      if (this.context && typeof this.context.setSinkId === "function" && this.context.sinkId !== id) await this.context.setSinkId(id);
      this.set({ speakerId: id, speakerStatus: `Output: ${label}` });
    } catch {
      this.set({ speakerStatus: "Could not switch to that speaker. Check it is connected, or choose another." });
    }
  }

  async testSpeaker() {
    try {
      await this.prepareOutput();
      const context = this.context!;
      const tone = context.createOscillator();
      const gain = context.createGain();
      const now = context.currentTime;
      tone.frequency.value = 440;
      gain.gain.setValueAtTime(0, now);
      gain.gain.linearRampToValueAtTime(0.06, now + 0.02);
      gain.gain.linearRampToValueAtTime(0, now + 0.3);
      tone.connect(gain);
      gain.connect(context.destination);
      tone.onended = () => {
        tone.disconnect();
        gain.disconnect();
      };
      tone.start(now);
      tone.stop(now + 0.32);
      this.set({ speakerStatus: `Test tone sent to ${this.view.speakers.find((s) => s.id === this.view.speakerId)?.label || "System default"}.` });
    } catch {
      this.set({ speakerStatus: "Could not play the test tone. Check your speaker connection." });
    }
  }

  // ---- audio --------------------------------------------------------------------------

  private async prepareOutput() {
    this.context ??= new AudioContext() as SinkContext;
    const context = this.context;
    if (typeof context.setSinkId === "function" && context.sinkId !== this.view.speakerId) await context.setSinkId(this.view.speakerId);
    await context.resume();
  }

  private async audioOutput() {
    await this.prepareOutput();
    if (this.processor) return;
    const context = this.context!;
    await context.audioWorklet.addModule("/tibi-voice-worklet.js");
    const processor = new AudioWorkletNode(context, "voice-pcm", { numberOfInputs: 1, numberOfOutputs: 1, outputChannelCount: [1] });
    // Tibi's voice passes through a meter on its way to the speaker; an analyser adds no delay.
    const meter = context.createAnalyser();
    meter.fftSize = 1024;
    meter.smoothingTimeConstant = 0.6;
    processor.connect(meter);
    meter.connect(context.destination);
    this.tibiMeter = meter;
    processor.port.postMessage({ type: "configure", prebufferMs: 120 });
    processor.port.onmessage = ({ data }) => this.fromWorklet(data);
    this.processor = processor;
  }

  private fromWorklet(d: Message) {
    if (d.type === "frame" && this.enabled) {
      const socket = this.socket;
      if (!socket || socket.readyState !== WebSocket.OPEN || socket.bufferedAmount > 256000) {
        this.send({ type: "pause" });
        record("tibi", "audio connection fell behind");
        this.pauseLocal("The audio connection fell behind. Resume when ready.");
        return;
      }
      const bytes = new Uint8Array(d.pcm);
      const samples = new Int16Array(d.pcm);
      let binary = "";
      let energy = 0;
      for (const byte of bytes) binary += String.fromCharCode(byte);
      for (const value of samples) energy += value * value;
      if (++this.frames % 3 === 0) this.set({ level: Math.min(100, Math.sqrt(energy / samples.length) / 327.68) });
      this.send({ type: "frame", sequence: this.sequence++, pcm: btoa(binary) });
    }
    if (d.type === "chunk_started" && d.generation === this.generation && !d.cue && this.trace) {
      this.trace.mark("playback_start");
      this.trace.finish("complete");
      this.trace = null;
    }
    if (d.type === "playing" && d.generation === this.generation) {
      this.set({
        state: this.enabled ? "Speaking · you can interrupt" : "Speaking",
        notice: this.enabled ? "You can interrupt at any time." : this.view.typed ? "Type another message to interrupt." : "",
      });
    }
    if (d.type === "drained" && d.generation === this.generation) {
      this.audioDrained = true;
      this.finishPlayback();
    }
    if (d.type === "consumed") this.send({ type: "audio_ack", generation_id: d.generation, index: d.index });
    if (d.type === "overflow") {
      this.send({ type: "pause" });
      this.pauseLocal("Playback fell behind. Resume when ready.");
    }
  }

  private finishPlayback() {
    if (!this.speechDone || !this.audioDrained) return;
    this.set({
      state: this.enabled ? "Listening" : this.view.typed ? "Ready for your message" : "Microphone off",
      notice: this.enabled ? "Listening. Take your time." : this.view.typed ? "Type a message whenever you are ready." : "",
    });
  }

  private async microphone(): Promise<boolean> {
    if (!window.AudioWorkletNode) throw new Error("Voice is unavailable in this browser.");
    const epoch = this.epoch;
    let capture: MediaStream | null = null;
    if (!this.view.typed) {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error("This browser cannot use a microphone here.");
      const id = this.view.microphoneId;
      capture = await navigator.mediaDevices.getUserMedia({
        audio: {
          deviceId: id ? { exact: id } : undefined,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: false,
        },
      });
    }
    if (epoch !== this.epoch) {
      capture?.getTracks().forEach((track) => track.stop());
      return false;
    }
    this.stream = capture;
    const track = capture?.getAudioTracks()[0];
    this.set({ microphone: this.view.typed ? "Typed conversation · microphone off" : `Microphone: ${track?.label || "browser default"}` });
    await this.audioOutput();
    await this.refreshDevices().catch(() => undefined);
    if (capture) {
      this.input = this.context!.createMediaStreamSource(capture);
      this.input.connect(this.processor!);
      this.micMeter ??= this.context!.createAnalyser();
      this.micMeter.fftSize = 1024;
      this.input.connect(this.micMeter);
      for (const t of capture.getTracks()) {
        t.onended = () => {
          if (!this.enabled) return;
          this.send({ type: "pause" });
          record("tibi", "microphone disconnected");
          this.pauseLocal("The microphone disconnected. Check your headset, then resume.");
        };
      }
    }
    this.captureReady = true;
    return true;
  }

  private startCapture() {
    this.acceptAudio = true;
    if (this.view.typed) {
      this.enabled = false;
      this.set({ phase: "live", state: "Ready for your message" });
      return;
    }
    this.sequence = 0;
    this.streamStart = performance.now();
    this.enabled = true;
    this.processor?.port.postMessage({ type: "capture", enabled: true });
    this.set({ phase: "live", state: "Listening" });
  }

  private stopCapture() {
    this.enabled = false;
    this.captureReady = false;
    this.processor?.port.postMessage({ type: "capture", enabled: false });
    this.input?.disconnect();
    this.input = null;
    this.stream?.getTracks().forEach((track) => track.stop());
    this.stream = null;
    this.set({ level: 0 });
  }

  private resetAudio(generation = this.generation) {
    this.generation = generation;
    this.processor?.port.postMessage({ type: "reset", generation });
    this.speechDone = false;
    this.audioDrained = true;
  }

  private pauseLocal(message: string) {
    this.acceptAudio = false;
    this.stopCapture();
    this.resetAudio();
    this.trace?.finish("interrupted");
    this.trace = null;
    this.set({ phase: this.socket ? "paused" : "closed", state: "Paused", thinking: false, notice: message });
  }

  /** How loud Tibi and the microphone are now (0 to 1), and how bright Tibi's voice is: read each animation frame. */
  levels(): { tibi: number; mic: number; brightness: number } {
    const rms = (meter: AnalyserNode | null) => {
      if (!meter) return 0;
      const data = this.meterData.length === meter.fftSize ? this.meterData : (this.meterData = new Float32Array(meter.fftSize));
      meter.getFloatTimeDomainData(data);
      let sum = 0;
      for (const v of data) sum += v * v;
      return Math.min(1, Math.sqrt(sum / data.length) * 4);
    };
    const tibi = rms(this.tibiMeter);
    let brightness = 0;
    if (this.tibiMeter && tibi > 0.01) {
      this.tibiMeter.getByteFrequencyData(this.spectrum);
      let low = 0;
      let high = 0;
      for (let i = 2; i < 24; i++) low += this.spectrum[i];
      for (let i = 60; i < 180; i++) high += this.spectrum[i];
      brightness = Math.min(1, high / 120 / Math.max(1, low / 22));
    }
    return { tibi, mic: this.enabled ? rms(this.micMeter) : 0, brightness };
  }

  private clearSlowStart() {
    if (this.slowStart !== null) window.clearTimeout(this.slowStart);
    this.slowStart = null;
  }

  private send(data: Message) {
    if (this.socket?.readyState === WebSocket.OPEN) this.socket.send(JSON.stringify(data));
  }

  private diagnostic = (sessionId: string, data: unknown) => {
    void tibiServicePost(`/api/interviews/${sessionId}/timings`, data).catch(() => undefined);
  };

  private newTrace(source: string): TurnTiming {
    return new TurnTiming(this.session!.id, this.session!.revision, source, this.diagnostic);
  }

  // ---- the conversation protocol ---------------------------------------------------------

  private receive(m: Message) {
    if (m.session_id && this.session && m.session_id !== this.session.id) return;
    if (m.revision && this.session) this.session.revision = m.revision;
    const type = m.type;
    if (type === "listener_action" || type === "listener_handoff") {
      this.trace?.finish("text_only");
      this.trace = null;
      this.set({
        thinking: false,
        feedback: type === "listener_handoff" ? m.message ?? "" : "",
        notice: m.message ?? (m.spoken ? this.view.notice : "Listening. Take your time."),
      });
      return;
    }
    if (type === "knowledge_check") return this.set({ check: checkText(m.check) });
    if (type === "rehearsal") {
      return this.set({
        rehearsal: { state: m.state, message: m.message ?? "", listenForName: !!m.listen_for_name, keepTranscript: !!m.keep_transcript },
        muted: m.state === "muted",
      });
    }
    if (type === "meeting_line") {
      return this.set({
        meeting: [...this.view.meeting, { text: m.text ?? "", after: this.view.transcript.length, kept: !!m.kept }].slice(-200),
        partial: "",
        thinking: false,
      });
    }
    if (type === "reply_preparing") {
      this.trace?.mark("question_ready");
      this.trace?.mark("tts_requested");
      return;
    }
    if (type === "social_reply") {
      this.trace?.mark("question_ready");
      this.set({
        boundary: "",
        details: { route: m.route, grounding: m.grounding, evidence: m.evidence ?? [], governance: m.governance ?? null },
        check: m.background_check ? "A separate evidence check will follow this answer." : "",
      });
      return;
    }
    if (type === "social_boundary") return this.set({ boundary: m.message ?? "" });
    if (type === "endpoint_wait") return this.set({ feedback: m.message ?? "" });
    if (type === "listener_resumed") {
      this.resetAudio();
      this.cuePlaying = false;
      return;
    }
    if (type === "speech_start") {
      this.trace?.finish("interrupted");
      this.resetAudio(m.generation_id);
      this.set({ feedback: "", thinking: false, state: "Listening" });
      this.timingGeneration = this.generation;
      this.trace = this.newTrace("microphone");
      this.trace.data.generation_id = this.generation;
      this.trace.origin = Math.min(performance.now(), this.streamStart + m.sample / 16);
      this.trace.data.marks.capture_start = 0;
      this.trace.flush();
      return;
    }
    if (type === "snapshot") {
      this.session = m.session;
      const s = m.session as Session;
      return this.set({ transcript: s.social_transcript ?? s.social_dialogue ?? [] });
    }
    if (type === "ready") {
      this.clearSlowStart();
      record("tibi", "conversation ready", { seconds: Math.round((performance.now() - this.startedAt) / 100) / 10, session: this.session?.id });
      if (this.captureReady) {
        this.startCapture();
        this.set({ notice: this.view.typed ? "Type a message when you are ready." : "Listening. You can interrupt Tibi at any time." });
      } else {
        this.send({ type: "pause" });
        this.pauseLocal("Press Resume when you are ready.");
      }
      return;
    }
    if (type === "paused") {
      record("tibi", "paused by Tibi", { message: m.message });
      return this.pauseLocal(m.message);
    }
    if (type === "quality_notice") {
      record("tibi", "quality notice", { message: m.message });
      return this.set({ quality: m.message ?? "" });
    }
    if (type === "error") {
      record("tibi", "Tibi reported an error", { message: m.message });
      return this.set({ notice: m.message ?? "", thinking: false });
    }
    if (type === "state") {
      if (m.state === "thinking") this.trace?.mark("plan_requested");
      this.set({
        state: m.state === "thinking" ? "Thinking" : m.state === "transcribing" ? "Checking wording" : "Preparing",
        thinking: m.state === "thinking",
        notice: m.message ?? "",
      });
      return;
    }
    if (this.generation && Number(m.generation_id) < Number(this.generation)) return;
    if (type === "endpoint" && this.trace) {
      this.trace.data.endpoint_kind = m.endpoint_kind;
      this.trace.data.marks.speech_end = Math.max(0, this.streamStart + m.speech_end_sample / 16 - this.trace.origin);
      this.trace.mark("endpoint");
      this.trace.mark("encoded");
      this.trace.mark("asr_requested");
      this.set({ thinking: true, state: "Considering what you said" });
      return;
    }
    if (type === "partial" || type === "final_transcript" || type === "wording_check") {
      if (type === "final_transcript") this.trace?.mark("final_transcript");
      return this.set({ partial: m.text ?? "" });
    }
    if (type === "clarification") return this.set({ notice: m.text ?? "" });
    if (type === "audio_end") {
      this.processor?.port.postMessage({ type: "end", generation: m.generation_id });
      return;
    }
    if (type === "speech_append") {
      if (this.acceptAudio && m.generation_id === this.generation) this.set({ reply: `${this.view.reply} ${m.text}` });
      return;
    }
    if (type === "speech") {
      if (!this.acceptAudio) return;
      this.cuePlaying = !!m.cue;
      if (m.generation_id !== this.generation) this.resetAudio(m.generation_id);
      this.speechDone = false;
      this.processor?.port.postMessage({ type: "begin", generation: this.generation });
      if (this.cuePlaying) return this.set({ notice: m.text ?? "" });
      this.set({ reply: m.text ?? "", thinking: false });
      if (!this.trace && this.timingGeneration !== this.generation) {
        this.timingGeneration = this.generation;
        this.trace = this.newTrace("replay");
      }
      this.trace?.mark("tts_requested");
      return;
    }
    if (type === "audio_chunk") {
      if (!this.acceptAudio || m.generation_id !== this.generation) return;
      this.audioDrained = false;
      const bytes = Uint8Array.from(atob(m.pcm), (c) => c.charCodeAt(0));
      if (!this.cuePlaying) {
        this.trace?.mark("audio_ready");
        this.trace?.mark("first_audio");
      }
      this.processor?.port.postMessage(
        { type: "audio", generation: this.generation, index: m.index, pcm: bytes.buffer, rate: m.rate, cue: !!m.cue },
        [bytes.buffer],
      );
      return;
    }
    if (type === "speech_done") {
      this.speechDone = true;
      this.finishPlayback();
    }
  }

  // ---- controls -------------------------------------------------------------------------

  async start(options: StartOptions) {
    if (this.view.phase === "starting") return;
    this.epoch++;
    this.shutdown("abandoned");
    this.set({
      ...INITIAL,
      microphones: this.view.microphones,
      speakers: this.view.speakers,
      microphoneId: this.view.microphoneId,
      speakerId: this.view.speakerId,
      speakerStatus: this.view.speakerStatus,
      namesHidden: this.view.namesHidden,
      phase: "starting",
      state: "Starting",
      typed: options.typed,
      mode: options.mode,
      notice: "Starting Tibi…",
    });
    this.startedAt = performance.now();
    record("tibi", "start pressed", { mode: options.mode, voice: options.voice, typed: options.typed });
    this.clearSlowStart();
    this.slowStart = window.setTimeout(() => {
      if (this.view.phase !== "starting") return;
      record("tibi", "slow start", { seconds: 60 });
      this.set({
        notice:
          "Tibi is taking longer than usual to start. The local model server may be busy, for example with the governance review. " +
          "Keep waiting, or use Restart services under Status.",
      });
    }, 60_000);
    try {
      if (!(await this.microphone())) return;
      record("tibi", this.view.typed ? "typed conversation: no microphone" : "microphone ready", { microphone: this.view.microphone });
      const settings =
        options.mode === "interview"
          ? { product_interview: { contributor: options.contributor, topic: options.topic } }
          : options.mode === "governance"
            ? { governance_interview: { contributor: options.contributor } }
            : options.mode === "rehearsal"
              ? {
                  sales_rehearsal: {
                    customer: (options.customer ?? "").slice(0, 200),
                    listen_for_name: Boolean(options.listenForName),
                    keep_transcript: Boolean(options.keepTranscript),
                  },
                }
              : {};
      this.session = await tibiServicePost<Session>("/api/interviews", {
        request_id: crypto.randomUUID(),
        accept_local_storage: true,
        scope: { region: "unknown", variant: "unknown", date: "" },
        ...settings,
      });
      record("tibi", "conversation created", { session: this.session.id });
      await this.connect(options.voice);
    } catch (error) {
      this.clearSlowStart();
      this.stopCapture();
      const name = error instanceof Error ? error.name : "";
      record("tibi", "could not start", { error: name, message: error instanceof Error ? error.message : String(error) });
      this.set({
        phase: "idle",
        state: "Ready",
        notice:
          name === "NotAllowedError"
            ? "The browser did not allow the microphone. Allow it for this page, or choose typed input."
            : error instanceof Error
              ? error.message
              : "Tibi could not start.",
      });
    }
  }

  private async connect(voice: string) {
    const token = await getTibiServiceToken(true);
    const session = this.session!;
    const scheme = location.protocol === "https:" ? "wss" : "ws";
    const socket = new WebSocket(`${scheme}://${location.host}/services/tibi/api/conversation/${session.id}`);
    this.socket = socket;
    let failure: string | null = null;
    socket.onopen = () => {
      record("tibi", "socket open", { session: session.id });
      socket.send(
        JSON.stringify({
          opsatlas_token: signInToken(),
          token,
          listener_practice: false,
          social_voice: voice,
          text_only: this.view.typed,
        }),
      );
    };
    socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data) as Message;
        if (message.type === "error") failure = message.message;
        this.receive(message);
      } catch {
        this.send({ type: "pause" });
        this.pauseLocal("The conversation could not continue safely. Start a new one.");
      }
    };
    socket.onclose = (event) => {
      record("tibi", "socket closed", { session: session.id, code: event.code, reason: event.reason || null, clean: event.wasClean });
      this.clearSlowStart();
      if (this.socket !== socket) return;
      this.socket = null;
      // Tibi's own reason first ("Another conversation with Tibi is still open…"), then a general one.
      this.pauseLocal(
        failure ??
          (event.reason ||
            (event.code === 1008
              ? "Tibi refused the connection. If another conversation is open, end it; otherwise sign in again."
              : event.code === 1011
                ? "Tibi is not running. Use Restart services under Status, then start again."
                : "The conversation ended. Start a new one whenever you like.")),
      );
    };
    socket.onerror = () => {
      record("tibi", "socket error", { session: session.id });
      this.set({ notice: "Could not reach Tibi. Check the Tibi service is running." });
    };
  }

  pause() {
    record("tibi", "pause pressed");
    this.epoch++;
    this.send({ type: "pause" });
    this.pauseLocal("Paused. Your microphone and playback are stopped.");
  }

  async resume() {
    record("tibi", "resume pressed");
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      this.set({ notice: "This conversation has ended. Start a new one." });
      return;
    }
    this.epoch++;
    try {
      if (!(await this.microphone())) return;
      this.acceptAudio = true;
      this.send({ type: "resume" });
    } catch (error) {
      this.set({ notice: error instanceof Error ? error.message : "Could not resume." });
    }
  }

  finishAnswer() {
    this.send({ type: "finish_answer" });
  }

  // ---- sales rehearsal ------------------------------------------------------------------------

  /** Ask Tibi: the next thing said is a request (it interrupts Tibi if it is speaking). */
  askTibi() {
    if (this.view.mode !== "rehearsal" || this.view.phase !== "live") return;
    record("tibi", "ask Tibi pressed");
    this.resetAudio();
    this.acceptAudio = true;
    this.send({ type: "activate" });
  }

  cancelRequest() {
    this.send({ type: "cancel_request" });
  }

  /** Mute stops listening at once: no microphone audio leaves the page until unmuted. */
  setMuted(muted: boolean) {
    if (this.view.mode !== "rehearsal" || this.view.phase !== "live" || this.view.typed) return;
    record("tibi", muted ? "muted" : "unmuted");
    this.enabled = !muted;
    this.processor?.port.postMessage({ type: "capture", enabled: !muted });
    this.send({ type: muted ? "mute" : "unmute" });
    this.set({ muted, level: 0 });
  }

  setRehearsalOptions(options: { listenForName?: boolean; keepTranscript?: boolean }) {
    record("tibi", "rehearsal settings", options);
    this.send({
      type: "rehearsal_settings",
      ...(options.listenForName !== undefined ? { listen_for_name: options.listenForName } : {}),
      ...(options.keepTranscript !== undefined ? { keep_transcript: options.keepTranscript } : {}),
    });
  }

  /** Typed rehearsal: a line of the meeting, or a request to Tibi. */
  sendRehearsalLine(text: string, toTibi: boolean) {
    const value = text.trim();
    if (!value) return;
    this.resetAudio();
    this.acceptAudio = true;
    this.send({ type: "rehearsal_line", text: value, to_tibi: toTibi });
    if (toTibi) this.set({ partial: value });
  }

  sendText(text: string) {
    const value = text.trim();
    if (!value) return;
    this.resetAudio();
    this.acceptAudio = true;
    this.send({ type: "social_text", text: value });
    this.set({ partial: value });
  }

  end() {
    record("tibi", "end pressed", { session: this.session?.id });
    this.clearSlowStart();
    this.epoch++;
    this.send({ type: "pause" });
    this.shutdown("ended");
    this.set({ phase: "closed", state: "Ended", thinking: false, notice: "Conversation ended. Start another whenever you like." });
  }

  private shutdown(status: string) {
    this.stopCapture();
    this.resetAudio();
    this.trace?.finish(status);
    this.trace = null;
    const socket = this.socket;
    this.socket = null;
    socket?.close();
  }
}

let client: TibiVoice | null = null;

/** The page's one Tibi voice client. */
export function tibiVoice(): TibiVoice {
  client ??= new TibiVoice();
  return client;
}
