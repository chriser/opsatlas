// Processes: the registry, maps, diagrams and BeePee's process interviews.
// One module of the control panel's API client; pages import it through ./index.ts, as "./api".

import { apiRequest, authHeaders, guard } from "./http";
import type { Citation } from "./answers";
import { tibiServiceDelete, tibiServiceGet } from "./tibi";

export interface ProcessRule {
  record_id: string;
  topic: string;
  role: string;
  rule: string;
  confidence: string;
}

export interface ProcessRecord {
  id: string;
  source_id: string;
  source_title: string;
  name: string;
  domain: string;
  process: string;
  capabilities: string[];
  roles: string[];
  systems: string[];
  controls: string[];
  dependencies: string[];
  business_rules: string[];
  rules: ProcessRule[];
}

export interface ProcessMapDraft {
  process_id: string;
  name: string;
  source_title: string;
  domain: string;
  process: string;
  roles: string[];
  systems: string[];
  controls: string[];
  dependencies: string[];
  open_decisions: string[];
  steps: { id: string; label: string; owner: string; topic: string; confidence: string }[];
  edges: { source: string; target: string; label: string }[];
  mermaid: string;
}

export interface ProcessDiagramContext {
  status: "available" | "empty" | "unavailable" | string;
  message: string;
  process_id: string;
  process_name: string;
  source_title: string;
  service_url: string;
  chart?: ProcessDiagramChart | null;
  svg: string;
}

export interface ProcessDiagramServiceStatus {
  service_url: string;
  running: boolean;
  started: boolean;
  startable: boolean;
  pid?: number | null;
  message: string;
  health: Record<string, unknown>;
  start_command: string[];
  log_path: string;
}

export interface ProcessDiagramPoint {
  x: number;
  y: number;
}

export interface ProcessDiagramNode {
  id: string;
  type: "lane" | "who" | "start" | "end" | "task" | "gateway" | "control" | "system" | "risk" | "annotation" | string;
  label: string;
  lane: string;
  x: number;
  y: number;
  width: number;
  height: number;
  metadata: Record<string, string>;
}

export interface ProcessDiagramEdge {
  id: string;
  from: string;
  to: string;
  label: string;
  type: "sequence" | "message" | "association" | "control" | string;
  points: ProcessDiagramPoint[];
}

export interface ProcessDiagramAnimationStep {
  step: number;
  action: "draw_node" | "draw_edge" | "draw_lane" | "highlight_node" | string;
  target_id: string;
  label: string;
  narration: string;
}

export interface ProcessDiagramChart {
  schema_version: string;
  chart_id: string;
  title: string;
  style: string;
  format: string;
  nodes: ProcessDiagramNode[];
  edges: ProcessDiagramEdge[];
  animation_steps: ProcessDiagramAnimationStep[];
  narration_script: string[];
  warnings: string[];
}

export async function getProcessRegistry(): Promise<ProcessRecord[]> {
  const res = await guard(await fetch("/api/process/registry", { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load process registry");
  return res.json();
}

export async function getProcessMap(processId: string): Promise<ProcessMapDraft> {
  const res = await guard(await fetch(`/api/process/maps/${processId}`, { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load process map");
  return res.json();
}

export async function getProcessDiagram(processId: string): Promise<ProcessDiagramContext> {
  const res = await guard(await fetch(`/api/process/diagrams/${processId}`, { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load process diagram");
  return res.json();
}

export async function resolveProcessDiagram(question: string, citations: Citation[]): Promise<ProcessDiagramContext> {
  const res = await guard(
    await fetch("/api/process/diagrams/resolve", {
      method: "POST",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({ question, citations }),
    }),
  );
  if (!res.ok) throw new Error("could not resolve process diagram");
  return res.json();
}

export async function getProcessDiagramServiceStatus(): Promise<ProcessDiagramServiceStatus> {
  const res = await guard(await fetch("/api/process/diagrams/service/status", { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load diagram service status");
  return res.json();
}

export async function startProcessDiagramService(): Promise<ProcessDiagramServiceStatus> {
  const res = await guard(await fetch("/api/process/diagrams/service/start", { method: "POST", headers: authHeaders() }));
  if (!res.ok) throw new Error("could not start diagram service");
  return res.json();
}

// ---- Process interviews (TIBI E5): the working process model, the live map, continuing and saving --------------------

export interface ProcessQuote {
  text: string;
  turn: number;
}
export interface ProcessStep {
  id: string;
  /** open: a path named but not described yet (``join``: where the paths meet, before what follows is described);
   *  event: a trigger, something that happens and sets off what follows (PI F23) */
  kind: "task" | "event" | "decision" | "end" | "open";
  join?: boolean;
  label: string;
  who: string;
  /** anyone else taking part, such as the customer the cashier serves */
  with?: string;
  system: string;
  /** a decision: xor (only one path), or (any number, shown as ANY), and (all); "" not asked yet */
  gateway?: "" | "xor" | "or" | "and";
  next: { to: string; label: string }[];
  status: "heard" | "confirmed" | "disputed";
  quotes: ProcessQuote[];
  unknown?: string[];
}
export interface ProcessNote {
  id: string;
  text: string;
  at: string;
  handling?: string;
  status: string;
  quotes: ProcessQuote[];
}
export interface InterviewedProcess {
  id: string;
  name: string;
  status: "planned" | "active" | "done";
  quote: string;
  details: Record<string, { value: string; quote: string; turn: number; status: string }>;
  start: string | null;
  steps: ProcessStep[];
  exceptions: ProcessNote[];
  controls: ProcessNote[];
}
export interface ProcessOpenItem {
  id: string;
  kind: "conflict" | "unclear";
  status: "open" | "raised" | "resolved";
  item: string;
  field: string;
  earlier?: string;
  earlier_quote?: string;
  now?: string;
  text?: string;
  quote?: string;
  turn: number;
  resolution?: string;
}
/** What the participant has said so far, as Tibi's note-taker has captured it (opsatlas.process-model.v1). */
export interface ProcessModel {
  schema: string;
  space: { id: string; name: string };
  participant: Record<string, { value: string; quote: string; turn: number }>;
  processes: InterviewedProcess[];
  open: ProcessOpenItem[];
  focus: string | null;
  turns: number;
}
export interface ProcessInterviewSummary {
  id: string;
  status: string;
  updated_at: string;
  created_at: string;
  space_name: string;
  participant: string;
  role: string;
  processes: { id: string; name: string; steps: number }[];
  open: number;
  pending: number;
  turns: number;
}
export interface ProcessInterviewSession {
  id: string;
  status: string;
  revision: number;
  evidence: { process_interview?: { space: string; space_name: string } };
  process_model?: ProcessModel;
  process_pending?: { turn: number; answer: string; question: string }[];
  social_transcript?: { role: string; content: string }[];
}
export const listProcessInterviews = (space: string) =>
  tibiServiceGet<{ interviews: ProcessInterviewSummary[] }>(`/api/process-interviews?space=${encodeURIComponent(space)}`);
/** Delete an interview for good: its notes, map, timings and conversation-log turns (PI F15). Saved processes stay. */
export const deleteProcessInterview = (id: string) =>
  tibiServiceDelete<{ deleted: string }>(`/api/process-interviews/${encodeURIComponent(id)}`);
export const getProcessInterview = (id: string) => tibiServiceGet<ProcessInterviewSession>(`/api/interviews/${encodeURIComponent(id)}`);
/** The live map of an interview's process, drawn by the process diagram service in the interview's space. */
export const renderInterviewMap = (space: string, model: ProcessModel, process?: string | null) =>
  apiRequest<{ status: "available" | "unavailable"; process_name: string; chart?: ProcessDiagramChart; message?: string }>(
    "POST",
    "/api/process/interview-map",
    { process_model: model, process: process ?? null },
    space,
  );
/** Save one interviewed process to its organisation's space: a document waiting for approval in Governance Review. */
export const saveProcessCapture = (space: string, model: ProcessModel, process: string, interview: string, organisation: string) =>
  apiRequest<{ source_id: string; title: string; approval_status: string }>(
    "POST",
    "/api/process/captures",
    { process_model: model, process, interview, organisation },
    space,
  );
