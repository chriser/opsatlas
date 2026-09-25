// Talk with Tibi, natively in the control panel: the browser side of Tibi's voice loop.
//
// Captures the microphone at 16 kHz through an AudioWorklet, streams it to the Tibi service over its live
// socket (through the OpsAtlas gateway), and plays Tibi's streamed speech with barge-in: speaking over Tibi
// starts a new turn and discards the old audio. The same protocol as the Tibi service's reference client
// (services/sme_interviewer/web/conversation.js), for chat, product interviews and governance interviews.
//
// One client for the page's lifetime, outside React: a conversation keeps going while you look at another
// page (for example the Governance page during a governance interview).

import { getTibiServiceToken, signInToken, tibiServicePost } from "../api";
import { TurnTiming } from "./timing";

export type TibiMode = "recall" | "interview" | "governance";

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
}

export interface StartOptions {
  mode: TibiMode;
  contributor: string;
  topic: string;
  voice: string;
  typed: boolean;
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
    processor.connect(context.destination);
    processor.port.postMessage({ type: "configure", prebufferMs: 120 });
    processor.port.onmessage = ({ data }) => this.fromWorklet(data);
    this.processor = processor;
  }

  private fromWorklet(d: Message) {
    if (d.type === "frame" && this.enabled) {
      const socket = this.socket;
      if (!socket || socket.readyState !== WebSocket.OPEN || socket.bufferedAmount > 256000) {
        this.send({ type: "pause" });
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
      for (const t of capture.getTracks()) {
        t.onended = () => {
          if (!this.enabled) return;
          this.send({ type: "pause" });
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
      if (this.captureReady) {
        this.startCapture();
        this.set({ notice: this.view.typed ? "Type a message when you are ready." : "Listening. You can interrupt Tibi at any time." });
      } else {
        this.send({ type: "pause" });
        this.pauseLocal("Press Resume when you are ready.");
      }
      return;
    }
    if (type === "paused") return this.pauseLocal(m.message);
    if (type === "quality_notice") return this.set({ quality: m.message ?? "" });
    if (type === "error") return this.set({ notice: m.message ?? "", thinking: false });
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
    try {
      if (!(await this.microphone())) return;
      const settings =
        options.mode === "interview"
          ? { product_interview: { contributor: options.contributor, topic: options.topic } }
          : options.mode === "governance"
            ? { governance_interview: { contributor: options.contributor } }
            : {};
      this.session = await tibiServicePost<Session>("/api/interviews", {
        request_id: crypto.randomUUID(),
        accept_local_storage: true,
        scope: { region: "unknown", variant: "unknown", date: "" },
        ...settings,
      });
      await this.connect(options.voice);
    } catch (error) {
      this.stopCapture();
      this.set({ phase: "idle", state: "Ready", notice: error instanceof Error ? error.message : "Tibi could not start." });
    }
  }

  private async connect(voice: string) {
    const token = await getTibiServiceToken(true);
    const session = this.session!;
    const scheme = location.protocol === "https:" ? "wss" : "ws";
    const socket = new WebSocket(`${scheme}://${location.host}/services/tibi/api/conversation/${session.id}`);
    this.socket = socket;
    let failure: string | null = null;
    socket.onopen = () =>
      socket.send(
        JSON.stringify({
          opsatlas_token: signInToken(),
          token,
          listener_practice: false,
          social_voice: voice,
          text_only: this.view.typed,
        }),
      );
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
      if (this.socket !== socket) return;
      this.socket = null;
      this.pauseLocal(
        failure ??
          (event.code === 1008
            ? "Tibi refused the connection. Sign in again, then start a new conversation."
            : "The conversation ended. Start a new one whenever you like."),
      );
    };
    socket.onerror = () => this.set({ notice: "Could not reach Tibi. Check the Tibi service is running." });
  }

  pause() {
    this.epoch++;
    this.send({ type: "pause" });
    this.pauseLocal("Paused. Your microphone and playback are stopped.");
  }

  async resume() {
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

  sendText(text: string) {
    const value = text.trim();
    if (!value) return;
    this.resetAudio();
    this.acceptAudio = true;
    this.send({ type: "social_text", text: value });
    this.set({ partial: value });
  }

  end() {
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
