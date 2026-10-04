// The Enterprise Activity Model.
// One module of the control panel's API client; pages import it through ./index.ts, as "./api".

import { authHeaders, guard } from "./http";

export interface EamTaxonomyEntry {
  id: string;
  label: string;
  description: string;
  keywords: string[];
  order: number;
}

export interface EamNode {
  id: string;
  process_id: string;
  name: string;
  domain_id: string;
  domain_label: string;
  lifecycle_id: string;
  lifecycle_label: string;
  domain_confidence: number;
  lifecycle_confidence: number;
  matched_domain_keywords: string[];
  matched_lifecycle_keywords: string[];
  role_count: number;
  system_count: number;
  control_count: number;
  dependency_count: number;
  source_refs: string[];
  evidence_strength: number;
  confidence_band: "green" | "amber" | "red" | string;
}

export interface EamCell {
  domain_id: string;
  lifecycle_id: string;
  node_ids: string[];
  is_gap: boolean;
}

export interface EamEdge {
  id: string;
  edge_type: "system" | "control" | "dependency" | string;
  from_node_id: string;
  to_node_id: string;
  shared_entity_ids: string[];
  shared_entity_labels: string[];
}

export interface EamEntityRollup {
  id: string;
  object_type: string;
  name: string;
  process_count: number;
  linked_process_ids: string[];
  linked_entity_counts: Record<string, number>;
}

export interface EamDomainCoverage {
  domain_id: string;
  label: string;
  status: "covered" | "partial" | "uncovered" | string;
  node_count: number;
  lifecycle_stage_count: number;
  average_evidence_strength: number;
  node_ids: string[];
}

export interface EamCoverage {
  score: number;
  covered_domain_count: number;
  partial_domain_count: number;
  uncovered_domain_count: number;
  domains: EamDomainCoverage[];
}

export interface EamFinding {
  id: string;
  finding_type: "gap" | "overlap" | "clash" | string;
  severity: "high" | "medium" | "low" | string;
  title: string;
  description: string;
  node_ids: string[];
  entity_ids: string[];
  evidence: string[];
  recommended_action: string;
}

export interface EamModel {
  taxonomy_version: string;
  generated_at: string;
  source_count: number;
  process_count: number;
  domains: EamTaxonomyEntry[];
  lifecycle_stages: EamTaxonomyEntry[];
  nodes: EamNode[];
  cells: EamCell[];
  edges: EamEdge[];
  entity_rollups: Record<string, EamEntityRollup[]>;
  coverage: EamCoverage;
  findings: EamFinding[];
  finding_counts: Record<string, number>;
  meta: Record<string, unknown>;
}

export async function getEamModel(): Promise<EamModel> {
  const res = await guard(await fetch("/api/eam/model", { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load Enterprise Activity Model");
  return res.json();
}

export async function getEamSvg(
  view = "activity",
  expandedNodeIds: string[] = [],
  selectedNodeId = "",
  showAllConnections = false,
): Promise<string> {
  const params = new URLSearchParams({ view });
  if (expandedNodeIds.length) params.set("expanded", expandedNodeIds.join(","));
  if (selectedNodeId) params.set("selected", selectedNodeId);
  if (showAllConnections) params.set("connections", "all");
  const res = await guard(await fetch(`/api/eam/svg?${params.toString()}`, { headers: authHeaders() }));
  if (!res.ok) throw new Error("could not load Enterprise Activity Model canvas");
  return res.text();
}
