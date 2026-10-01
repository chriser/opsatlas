// The facts map (ontology): investigations, proposals and the action log.
// One module of the control panel's API client; pages import it through ./index.ts, as "./api".

import { authHeaders, guard } from "./http";

export interface ActionExecution {
  execution_id: string;
  action: string;
  params: Record<string, unknown>;
  actor: { type: "operator" | "agent" | string; id: string; approved_by?: string | null };
  validation_results?: { rule: string; passed: boolean; message: string }[];
  outcome: "ok" | "rejected" | "error" | string;
  duration_ms: number;
  timestamp: string;
  failed_rule?: string | null;
  message: string;
}

export interface AgentStep {
  tool: string;
  args: Record<string, unknown>;
  result_summary: string;
  latency_ms: number;
}

export interface ProposedAction {
  proposal_id: string;
  action: string;
  params: Record<string, unknown>;
  rationale: string;
  status: string;
}

export interface PendingActionProposal extends ProposedAction {
  agent_run_id: string;
  created_at: string;
  execution_id: string;
  approved_at: string;
  declined_at: string;
  declined_reason: string;
}

export interface AgentRunTrace {
  run_id: string;
  question: string;
  steps: AgentStep[];
  final_answer: string;
  proposed_actions: ProposedAction[];
  persisted_proposals?: PendingActionProposal[];
  total_latency_ms: number;
  created_at: string;
  stopped_reason: string;
}

export async function getActionLog(limit = 20): Promise<ActionExecution[]> {
  const res = await guard(await fetch(`/api/ontology/actions/log?limit=${limit}`, { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load action log");
  return (await res.json()).executions;
}

export async function runOntologyInvestigation(question: string): Promise<AgentRunTrace> {
  const res = await guard(
    await fetch("/api/ontology/agent/runs", {
      method: "POST",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    }),
  );
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? "could not run ontology investigation");
  }
  return res.json();
}

export async function approveOntologyProposal(proposalId: string): Promise<{ proposal: PendingActionProposal; execution?: ActionExecution; already_approved: boolean }> {
  const res = await guard(await fetch(`/api/ontology/proposals/${proposalId}/approve`, { method: "POST", headers: authHeaders() }));
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? "could not approve proposal");
  }
  return res.json();
}

export async function declineOntologyProposal(proposalId: string, reason = ""): Promise<{ proposal: PendingActionProposal; already_declined: boolean }> {
  const res = await guard(
    await fetch(`/api/ontology/proposals/${proposalId}/decline`, {
      method: "POST",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({ reason }),
    }),
  );
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? "could not decline proposal");
  }
  return res.json();
}
