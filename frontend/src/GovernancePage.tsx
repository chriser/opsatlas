import { useEffect, useState } from "react";
import {
  acceptIssue,
  cancelComplianceReasoningReview,
  cancelInternalReview,
  getComplianceReasoningFindings,
  getComplianceReasoningReviewStatus,
  getComplianceReasoningStatus,
  getComplianceResolutions,
  getGovernanceReanalysis,
  getInternalReviewLatest,
  getInternalReviewStatus,
  approveSource,
  getIntelligence,
  getRegulatoryCandidates,
  listSources,
  reanalyseGovernance,
  reconcileComplianceFindings,
  rejectSource,
  reviewRegulatoryCandidate,
  runComplianceReasoningReview,
  runInternalReview,
  simulateRegulatoryImpact,
  type ComplianceFinding,
  type ComplianceFindingClassification,
  type ComplianceFindingReconcileReport,
  type ComplianceReasoningStatus,
  type ComplianceResolution,
  type ComplianceResolutionReport,
  type ComplianceReviewResult,
  type GovernanceReanalysisReport,
  type InternalReviewResult,
  type IntelligenceIssue,
  type IntelligenceReport,
  type RegulatoryCandidate,
  type RegulatoryCandidateReport,
  type RegulatoryImpactSimulation,
  type ReviewDepth,
  type SourceRecord,
} from "./api";
import { ComplianceFindingWorkbench } from "./ComplianceFindingWorkbench";
import { Markdown } from "./Markdown";
import { ReviewWorkbench } from "./ReviewWorkbench";

const CATEGORY_LABELS: Record<string, string> = {
  compliance: "Compliance",
  consistency: "Consistency",
  correctness: "Correctness",
};

const CATEGORY_DESCRIPTIONS: Record<string, string> = {
  compliance: "Readiness & hygiene: metadata, acronyms, readability.",
  consistency: "Uniformity: duplicates, locale and house-style.",
  correctness: "Accuracy: contradictions, currency and links.",
};

// What leaving (or accepting) each issue costs the assistant — shown so the decision is informed.
const IMPACT: Record<string, string> = {
  conflict: "May cause wrong or inconsistent answers (correctness risk).",
  duplicate: "Redundant citations and less complete answers — alternative evidence gets crowded out.",
  not_ingested: "Content is unusable — related questions get refused (coverage gap).",
  undefined_acronym: "Queries using the full term may miss this document; answers less clear.",
  readability: "Dense text extracts less cleanly into answers.",
  localisation: "Split retrieval matches and inconsistent wording in answers.",
  content_style: "Inconsistent wording; placeholders may surface in answers.",
  metadata_title: "Unhelpful source name in citations (traceability only — no quality impact).",
  broken_link: "A cited reference can’t be followed (traceability only).",
};

const SEVERITY_COLOR: Record<string, string> = { high: "#dc2626", medium: "#d97706", low: "#64748b" };
const HEALTH: Record<string, { color: string; label: string }> = {
  green: { color: "#16a34a", label: "Healthy" },
  amber: { color: "#d97706", label: "Needs attention" },
  red: { color: "#dc2626", label: "Critical" },
};
const REGULATORY_STATUS_GUIDE: Record<string, string> = {
  unreviewed: "New candidate generated from approved ingested knowledge; no human decision has been recorded yet.",
  relevant: "Keep as an in-scope regulatory signal for follow-up analysis and future content prioritisation.",
  needs_research: "Hold for manual validation against authoritative guidance before treating it as confirmed relevant.",
  irrelevant: "Mark as out of scope for this platform direction; it stays auditable but should not drive follow-up work.",
};
const COMPLIANCE_FINDING_LABELS: Record<ComplianceFindingClassification, string> = {
  supported: "Supported",
  contradiction: "Contradiction",
  missing_obligation: "Missing obligation",
  missing_detail: "Missing detail",
  duplicate: "Duplicate guidance",
  too_vague: "Too vague",
  outdated: "Outdated",
  unsupported_claim: "Unsupported claim",
  not_related: "Not related",
  needs_human_review: "Needs human review",
};
const COMPLIANCE_FINDING_DESCRIPTIONS: Record<ComplianceFindingClassification, string> = {
  supported: "External and internal wording appear to address the same requirement consistently.",
  contradiction: "Internal wording appears to conflict with, weaken or reverse the external requirement.",
  missing_obligation: "External evidence contains an obligation with no clear internal coverage.",
  missing_detail: "Internal wording covers the topic but appears to omit an important external detail.",
  duplicate: "Internal sources appear to repeat the same substantive guidance rather than cross-reference it.",
  too_vague: "Internal wording is less precise or less mandatory than the external evidence.",
  outdated: "Internal wording may no longer match the external evidence version.",
  unsupported_claim: "Internal wording makes a governed claim without aligned external evidence in the review set.",
  not_related: "The checked passages do not appear to govern the same concrete obligation.",
  needs_human_review: "The review found enough signal to triage, but not enough certainty for a stronger classification.",
};
const COMPLIANCE_SEVERITY_COLOR: Record<ComplianceFinding["severity"], string> = {
  high: "#dc2626",
  medium: "#d97706",
  low: "#64748b",
};
const ACTIONABLE_COMPLIANCE_CLASSIFICATIONS = new Set<ComplianceFindingClassification>([
  "contradiction",
  "missing_obligation",
  "missing_detail",
  "duplicate",
  "too_vague",
  "outdated",
  "unsupported_claim",
  "needs_human_review",
]);
const REVIEW_DEPTH_LABELS: Record<ReviewDepth, string> = {
  fast: "Fast triage",
  balanced: "Balanced",
  deep: "Deep audit",
};
const REVIEW_DEPTH_HELP: Record<ReviewDepth, string> = {
  fast: "Deterministic checks only; quickest and lowest hardware load.",
  balanced: "Limited lighter-model reasoning; intended for same-day benchmarking.",
  deep: "Full local reasoning; defaults to the 14B benchmark baseline unless overridden.",
};
const INTERNAL_CLASSIFICATION_CATEGORY: Record<ComplianceFindingClassification, keyof typeof CATEGORY_LABELS> = {
  supported: "correctness",
  contradiction: "correctness",
  missing_obligation: "compliance",
  missing_detail: "compliance",
  duplicate: "consistency",
  too_vague: "compliance",
  outdated: "correctness",
  unsupported_claim: "correctness",
  not_related: "correctness",
  needs_human_review: "correctness",
};

function issueTone(count: number, highestSeverity?: "high" | "medium" | "low") {
  if (count <= 0) return { background: "#dcfce7", borderColor: "#86efac", color: "#166534" };
  if (highestSeverity === "high") return { background: "#fee2e2", borderColor: "#fecaca", color: "#991b1b" };
  if (highestSeverity === "medium") return { background: "#ffedd5", borderColor: "#fed7aa", color: "#9a3412" };
  return { background: "#f1f5f9", borderColor: "#cbd5e1", color: "#334155" };
}

function isActionableComplianceFinding(finding: ComplianceFinding) {
  return ACTIONABLE_COMPLIANCE_CLASSIFICATIONS.has(finding.classification);
}

function groupedFindingRepresentatives(
  findings: ComplianceFinding[],
  currentStatusMap: Record<string, { related_key?: string } | undefined>,
) {
  const seen = new Set<string>();
  return findings.filter((finding) => {
    const key = currentStatusMap[finding.id]?.related_key || finding.id;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function Dot({ color }: { color: string }) {
  return <span style={{ width: 9, height: 9, borderRadius: "50%", background: color, display: "inline-block", flexShrink: 0 }} />;
}

function formatDate(value?: string) {
  if (!value) return "Not run";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function formatPercent(value: number) {
  return `${Math.round(value * 100)}%`;
}

function formatDuration(seconds?: number) {
  if (!seconds || seconds <= 0) return "Estimating";
  const whole = Math.round(seconds);
  const h = Math.floor(whole / 3600);
  const m = Math.floor((whole % 3600) / 60);
  const s = whole % 60;
  if (h) return `${h}h ${m}m`;
  if (m) return `${m}m ${s}s`;
  return `${s}s`;
}

function formatTimingLabel(label?: string, seconds?: number) {
  if (label === "Completed") return "Review complete";
  if (label === "Stopped") return "Review stopped";
  if (label && label !== "Completed" && label !== "Stopped") return label;
  if (seconds && seconds > 0) return formatDuration(seconds);
  return "Timing uncertain";
}

function cacheLabel(value?: string) {
  return {
    hit: "cache reused",
    miss: "reviewed",
    bypassed: "force rerun",
    pending: "pending",
  }[value ?? "pending"] ?? value;
}

function externalReviewOptions(depth: ReviewDepth, forceRerun: boolean, throttleDeep: boolean) {
  const profiles = {
    fast: {
      min_pair_relevance_score: 0.18,
      max_agent_calls_per_pair: 0,
      max_findings: 30,
    },
    balanced: {
      min_pair_relevance_score: 0.14,
      max_agent_calls_per_pair: 2,
      max_findings: 40,
    },
    deep: {
      min_pair_relevance_score: 0.12,
      max_agent_calls_per_pair: 0,
      max_findings: 50,
    },
  }[depth];
  return {
    include_supported_findings: true,
    include_unsupported_internal_claims: false,
    include_missing_obligations: false,
    include_not_related_pairs: false,
    min_pair_relevance_score: profiles.min_pair_relevance_score,
    max_findings: profiles.max_findings,
    force_rerun: forceRerun,
    review_depth: depth,
    throttle_deep: depth === "deep" && throttleDeep,
    max_agent_calls_per_pair: profiles.max_agent_calls_per_pair,
  };
}

type InternalTriageIssue = IntelligenceIssue & { cat: string };

function filenameStamp() {
  return new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
}

function downloadMarkdown(filename: string, markdown: string) {
  const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function mdValue(value: unknown) {
  if (value === undefined || value === null || value === "") return "Not available";
  return String(value);
}

function fencedMarkdown(value?: string) {
  const text = value?.trim() || "No evidence text supplied.";
  return `\n\`\`\`markdown\n${text.replace(/```/g, "'''")}\n\`\`\`\n`;
}

function evidenceMarkdownBlock(label: string, evidence: ComplianceFinding["external_evidence"]) {
  if (!evidence) return `### ${label}\n\nNo evidence attached.\n`;
  return [
    `### ${label}`,
    "",
    `- Source: ${mdValue(evidence.source_title)}`,
    `- Citation: ${mdValue(evidence.citation || evidence.heading)}`,
    evidence.url ? `- URL: ${evidence.url}` : "",
    fencedMarkdown(evidence.text),
  ].filter(Boolean).join("\n");
}

function findingResolutionStatus(
  finding: ComplianceFinding,
  resolutions?: ComplianceResolutionReport | null,
  reconciliation?: ComplianceFindingReconcileReport | null,
) {
  const resolution = resolutions?.by_finding?.[finding.id];
  if (resolution) return `Recorded decision: ${resolution.action}${resolution.note ? ` - ${resolution.note}` : ""}`;
  const current = reconciliation?.by_finding?.[finding.id];
  if (current?.source_status === "already_changed") return `Superseded by source edit: ${current.message}`;
  if (current?.message) return current.message;
  return "Open";
}

function complianceFindingMarkdown(
  finding: ComplianceFinding,
  index: number,
  categoryLabel: string,
  resolutions?: ComplianceResolutionReport | null,
  reconciliation?: ComplianceFindingReconcileReport | null,
) {
  return [
    `## ${index}. ${categoryLabel} - ${COMPLIANCE_FINDING_LABELS[finding.classification]}`,
    "",
    `- Severity: ${finding.severity}`,
    `- Review score: ${formatPercent(finding.confidence)}`,
    `- Alignment: ${formatPercent(finding.alignment_score)}`,
    `- Status: ${findingResolutionStatus(finding, resolutions, reconciliation)}`,
    finding.confidence_interpretation ? `- Confidence interpretation: ${finding.confidence_interpretation}` : "",
    "",
    `Rationale: ${finding.advisor_summary || finding.rationale || "No rationale supplied."}`,
    finding.why_it_matters ? `\nWhy it matters: ${finding.why_it_matters}` : "",
    finding.recommended_action ? `\nRecommended action: ${finding.recommended_action}` : "",
    finding.proposed_internal_text ? `\nSuggested wording:${fencedMarkdown(finding.proposed_internal_text)}` : "",
    evidenceMarkdownBlock("External / Source A Evidence", finding.external_evidence),
    evidenceMarkdownBlock("Internal / Source B Evidence", finding.internal_evidence),
    finding.signals.length ? `Signals: ${finding.signals.join("; ")}` : "",
  ].filter(Boolean).join("\n");
}

function internalTriageIssueMarkdown(issue: InternalTriageIssue, index: number) {
  return [
    `## ${index}. ${CATEGORY_LABELS[issue.cat]} - ${issue.check.replace(/_/g, " ")}`,
    "",
    `- Severity: ${issue.severity}`,
    `- Score: ${Math.round(issue.score * 100)}%`,
    `- Source: ${issue.source_title}`,
    "",
    issue.advisor_summary || issue.detail,
    issue.recommended_action ? `\nRecommended action: ${issue.recommended_action}` : "",
    issue.why_it_matters ? `\nWhy it matters: ${issue.why_it_matters}` : "",
  ].filter(Boolean).join("\n");
}

function externalReviewMarkdown(
  review: ComplianceReviewResult,
  resolutions?: ComplianceResolutionReport | null,
  reconciliation?: ComplianceFindingReconcileReport | null,
) {
  const status = review.status;
  const lines = [
    "# External Source Review Findings",
    "",
    `Exported: ${new Date().toISOString()}`,
    `Job: ${status.job_id}`,
    `Status: ${status.status}`,
    `Depth: ${REVIEW_DEPTH_LABELS[status.review_depth] ?? status.review_depth}`,
    `Deep throttle: ${status.throttle_deep ? "enabled" : "disabled"}`,
    `Engine: ${status.audit.engine}`,
    `Model profile: ${status.audit.model_profile}`,
    `Prompt version: ${status.audit.prompt_version || "Not available"}`,
    `Pairs: ${status.pair_completed} / ${status.pair_total}`,
    `Elapsed: ${formatDuration(status.elapsed_seconds)}`,
    `Findings: ${review.findings.length}`,
    `Cache: ${status.cache_hit_count} reused, ${status.cache_miss_count} reviewed, ${status.cache_bypass_count} forced`,
    "",
    "# Pair Progress",
    "",
    "| Pair | Status | Findings | Cache | Duration |",
    "| --- | --- | ---: | --- | ---: |",
    ...status.pairs.map((pair) => (
      `| ${pair.external_title} vs ${pair.internal_title} | ${pair.status} | ${pair.finding_count} | ${pair.cache_status} | ${formatDuration(pair.duration_seconds)} |`
    )),
    "",
    "# Findings",
    "",
    review.findings.length
      ? review.findings.map((finding, index) => complianceFindingMarkdown(finding, index + 1, COMPLIANCE_FINDING_LABELS[finding.classification], resolutions, reconciliation)).join("\n\n")
      : "No findings returned.",
  ];
  return lines.join("\n");
}

function internalReviewMarkdown(
  report: IntelligenceReport | null,
  triageIssues: InternalTriageIssue[],
  review: InternalReviewResult | null,
  pairwiseFindings: ComplianceFinding[],
  resolutions?: ComplianceResolutionReport | null,
  reconciliation?: ComplianceFindingReconcileReport | null,
) {
  const status = review?.status ?? null;
  const lines = [
    "# Internal Source Review Findings",
    "",
    `Exported: ${new Date().toISOString()}`,
    `Job: ${mdValue(status?.job_id)}`,
    `Status: ${mdValue(status?.status)}`,
    `Depth: ${status?.review_depth ? REVIEW_DEPTH_LABELS[status.review_depth] : "Not available"}`,
    `Deep throttle: ${status?.throttle_deep ? "enabled" : "disabled"}`,
    `Engine: ${mdValue(status?.engine)}`,
    `Model profile: ${mdValue(status?.model_profile)}`,
    `Prompt version: ${mdValue(status?.prompt_version)}`,
    `Pairs: ${mdValue(status ? `${status.item_completed} / ${status.item_total}` : "")}`,
    `Elapsed: ${formatDuration(status?.elapsed_seconds)}`,
    `Fast triage health: ${report ? HEALTH[report.health].label : "Not available"}`,
    `Fast triage issues: ${report?.total_issues ?? 0}`,
    `Pairwise findings: ${pairwiseFindings.length}`,
    "",
    "# Fast Triage Issues",
    "",
    triageIssues.length
      ? triageIssues.map((issue, index) => internalTriageIssueMarkdown(issue, index + 1)).join("\n\n")
      : "No fast triage issues returned.",
    "",
    "# Pairwise / Deep Findings",
    "",
    pairwiseFindings.length
      ? pairwiseFindings.map((finding, index) => {
        const category = INTERNAL_CLASSIFICATION_CATEGORY[finding.classification];
        return complianceFindingMarkdown(finding, index + 1, CATEGORY_LABELS[category], resolutions, reconciliation);
      }).join("\n\n")
      : "No pairwise findings returned.",
  ];
  return lines.join("\n");
}

function evidenceMarkdown(text: string) {
  const lines = text.split(/\r?\n/).map((line) => line.trimEnd()).filter((line) => line.trim());
  const firstTableIndex = lines.findIndex((line) => line.trim().startsWith("|") && line.trim().indexOf("|", 1) !== -1);
  if (firstTableIndex >= 0) {
    const tableRows: string[] = [];
    for (let index = firstTableIndex; index < lines.length; index += 1) {
      const line = lines[index].trim();
      if (!line.startsWith("|") || line.indexOf("|", 1) === -1) break;
      tableRows.push(line);
    }
    if (tableRows.length >= 3 && /^\|?\s*:?-{1,}:?/.test(tableRows[1])) return tableRows.slice(0, 3).join("\n");
    return tableRows[0] ?? text;
  }
  return text;
}

function ComplianceEvidenceText({ text }: { text: string }) {
  return (
    <div className="compliance-evidence-markdown">
      <Markdown text={evidenceMarkdown(text)} />
    </div>
  );
}

function isIntelligenceReport(value: unknown): value is IntelligenceReport {
  return Boolean(
    value
    && typeof value === "object"
    && "issues" in value
    && "categories" in value
    && "total_issues" in value,
  );
}

function wait(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export function GovernancePage() {
  const [report, setReport] = useState<IntelligenceReport | null>(null);
  const [regulatory, setRegulatory] = useState<RegulatoryCandidateReport | null>(null);
  const [reanalysis, setReanalysis] = useState<GovernanceReanalysisReport | null>(null);
  const [complianceStatus, setComplianceStatus] = useState<ComplianceReasoningStatus | null>(null);
  const [complianceReview, setComplianceReview] = useState<ComplianceReviewResult | null>(null);
  const [complianceResolutions, setComplianceResolutions] = useState<ComplianceResolutionReport | null>(null);
  const [complianceReconciliation, setComplianceReconciliation] = useState<ComplianceFindingReconcileReport | null>(null);
  const [complianceFilter, setComplianceFilter] = useState<ComplianceFindingClassification | null>(null);
  const [resolvingFinding, setResolvingFinding] = useState<ComplianceFinding | null>(null);
  const [internalDeepFindings, setInternalDeepFindings] = useState<ComplianceFinding[]>([]);
  const [internalReconciliation, setInternalReconciliation] = useState<ComplianceFindingReconcileReport | null>(null);
  const [resolvingInternalFinding, setResolvingInternalFinding] = useState<ComplianceFinding | null>(null);
  const [complianceBusy, setComplianceBusy] = useState(false);
  const [complianceError, setComplianceError] = useState<string | null>(null);
  const [internalReview, setInternalReview] = useState<InternalReviewResult | null>(null);
  const [internalReviewBusy, setInternalReviewBusy] = useState(false);
  const [internalReviewCancelling, setInternalReviewCancelling] = useState(false);
  const [internalReviewDepth, setInternalReviewDepth] = useState<ReviewDepth>("balanced");
  const [internalThrottleDeep, setInternalThrottleDeep] = useState(false);
  const [internalReviewError, setInternalReviewError] = useState<string | null>(null);
  const [complianceReviewDepth, setComplianceReviewDepth] = useState<ReviewDepth>("balanced");
  const [complianceThrottleDeep, setComplianceThrottleDeep] = useState(false);
  const [complianceCancelling, setComplianceCancelling] = useState(false);
  const [sources, setSources] = useState<SourceRecord[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [reanalysisBusy, setReanalysisBusy] = useState(false);
  const [filter, setFilter] = useState<string | null>(null);
  const [reviewing, setReviewing] = useState<IntelligenceIssue | null>(null);
  const [impact, setImpact] = useState<RegulatoryImpactSimulation | null>(null);

  async function refresh() {
    try {
      const [r, s, regulatoryReport, reanalysisReport, complianceStatusReport, resolutionReport, internalReviewReport] = await Promise.all([
        getIntelligence(),
        listSources(),
        getRegulatoryCandidates(),
        getGovernanceReanalysis(),
        getComplianceReasoningStatus(),
        getComplianceResolutions(),
        getInternalReviewLatest(),
      ]);
      setReport(r);
      setSources(s);
      setRegulatory(regulatoryReport);
      setReanalysis(reanalysisReport);
      setComplianceStatus(complianceStatusReport);
      setComplianceResolutions(resolutionReport);
      setInternalReview(internalReviewReport);
      setInternalDeepFindings(internalReviewReport.findings ?? []);
      if (isIntelligenceReport(internalReviewReport.report)) {
        setReport(internalReviewReport.report);
      }
      setError(null);
    } catch {
      setError("Could not reach the backend.");
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function runReanalysis() {
    setReanalysisBusy(true);
    setBusy(true);
    try {
      setReanalysis(await reanalyseGovernance());
      await refresh();
    } finally {
      setReanalysisBusy(false);
      setBusy(false);
    }
  }

  async function act(fn: (id: string) => Promise<void>, id: string) {
    setBusy(true);
    try {
      await fn(id);
      await refresh();
    } finally {
      setBusy(false);
    }
  }

  async function accept(i: IntelligenceIssue) {
    setBusy(true);
    try {
      await acceptIssue(i.source_id, i.check, i.detail);
      await refresh();
    } finally {
      setBusy(false);
    }
  }

  async function reviewCandidate(candidate: RegulatoryCandidate, status: "relevant" | "irrelevant" | "needs_research") {
    setBusy(true);
    try {
      await reviewRegulatoryCandidate(candidate.id, status);
      await refresh();
    } finally {
      setBusy(false);
    }
  }

  async function simulateImpact(candidate: RegulatoryCandidate) {
    setBusy(true);
    try {
      setImpact(await simulateRegulatoryImpact(candidate.id));
    } finally {
      setBusy(false);
    }
  }

  async function runInternalSourceReview(forceRerun = false) {
    setInternalReviewBusy(true);
    setBusy(true);
    setInternalReviewError(null);
    try {
      const started = await runInternalReview({
        force_rerun: forceRerun,
        review_depth: internalReviewDepth,
        throttle_deep: internalReviewDepth === "deep" && internalThrottleDeep,
      });
      setInternalReview(started);
      setInternalDeepFindings(started.findings ?? []);
      let current = started;
      while (current.status?.status === "queued" || current.status?.status === "running") {
        await wait(1000);
        current = await getInternalReviewStatus(current.status.job_id);
        setInternalReview(current);
        setInternalDeepFindings(current.findings ?? []);
      }
      if (current.status?.status === "completed" && isIntelligenceReport(current.report)) {
        setReport(current.report);
      } else if (current.status?.status === "completed") {
        setInternalDeepFindings(current.findings ?? []);
        await reconcileCurrentInternalFindings(current.findings ?? []);
      } else if (current.status?.status === "failed") {
        setInternalReviewError(current.status.failure_reason || "Internal Source Review failed.");
      } else if (current.status?.status === "cancelled") {
        setInternalReviewError(null);
      }
    } catch (err) {
      setInternalReviewError(err instanceof Error ? err.message : "Could not run Internal Source Review.");
    } finally {
      setInternalReviewBusy(false);
      setBusy(false);
    }
  }

  async function stopInternalSourceReview() {
    const jobId = internalReview?.status?.job_id;
    if (!jobId) return;
    setInternalReviewCancelling(true);
    setInternalReviewError(null);
    try {
      const cancelled = await cancelInternalReview(jobId);
      setInternalReview(cancelled);
      setInternalDeepFindings(cancelled.findings ?? []);
      setInternalReviewBusy(false);
    } catch (err) {
      setInternalReviewError(err instanceof Error ? err.message : "Could not stop Internal Source Review.");
    } finally {
      setInternalReviewCancelling(false);
    }
  }

  async function reconcileCurrentInternalFindings(findings = internalDeepFindings, persistSuperseded = false) {
    if (!findings.length) {
      setInternalReconciliation(null);
      return null;
    }
    const reconciliation = await reconcileComplianceFindings(findings, persistSuperseded);
    setInternalReconciliation(reconciliation);
    if (persistSuperseded && reconciliation.superseded_records.length) {
      setComplianceResolutions(await getComplianceResolutions());
    }
    return reconciliation;
  }

  async function reconcileCurrentComplianceFindings(findings = complianceReview?.findings ?? [], persistSuperseded = false) {
    if (!findings.length) {
      setComplianceReconciliation(null);
      return null;
    }
    const reconciliation = await reconcileComplianceFindings(findings, persistSuperseded);
    setComplianceReconciliation(reconciliation);
    if (persistSuperseded && reconciliation.superseded_records.length) {
      setComplianceResolutions(await getComplianceResolutions());
    }
    return reconciliation;
  }

  function mergeComplianceResolution(record: ComplianceResolution) {
    setComplianceResolutions((current) => {
      const base: ComplianceResolutionReport = current ?? { records: [], by_finding: {}, source_summary: {}, actions: [] };
      const records = [...base.records.filter((item) => item.finding_id !== record.finding_id), record];
      const sourceSummary = { ...base.source_summary };
      if (record.source_id) {
        const row = sourceSummary[record.source_id] ?? {
          resolved: 0,
          fixed: 0,
          accepted_risk: 0,
          dismissed: 0,
          needs_sme_review: 0,
          superseded_by_source_edit: 0,
          latest_resolved_at: "",
        };
        sourceSummary[record.source_id] = {
          ...row,
          resolved: row.resolved + 1,
          fixed: row.fixed + (record.action === "fixed" ? 1 : 0),
          accepted_risk: row.accepted_risk + (record.action === "accepted_risk" ? 1 : 0),
          dismissed: row.dismissed + (record.action === "dismissed" ? 1 : 0),
          needs_sme_review: row.needs_sme_review + (record.action === "needs_sme_review" ? 1 : 0),
          superseded_by_source_edit: row.superseded_by_source_edit + (record.action === "superseded_by_source_edit" ? 1 : 0),
          latest_resolved_at: record.resolved_at,
        };
      }
      return { ...base, records, by_finding: { ...base.by_finding, [record.finding_id]: record }, source_summary: sourceSummary };
    });
  }

  async function recordComplianceResolution(record: ComplianceResolution) {
    mergeComplianceResolution(record);
    try {
      await reconcileCurrentComplianceFindings(complianceReview?.findings ?? [], record.action === "fixed");
    } catch (err) {
      setComplianceError(err instanceof Error ? err.message : "Resolution saved, but finding reconciliation could not refresh.");
    }
  }

  async function recordInternalComplianceResolution(record: ComplianceResolution) {
    mergeComplianceResolution(record);
    try {
      await reconcileCurrentInternalFindings(internalDeepFindings, record.action === "fixed");
    } catch (err) {
      setInternalReviewError(err instanceof Error ? err.message : "Resolution saved, but internal finding reconciliation could not refresh.");
    }
  }

  async function runComplianceReview(forceRerun = false) {
    setComplianceBusy(true);
    setBusy(true);
    setComplianceError(null);
    try {
      const started = await runComplianceReasoningReview(externalReviewOptions(complianceReviewDepth, forceRerun, complianceThrottleDeep));
      setComplianceReview(started);
      setComplianceStatus(await getComplianceReasoningStatus());
      let status = started.status;
      while (status.status === "queued" || status.status === "running") {
        await wait(1000);
        status = await getComplianceReasoningReviewStatus(started.status.job_id);
        setComplianceReview((current) => current ? { ...current, status } : { ...started, status });
      }
      if (status.status === "completed") {
        const findingResponse = await getComplianceReasoningFindings(started.status.job_id);
        setComplianceReview((current) => current ? { ...current, status, findings: findingResponse.findings } : { ...started, status, findings: findingResponse.findings });
        await reconcileCurrentComplianceFindings(findingResponse.findings);
      } else if (status.status === "failed") {
        setComplianceError(status.failure_reason || "Compliance reasoning review failed.");
      } else if (status.status === "cancelled") {
        setComplianceError(null);
      }
    } catch (err) {
      setComplianceError(err instanceof Error ? err.message : "Could not run compliance reasoning review.");
    } finally {
      setComplianceBusy(false);
      setBusy(false);
    }
  }

  async function stopComplianceReview() {
    const jobId = complianceReview?.status.job_id;
    if (!jobId) return;
    setComplianceCancelling(true);
    setComplianceError(null);
    try {
      const status = await cancelComplianceReasoningReview(jobId);
      setComplianceReview((current) => current ? { ...current, status } : null);
      setComplianceBusy(false);
    } catch (err) {
      setComplianceError(err instanceof Error ? err.message : "Could not stop compliance reasoning review.");
    } finally {
      setComplianceCancelling(false);
    }
  }

  function exportInternalReview() {
    const markdown = internalReviewMarkdown(
      report,
      allIssues,
      internalReview,
      internalDeepFindings,
      complianceResolutions,
      internalReconciliation,
    );
    downloadMarkdown(`internal-source-review-${filenameStamp()}.md`, markdown);
  }

  function exportExternalReview() {
    if (!complianceReview) return;
    downloadMarkdown(
      `external-source-review-${filenameStamp()}.md`,
      externalReviewMarkdown(complianceReview, complianceResolutions, complianceReconciliation),
    );
  }

  const allIssues = report ? Object.entries(report.issues).flatMap(([cat, list]) => list.map((i) => ({ cat, ...i }))) : [];
  const visibleIssues = allIssues
    .filter((i) => filter === null || i.cat === filter)
    .sort((a, b) => b.score - a.score);
  const internalExportAvailable = Boolean(report || internalReview?.status || internalDeepFindings.length);
  const externalExportAvailable = Boolean(complianceReview);
  const coverage = reanalysis?.coverage ?? [];
  const coveragePreview = coverage.slice(0, 6);
  const reanalysisStatus = reanalysis?.needs_reanalysis ? "Needs re-analysis" : reanalysis?.has_run ? "Current" : "Not run";
  const reanalysisStatusClass = reanalysis?.has_run && !reanalysis.needs_reanalysis ? "status-pill status-pill--good" : "status-pill status-pill--warn";
  const complianceAvailable = complianceStatus?.enabled && complianceStatus.status === "available";
  const complianceStatusText = complianceStatus
    ? complianceStatus.status.replace("_", " ")
    : "Loading";
  const complianceStatusClass = complianceAvailable ? "status-pill status-pill--good" : "status-pill status-pill--warn";
  const complianceFindings = complianceReview?.findings ?? [];
  const complianceResolutionMap = complianceResolutions?.by_finding ?? {};
  const complianceCurrentStatusMap = complianceReconciliation?.by_finding ?? {};
  const supportedComplianceFindings = complianceFindings.filter((finding) => finding.classification === "supported");
  const isSupersededByEdit = (finding: ComplianceFinding) => (
    complianceResolutionMap[finding.id]?.action === "superseded_by_source_edit"
    || (!complianceResolutionMap[finding.id] && complianceCurrentStatusMap[finding.id]?.source_status === "already_changed")
  );
  const supersededComplianceFindings = complianceFindings.filter(isSupersededByEdit);
  const openComplianceFindings = complianceFindings.filter((finding) => (
    isActionableComplianceFinding(finding)
    && !complianceResolutionMap[finding.id]
    && !isSupersededByEdit(finding)
  ));
  const visibleComplianceFindings = groupedFindingRepresentatives(
    openComplianceFindings.filter((finding) => complianceFilter === null || finding.classification === complianceFilter),
    complianceCurrentStatusMap,
  );
  const resolvedComplianceCount = complianceFindings.filter((finding) => complianceResolutionMap[finding.id]).length;
  const complianceCounts = openComplianceFindings.reduce<Record<string, number>>((acc, finding) => {
    acc[finding.classification] = (acc[finding.classification] ?? 0) + 1;
    return acc;
  }, {});
  const complianceHighestSeverity = openComplianceFindings.some((finding) => finding.severity === "high")
    ? "high"
    : openComplianceFindings.some((finding) => finding.severity === "medium")
      ? "medium"
      : "low";
  const internalStatus = internalReview?.status ?? null;
  const internalCurrentStatusMap = internalReconciliation?.by_finding ?? {};
  const supportedInternalFindings = internalDeepFindings.filter((finding) => finding.classification === "supported");
  const isSupersededInternalFinding = (finding: ComplianceFinding) => (
    complianceResolutionMap[finding.id]?.action === "superseded_by_source_edit"
    || (!complianceResolutionMap[finding.id] && internalCurrentStatusMap[finding.id]?.source_status === "already_changed")
  );
  const supersededInternalFindings = internalDeepFindings.filter(isSupersededInternalFinding);
  const openInternalDeepFindings = internalDeepFindings.filter((finding) => (
    isActionableComplianceFinding(finding)
    && !complianceResolutionMap[finding.id]
    && !isSupersededInternalFinding(finding)
  ));
  const visibleInternalDeepFindings = groupedFindingRepresentatives(
    openInternalDeepFindings.filter((finding) => (
      filter === null || INTERNAL_CLASSIFICATION_CATEGORY[finding.classification] === filter
    )),
    internalCurrentStatusMap,
  );
  const resolvedInternalCount = internalDeepFindings.filter((finding) => complianceResolutionMap[finding.id]).length;
  const internalDeepCounts = openInternalDeepFindings.reduce<Record<string, number>>((acc, finding) => {
    const category = INTERNAL_CLASSIFICATION_CATEGORY[finding.classification];
    acc[category] = (acc[category] ?? 0) + 1;
    return acc;
  }, {});
  const internalDeepHighestSeverity = openInternalDeepFindings.some((finding) => finding.severity === "high")
    ? "high"
    : openInternalDeepFindings.some((finding) => finding.severity === "medium")
      ? "medium"
      : "low";
  const internalCategoryCounts = Object.keys(CATEGORY_LABELS).reduce<Record<string, number>>((acc, key) => {
    acc[key] = (report?.categories[key] ?? 0) + (internalDeepCounts[key] ?? 0);
    return acc;
  }, {});
  const internalOpenIssueTotal = (report?.total_issues ?? 0) + openInternalDeepFindings.length;
  const internalOpenHighestSeverity = report?.health === "red" || internalDeepHighestSeverity === "high"
    ? "high"
    : report?.health === "amber" || internalDeepHighestSeverity === "medium"
      ? "medium"
      : "low";
  const selectedInternalDeepCount = filter ? (internalDeepCounts[filter] ?? 0) : openInternalDeepFindings.length;
  const hasInternalCategoryResults = Boolean(report || internalDeepFindings.length);
  const internalCategorySeverity = (category: string): "high" | "medium" | "low" => {
    const triageIssues = report?.issues[category] ?? [];
    const pairwiseFindings = openInternalDeepFindings.filter((finding) => INTERNAL_CLASSIFICATION_CATEGORY[finding.classification] === category);
    if (triageIssues.some((issue) => issue.severity === "high") || pairwiseFindings.some((finding) => finding.severity === "high")) return "high";
    if (triageIssues.some((issue) => issue.severity === "medium") || pairwiseFindings.some((finding) => finding.severity === "medium")) return "medium";
    return "low";
  };
  const internalReviewActive = internalStatus?.status === "queued" || internalStatus?.status === "running";
  const internalReviewCancellable = internalReviewActive && Boolean(internalStatus?.job_id.startsWith("cr-"));
  const complianceReviewActive = complianceReview?.status.status === "queued" || complianceReview?.status.status === "running";

  return (
    <div className="view-stack">
      <div className="page-intro">
        <h1>Governance</h1>
        <p>Knowledge intelligence and the human-in-the-loop approval gate. Only approved sources are queryable.</p>
      </div>

      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Internal Source Review</h2>
            <p className="muted-text">Internal knowledge hygiene, consistency and correctness checks.</p>
          </div>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 8, flexWrap: "wrap", justifyContent: "flex-end" }}>
            {report ? (
              <span className="status-pill" style={{ display: "inline-flex", alignItems: "center", gap: 7 }}>
                <Dot color={HEALTH[report.health].color} />
                {HEALTH[report.health].label} · {report.total_issues} issues
              </span>
            ) : (
              <span className="status-pill">…</span>
            )}
            <span className="segmented-control" role="group" aria-label="Internal review depth">
              {(Object.keys(REVIEW_DEPTH_LABELS) as ReviewDepth[]).map((depth) => (
                <button
                  key={depth}
                  type="button"
                  className={internalReviewDepth === depth ? "is-active" : ""}
                  disabled={internalReviewBusy}
                  onClick={() => setInternalReviewDepth(depth)}
                  title={REVIEW_DEPTH_HELP[depth]}
                >
                  {REVIEW_DEPTH_LABELS[depth]}
                </button>
              ))}
            </span>
            <label className={`toggle-chip${internalReviewDepth !== "deep" ? " is-disabled" : ""}`} title="Run Deep Audit with reduced GPU offload. This is slower, but keeps GPU load lower.">
              <input
                type="checkbox"
                checked={internalThrottleDeep}
                disabled={internalReviewBusy || internalReviewDepth !== "deep"}
                onChange={(event) => setInternalThrottleDeep(event.target.checked)}
              />
              Throttle Deep
            </label>
            <button type="button" className="mini-button" disabled={busy || internalReviewBusy} onClick={() => runInternalSourceReview(false)}>
              {internalReviewBusy ? "Running..." : "Run review"}
            </button>
            <button type="button" className="text-button" disabled={busy || internalReviewBusy} onClick={() => runInternalSourceReview(true)}>
              Force rerun
            </button>
            <button type="button" className="text-button" disabled={!internalExportAvailable} onClick={exportInternalReview}>
              Export .md
            </button>
            {internalReviewCancellable ? (
              <button type="button" className="text-button" disabled={internalReviewCancelling} onClick={stopInternalSourceReview}>
                {internalReviewCancelling ? "Stopping..." : "Stop"}
              </button>
            ) : null}
          </span>
        </div>
        {internalReviewError ? (
          <p className="muted-text" style={{ color: "var(--red)" }}>{internalReviewError}</p>
        ) : null}
        {internalStatus ? (
          <div className="compliance-progress-block" style={{ marginBottom: 12 }}>
            <div className="result-head">
              <b>{internalStatus.status.replace("_", " ")}</b>
              <span style={{ display: "inline-flex", gap: 8, flexWrap: "wrap", justifyContent: "flex-end" }}>
                <span className="status-pill">{internalStatus.item_completed} / {internalStatus.item_total} pairs</span>
                <span className="status-pill">{REVIEW_DEPTH_LABELS[internalStatus.review_depth ?? internalReviewDepth]}</span>
                {internalStatus.throttle_deep ? <span className="status-pill">throttled</span> : null}
                <span className="status-pill">elapsed {formatDuration(internalStatus.elapsed_seconds)}</span>
                {internalStatus.estimated_remaining_label ? (
                  <span className="status-pill">{formatTimingLabel(internalStatus.estimated_remaining_label, internalStatus.estimated_remaining_seconds)}</span>
                ) : null}
                <span className="status-pill">{cacheLabel(internalStatus.cache_status)}</span>
              </span>
            </div>
            <div className="compliance-progress-track" aria-label="Internal source review progress">
              <div className="compliance-progress-fill" style={{ width: `${internalStatus.progress_percent}%` }} />
            </div>
            {internalStatus.current_item ? (
              <p className="result-cite">Reviewing {internalStatus.current_item.title}</p>
            ) : internalStatus.status === "completed" ? (
              <p className="result-cite">Internal Source Review completed.</p>
            ) : internalStatus.status === "cancelled" ? (
              <p className="result-cite">Internal Source Review stopped.</p>
            ) : null}
          </div>
        ) : null}
        {/* Click a category to filter the list; click again (or All) to clear. */}
        <div className="result-list" style={{ gridTemplateColumns: "repeat(4, 1fr)", display: "grid", gap: 12 }}>
          {hasInternalCategoryResults ? (
            <button
              type="button"
              className="result-card"
              style={{ cursor: "pointer", textAlign: "left", boxShadow: filter === null ? "0 0 0 2px #db2777" : undefined, ...issueTone(internalOpenIssueTotal, internalOpenHighestSeverity) }}
              onClick={() => setFilter(null)}
            >
              <div className="result-head"><b>All</b><span className="status-pill">{internalOpenIssueTotal}</span></div>
            </button>
          ) : null}
          {hasInternalCategoryResults &&
            Object.entries(CATEGORY_LABELS).map(([key, label]) => (
              <button
                type="button"
                key={key}
                className="result-card"
                style={{
                  cursor: "pointer",
                  textAlign: "left",
                  boxShadow: filter === key ? "0 0 0 2px #db2777" : undefined,
                  ...issueTone(
                    internalCategoryCounts[key] ?? 0,
                    internalCategorySeverity(key),
                  ),
                }}
                onClick={() => setFilter((f) => (f === key ? null : key))}
              >
                <div className="result-head">
                  <b>{label}</b>
                  <span className="status-pill">{internalCategoryCounts[key] ?? 0}</span>
                </div>
                <p className="result-cite" style={{ marginTop: 4 }}>{CATEGORY_DESCRIPTIONS[key]}</p>
              </button>
            ))}
        </div>
        {visibleIssues.length > 0 ? (
          <div className="result-list" style={{ marginTop: 12 }}>
            {visibleIssues.map((i, idx) => (
              <div className="result-card" key={idx}>
                <div className="result-head">
                  <b style={{ display: "inline-flex", alignItems: "center", gap: 7 }}>
                    <Dot color={SEVERITY_COLOR[i.severity]} />
                    {CATEGORY_LABELS[i.cat]} · {i.check.replace(/_/g, " ")}
                  </b>
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                    <span className="status-pill">{i.severity}</span>
                    <button type="button" className="mini-button" onClick={() => setReviewing(i)}>Review</button>
                    <button type="button" className="text-button" disabled={busy} onClick={() => accept(i)} title="Drop from the list and record as accepted">Accept</button>
                  </span>
                </div>
                {report?.descriptions?.[i.check] ? <p className="result-cite">{report.descriptions[i.check]}</p> : null}
                <p className="result-text">{i.advisor_summary || i.detail}</p>
                {i.recommended_action ? <p className="result-cite">Recommended action: {i.recommended_action}</p> : null}
                {i.why_it_matters ? <p className="result-cite">Why it matters: {i.why_it_matters}</p> : null}
                {IMPACT[i.check] ? <p className="result-cite" style={{ color: "#b45309" }}>Impact if unresolved: {IMPACT[i.check]}</p> : null}
                <p className="result-cite">{i.source_title}</p>
              </div>
            ))}
          </div>
        ) : report ? (
          <p className="muted-text" style={{ marginTop: 12 }}>
            {filter
              ? `No triage-only ${CATEGORY_LABELS[filter]} issues${selectedInternalDeepCount ? "; pairwise findings are listed below." : "."}`
              : selectedInternalDeepCount
                ? "No triage-only issues detected; pairwise findings are listed below."
                : "No issues detected."}
          </p>
        ) : null}
        {internalDeepFindings.length ? (
          <>
            <div className="compliance-summary-grid" style={{ marginTop: 16 }}>
              <div className="result-card" style={issueTone(openInternalDeepFindings.length, internalDeepHighestSeverity)}>
                <div className="result-head"><b>{openInternalDeepFindings.length}</b></div>
                <p className="result-cite">Actionable pairwise findings</p>
              </div>
              <div className="result-card">
                <div className="result-head"><b>{resolvedInternalCount}</b></div>
                <p className="result-cite">Recorded decisions</p>
              </div>
              <div className="result-card">
                <div className="result-head"><b>{supersededInternalFindings.length}</b></div>
                <p className="result-cite">Superseded by edits</p>
              </div>
              <div className="result-card">
                <div className="result-head"><b>{supportedInternalFindings.length}</b></div>
                <p className="result-cite">Supported coverage</p>
              </div>
              <div className="result-card">
                <div className="result-head"><b>{internalStatus?.finding_count ?? internalDeepFindings.length}</b></div>
                <p className="result-cite">Pairwise findings</p>
              </div>
            </div>
            {openInternalDeepFindings.length === 0 ? (
              <p className="muted-text" style={{ marginTop: 12 }}>No actionable pairwise findings are open; supported coverage is listed separately.</p>
            ) : null}
            <div className="result-list compliance-finding-list">
              {visibleInternalDeepFindings.map((finding) => {
                const currentStatus = internalCurrentStatusMap[finding.id];
                const category = INTERNAL_CLASSIFICATION_CATEGORY[finding.classification];
                return (
                  <div className={`result-card compliance-finding-card compliance-finding-card--${finding.severity}`} key={finding.id}>
                    <div className="result-head">
                      <b style={{ display: "inline-flex", alignItems: "center", gap: 7 }}>
                        <Dot color={COMPLIANCE_SEVERITY_COLOR[finding.severity]} />
                        {CATEGORY_LABELS[category]} · {COMPLIANCE_FINDING_LABELS[finding.classification]}
                      </b>
                      <span style={{ display: "inline-flex", alignItems: "center", gap: 8, flexWrap: "wrap", justifyContent: "flex-end" }}>
                        <span className={`status-pill${finding.severity === "high" ? " status-pill--warn" : ""}`}>{finding.severity}</span>
                        <span className="status-pill">{formatPercent(finding.confidence)} review score</span>
                        <span className="status-pill">{formatPercent(finding.alignment_score)} aligned</span>
                        {currentStatus?.related_count > 1 ? <span className="status-pill">{currentStatus.related_count} related</span> : null}
                        <button type="button" className="mini-button" onClick={() => setResolvingInternalFinding(finding)}>Resolve</button>
                      </span>
                    </div>
                    <p className="result-text">{finding.advisor_summary || finding.rationale}</p>
                    {currentStatus?.message ? <p className="result-cite">{currentStatus.message}</p> : null}
                    {finding.why_it_matters ? <p className="result-cite" style={{ color: "#7c2d12" }}>Why it matters: {finding.why_it_matters}</p> : null}
                    {finding.recommended_action ? <p className="result-cite">Recommended action: {finding.recommended_action}</p> : null}
                    <div className="compliance-evidence-grid">
                      <div className="compliance-evidence-block">
                        <p className="result-cite">Source A evidence</p>
                        {finding.external_evidence ? (
                          <>
                            <b>{finding.external_evidence.source_title}</b>
                            <p className="result-cite">{finding.external_evidence.citation || finding.external_evidence.heading}</p>
                            <ComplianceEvidenceText text={finding.external_evidence.text} />
                          </>
                        ) : (
                          <p className="muted-text">No Source A evidence attached.</p>
                        )}
                      </div>
                      <div className="compliance-evidence-block">
                        <p className="result-cite">Source B evidence</p>
                        {finding.internal_evidence ? (
                          <>
                            <b>{finding.internal_evidence.source_title}</b>
                            <p className="result-cite">{finding.internal_evidence.citation || finding.internal_evidence.heading}</p>
                            <ComplianceEvidenceText text={finding.internal_evidence.text} />
                          </>
                        ) : (
                          <p className="muted-text">No aligned Source B wording found.</p>
                        )}
                      </div>
                    </div>
                    {finding.confidence_interpretation ? (
                      <p className="result-cite">{finding.confidence_interpretation}</p>
                    ) : null}
                    {finding.signals.length ? (
                      <details>
                        <summary className="result-cite">Signals</summary>
                        <p className="result-cite">{finding.signals.join("; ")}</p>
                      </details>
                    ) : null}
                  </div>
                );
              })}
            </div>
            {supportedInternalFindings.length ? (
              <details style={{ marginTop: 12 }}>
                <summary className="result-cite">Supported internal coverage ({supportedInternalFindings.length})</summary>
                <div className="result-list" style={{ marginTop: 12 }}>
                  {supportedInternalFindings.slice(0, 8).map((finding) => (
                    <div className="result-card" key={finding.id}>
                      <div className="result-head">
                        <b>{COMPLIANCE_FINDING_LABELS[finding.classification]}</b>
                        <span className="status-pill">{formatPercent(finding.alignment_score)} aligned</span>
                      </div>
                      <p className="result-text">{finding.advisor_summary || finding.rationale}</p>
                      <p className="result-cite">
                        {finding.external_evidence?.source_title ?? "Source A"} → {finding.internal_evidence?.source_title ?? "Source B"}
                      </p>
                    </div>
                  ))}
                </div>
              </details>
            ) : null}
          </>
        ) : internalStatus?.status === "completed" && internalStatus.review_mode === "internal_vs_internal" ? (
          <p className="muted-text" style={{ marginTop: 12 }}>No pairwise internal findings returned by the latest review.</p>
        ) : null}
      </div>

      {reviewing ? (
        <ReviewWorkbench issue={reviewing} onClose={() => setReviewing(null)} onSaved={() => void refresh()} />
      ) : null}

      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>External Source Review</h2>
            <p className="muted-text">Pairwise comparison of external obligations and approved internal wording.</p>
          </div>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 8, flexWrap: "wrap", justifyContent: "flex-end" }}>
            <span className={complianceStatusClass}>{complianceStatusText}</span>
            <span className="segmented-control" role="group" aria-label="External review depth">
              {(Object.keys(REVIEW_DEPTH_LABELS) as ReviewDepth[]).map((depth) => (
                <button
                  key={depth}
                  type="button"
                  className={complianceReviewDepth === depth ? "is-active" : ""}
                  disabled={complianceBusy}
                  onClick={() => setComplianceReviewDepth(depth)}
                  title={REVIEW_DEPTH_HELP[depth]}
                >
                  {REVIEW_DEPTH_LABELS[depth]}
                </button>
              ))}
            </span>
            <label className={`toggle-chip${complianceReviewDepth !== "deep" ? " is-disabled" : ""}`} title="Run Deep Audit with reduced GPU offload. This is slower, but keeps GPU load lower.">
              <input
                type="checkbox"
                checked={complianceThrottleDeep}
                disabled={complianceBusy || complianceReviewDepth !== "deep"}
                onChange={(event) => setComplianceThrottleDeep(event.target.checked)}
              />
              Throttle Deep
            </label>
            <button type="button" className="mini-button" disabled={busy || complianceBusy || !complianceAvailable} onClick={() => runComplianceReview(false)}>
              {complianceBusy ? "Running..." : "Run review"}
            </button>
            <button type="button" className="text-button" disabled={busy || complianceBusy || !complianceAvailable} onClick={() => runComplianceReview(true)}>
              Force rerun
            </button>
            <button type="button" className="text-button" disabled={!externalExportAvailable} onClick={exportExternalReview}>
              Export .md
            </button>
            {complianceReviewActive ? (
              <button type="button" className="text-button" disabled={complianceCancelling} onClick={stopComplianceReview}>
                {complianceCancelling ? "Stopping..." : "Stop"}
              </button>
            ) : null}
          </span>
        </div>
        {complianceError ? (
          <p className="muted-text" style={{ color: "var(--red)" }}>{complianceError}</p>
        ) : null}
        {complianceStatus?.status === "not_configured" ? (
          <p className="muted-text">Standalone compliance reasoning service is not configured for this environment.</p>
        ) : complianceStatus?.status === "unavailable" ? (
          <p className="muted-text">Standalone compliance reasoning service is currently unavailable.</p>
        ) : null}
        {complianceReview ? (
          <>
            <div className="compliance-progress-block">
              <div className="result-head">
                <b>{complianceReview.status.status.replace("_", " ")}</b>
                <span style={{ display: "inline-flex", gap: 8, flexWrap: "wrap", justifyContent: "flex-end" }}>
                  <span className="status-pill">{complianceReview.status.pair_completed} / {complianceReview.status.pair_total} pairs</span>
                  <span className="status-pill">{REVIEW_DEPTH_LABELS[complianceReview.status.review_depth ?? complianceReviewDepth]}</span>
                  {complianceReview.status.throttle_deep ? <span className="status-pill">throttled</span> : null}
                  <span className="status-pill">elapsed {formatDuration(complianceReview.status.elapsed_seconds)}</span>
                  {complianceReview.status.current_pair ? (
                    <span className="status-pill">current pair {formatDuration(complianceReview.status.current_pair_elapsed_seconds)}</span>
                  ) : null}
                  <span className="status-pill">{formatTimingLabel(complianceReview.status.estimated_remaining_label, complianceReview.status.estimated_remaining_seconds)}</span>
                </span>
              </div>
              <div className="compliance-progress-track" aria-label="Compliance review progress">
                <div className="compliance-progress-fill" style={{ width: `${complianceReview.status.progress_percent}%` }} />
              </div>
              {complianceReview.status.current_pair ? (
                <p className="result-cite">
                  Checking {complianceReview.status.current_pair.external_title} against {complianceReview.status.current_pair.internal_title}
                </p>
              ) : complianceReview.status.status === "completed" ? (
                <p className="result-cite">Pairwise review completed.</p>
              ) : null}
              <p className="result-cite">
                Cache: {complianceReview.status.cache_hit_count} reused · {complianceReview.status.cache_miss_count} reviewed · {complianceReview.status.cache_bypass_count} forced
              </p>
            </div>
            <div className="compliance-summary-grid">
              <div className="result-card" style={issueTone(openComplianceFindings.length, complianceHighestSeverity)}>
                <div className="result-head"><b>{openComplianceFindings.length}</b></div>
                <p className="result-cite">Actionable findings</p>
              </div>
              <div className="result-card">
                <div className="result-head"><b>{resolvedComplianceCount}</b></div>
                <p className="result-cite">Recorded decisions</p>
              </div>
              <div className="result-card">
                <div className="result-head"><b>{supersededComplianceFindings.length}</b></div>
                <p className="result-cite">Superseded by edits</p>
              </div>
              <div className="result-card">
                <div className="result-head"><b>{supportedComplianceFindings.length}</b></div>
                <p className="result-cite">Supported coverage</p>
              </div>
              <div className="result-card">
                <div className="result-head"><b>{complianceReview.status.obligation_count}</b></div>
                <p className="result-cite">Obligation checks</p>
              </div>
              <div className="result-card">
                <div className="result-head"><b>{complianceReview.status.internal_claim_count}</b></div>
                <p className="result-cite">Internal claim checks</p>
              </div>
              <div className="result-card">
                <div className="result-head"><b>{complianceReview.status.audit.engine}</b></div>
                <p className="result-cite">{complianceReview.status.audit.model_profile} · {formatDate(complianceReview.status.completed_at)}</p>
              </div>
            </div>
            {complianceFindings.length ? (
              <>
                <div className="compliance-count-grid">
                  {Object.entries(COMPLIANCE_FINDING_LABELS)
                    .filter(([key]) => complianceCounts[key])
                    .map(([key, label]) => (
                      <button
                        type="button"
                        className="result-card"
                        key={key}
                        style={{
                          cursor: "pointer",
                          textAlign: "left",
                          boxShadow: complianceFilter === key ? "0 0 0 2px #db2777" : undefined,
                          ...issueTone(
                            complianceCounts[key],
                            openComplianceFindings.some((finding) => finding.classification === key && finding.severity === "high")
                              ? "high"
                              : openComplianceFindings.some((finding) => finding.classification === key && finding.severity === "medium")
                                ? "medium"
                                : "low",
                          ),
                        }}
                        onClick={() => setComplianceFilter((current) => (current === key ? null : (key as ComplianceFindingClassification)))}
                      >
                        <div className="result-head">
                          <b>{label}</b>
                          <span className="status-pill">{complianceCounts[key]}</span>
                        </div>
                        <p className="result-cite">{COMPLIANCE_FINDING_DESCRIPTIONS[key as ComplianceFindingClassification]}</p>
                      </button>
                    ))}
                </div>
                {openComplianceFindings.length === 0 ? (
                  <p className="muted-text" style={{ marginTop: 12 }}>No actionable external-source findings are open; supported coverage is listed separately.</p>
                ) : null}
                <div className="result-list compliance-finding-list">
                  {visibleComplianceFindings.map((finding) => {
                    const currentStatus = complianceCurrentStatusMap[finding.id];
                    return (
                    <div className={`result-card compliance-finding-card compliance-finding-card--${finding.severity}`} key={finding.id}>
                      <div className="result-head">
                        <b style={{ display: "inline-flex", alignItems: "center", gap: 7 }}>
                          <Dot color={COMPLIANCE_SEVERITY_COLOR[finding.severity]} />
                          {COMPLIANCE_FINDING_LABELS[finding.classification]}
                        </b>
                        <span style={{ display: "inline-flex", alignItems: "center", gap: 8, flexWrap: "wrap", justifyContent: "flex-end" }}>
                          <span className={`status-pill${finding.severity === "high" ? " status-pill--warn" : ""}`}>{finding.severity}</span>
                          <span className="status-pill">{formatPercent(finding.confidence)} review score</span>
                          <span className="status-pill">{formatPercent(finding.alignment_score)} aligned</span>
                          {currentStatus?.related_count > 1 ? <span className="status-pill">{currentStatus.related_count} related</span> : null}
                          <button type="button" className="mini-button" onClick={() => setResolvingFinding(finding)}>Resolve</button>
                        </span>
                      </div>
                      <p className="result-text">{finding.advisor_summary || finding.rationale}</p>
                      {currentStatus?.message ? <p className="result-cite">{currentStatus.message}</p> : null}
                      {finding.why_it_matters ? <p className="result-cite" style={{ color: "#7c2d12" }}>Why it matters: {finding.why_it_matters}</p> : null}
                      {finding.recommended_action ? <p className="result-cite">Recommended action: {finding.recommended_action}</p> : null}
                      <div className="compliance-evidence-grid">
                        <div className="compliance-evidence-block">
                          <p className="result-cite">External evidence</p>
                          {finding.external_evidence ? (
                            <>
                              <b>{finding.external_evidence.source_title}</b>
                              <p className="result-cite">{finding.external_evidence.citation || finding.external_evidence.heading}</p>
                              <ComplianceEvidenceText text={finding.external_evidence.text} />
                            </>
                          ) : (
                            <p className="muted-text">No external evidence attached.</p>
                          )}
                        </div>
                        <div className="compliance-evidence-block">
                          <p className="result-cite">{finding.classification === "missing_obligation" ? "Internal coverage" : "Internal evidence"}</p>
                          {finding.internal_evidence ? (
                            <>
                              <b>{finding.internal_evidence.source_title}</b>
                              <p className="result-cite">{finding.internal_evidence.citation || finding.internal_evidence.heading}</p>
                              <ComplianceEvidenceText text={finding.internal_evidence.text} />
                            </>
                          ) : (
                            <p className="muted-text">
                              {finding.classification === "missing_obligation"
                                ? "No sufficiently similar approved wording was found for this external obligation."
                                : "No aligned internal wording found."}
                            </p>
                          )}
                        </div>
                      </div>
                      {finding.confidence_interpretation ? (
                        <p className="result-cite">{finding.confidence_interpretation}</p>
                      ) : null}
                      {finding.signals.length ? (
                        <details>
                          <summary className="result-cite">Signals</summary>
                          <p className="result-cite">{finding.signals.join("; ")}</p>
                        </details>
                      ) : null}
                    </div>
                    );
                  })}
                </div>
                {supportedComplianceFindings.length ? (
                  <details style={{ marginTop: 12 }}>
                    <summary className="result-cite">Supported external coverage ({supportedComplianceFindings.length})</summary>
                    <div className="result-list" style={{ marginTop: 12 }}>
                      {supportedComplianceFindings.slice(0, 8).map((finding) => (
                        <div className="result-card" key={finding.id}>
                          <div className="result-head">
                            <b>{COMPLIANCE_FINDING_LABELS[finding.classification]}</b>
                            <span className="status-pill">{formatPercent(finding.alignment_score)} aligned</span>
                          </div>
                          <p className="result-text">{finding.advisor_summary || finding.rationale}</p>
                          <p className="result-cite">
                            {finding.external_evidence?.source_title ?? "External source"} → {finding.internal_evidence?.source_title ?? "Internal source"}
                          </p>
                        </div>
                      ))}
                    </div>
                  </details>
                ) : null}
              </>
            ) : (
              <p className="muted-text" style={{ marginTop: 12 }}>No compliance findings returned by the latest review.</p>
            )}
          </>
        ) : complianceAvailable ? (
          <p className="muted-text">No compliance reasoning run has been loaded in this session.</p>
        ) : null}
      </div>

      {resolvingFinding ? (
        <ComplianceFindingWorkbench
          finding={resolvingFinding}
          existingResolution={complianceResolutionMap[resolvingFinding.id]}
          currentStatus={complianceCurrentStatusMap[resolvingFinding.id]}
          onClose={() => setResolvingFinding(null)}
          onResolved={recordComplianceResolution}
        />
      ) : null}

      {resolvingInternalFinding ? (
        <ComplianceFindingWorkbench
          finding={resolvingInternalFinding}
          existingResolution={complianceResolutionMap[resolvingInternalFinding.id]}
          currentStatus={internalCurrentStatusMap[resolvingInternalFinding.id]}
          evidenceLabels={{
            title: "Resolve internal source finding",
            reference: "Source A evidence",
            editable: "Source B evidence",
            missingReference: "No Source A evidence attached.",
            missingEditable: "No aligned Source B wording was attached.",
          }}
          onClose={() => setResolvingInternalFinding(null)}
          onResolved={recordInternalComplianceResolution}
        />
      ) : null}

      <details className="legacy-governance-details" style={{ order: 99 }}>
        <summary>Legacy regulatory signal triage</summary>
      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Regulatory signals</h2>
            <p className="muted-text">Keyword and theme triage from approved knowledge sections.</p>
          </div>
          <span className="status-pill">
            {regulatory ? `${regulatory.candidate_count} candidates` : "…"}
          </span>
        </div>
        {regulatory && regulatory.candidates.length ? (
          <>
            <div className="result-list" style={{ marginBottom: 12 }}>
              {Object.entries(REGULATORY_STATUS_GUIDE).map(([status, description]) => (
                <div className="result-card" key={status}>
                  <div className="result-head">
                    <b>{status.replace("_", " ")}</b>
                    <span className="status-pill">{regulatory.review_counts[status] ?? 0}</span>
                  </div>
                  <p className="result-cite">{description}</p>
                </div>
              ))}
            </div>
            <div className="result-list">
              {regulatory.candidates.slice(0, 8).map((candidate) => (
                <div className="result-card" key={candidate.id}>
                  <div className="result-head">
                    <b>{candidate.label}</b>
                    <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                      <span className="status-pill">{candidate.confidence}</span>
                      <span className="status-pill">{candidate.review_status.replace("_", " ")}</span>
                    </span>
                  </div>
                  <p className="result-cite">{candidate.source_title} · score {candidate.score}</p>
                  <p className="result-text">{candidate.reason}</p>
                  {candidate.passages.slice(0, 2).map((passage) => (
                    <p className="result-cite" key={`${candidate.id}-${passage.ordinal}`}>
                      {passage.heading}: {passage.excerpt}
                    </p>
                  ))}
                  {candidate.external_matches.length ? (
                    <p className="result-cite">
                      External context: {candidate.external_matches.map((match) => `${match.title} v${match.version}`).join("; ")}
                    </p>
                  ) : null}
                  <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
                    <button
                      type="button"
                      className="mini-button"
                      disabled={busy}
                      onClick={() => reviewCandidate(candidate, "relevant")}
                      title={REGULATORY_STATUS_GUIDE.relevant}
                    >
                      Relevant
                    </button>
                    <button
                      type="button"
                      className="mini-button"
                      disabled={busy}
                      onClick={() => simulateImpact(candidate)}
                    >
                      Simulate impact
                    </button>
                    <button
                      type="button"
                      className="mini-button"
                      disabled={busy}
                      onClick={() => reviewCandidate(candidate, "needs_research")}
                      title={REGULATORY_STATUS_GUIDE.needs_research}
                    >
                      Needs research
                    </button>
                    <button
                      type="button"
                      className="text-button"
                      disabled={busy}
                      onClick={() => reviewCandidate(candidate, "irrelevant")}
                      title={REGULATORY_STATUS_GUIDE.irrelevant}
                    >
                      Irrelevant
                    </button>
                  </div>
                </div>
              ))}
            </div>
            {impact ? (
              <div style={{ marginTop: 16, paddingTop: 16, borderTop: "1px solid var(--line)" }}>
                <div className="panel-heading">
                  <div>
                    <h2 style={{ fontSize: 15 }}>Impact simulation</h2>
                    <p className="muted-text">{impact.label} · {impact.affected_source_count} affected sources · {impact.external_context_count} external contexts</p>
                  </div>
                  <span className={`status-pill${impact.impact_band === "high" ? " status-pill--warn" : " status-pill--good"}`}>
                    {impact.impact_score} · {impact.impact_band}
                  </span>
                </div>
                <div className="result-list" style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10, marginBottom: 12 }}>
                  <div className="result-card">
                    <div className="result-head"><b>{impact.review_status.replace("_", " ")}</b></div>
                    <p className="result-cite">Review state</p>
                  </div>
                  <div className="result-card">
                    <div className="result-head"><b>{impact.affected_process_areas.length}</b></div>
                    <p className="result-cite">Process areas</p>
                  </div>
                  <div className="result-card">
                    <div className="result-head"><b>{impact.external_context_count}</b></div>
                    <p className="result-cite">External matches</p>
                  </div>
                </div>
                <div className="result-list" style={{ gap: 10, marginBottom: 12 }}>
                  {impact.recommended_actions.map((action) => (
                    <div className="result-card" key={action}>
                      <p className="result-text">{action}</p>
                    </div>
                  ))}
                </div>
                <div className="table-frame">
                  <table className="data-table regulatory-impact-table">
                    <colgroup>
                      <col style={{ width: "18%" }} />
                      <col style={{ width: "10%" }} />
                      <col style={{ width: "20%" }} />
                      <col style={{ width: "30%" }} />
                      <col style={{ width: "22%" }} />
                    </colgroup>
                    <thead>
                      <tr><th>Source</th><th>Impact</th><th>Process areas</th><th>Evidence</th><th>Action</th></tr>
                    </thead>
                    <tbody>
                      {impact.affected_sources.map((source) => (
                        <tr key={source.source_id}>
                          <td>{source.source_title}</td>
                          <td>{source.impact_score} · {source.impact_band}</td>
                          <td>{source.process_areas.join("; ")}</td>
                          <td>
                            {source.passages.slice(0, 2).map((passage) => (
                              <div className="regulatory-evidence-block" key={`${source.source_id}-${passage.ordinal}`}>
                                <p className="result-cite">{passage.heading}</p>
                                <Markdown text={passage.excerpt} />
                              </div>
                            ))}
                          </td>
                          <td>{source.recommended_action}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="result-cite" style={{ marginTop: 10 }}>{impact.assumptions.join(" ")}</p>
              </div>
            ) : null}
          </>
        ) : regulatory ? (
          <p className="muted-text">No regulatory candidates detected in approved ingested sources.</p>
        ) : (
          <p className="muted-text">Loading regulatory candidates…</p>
        )}
      </div>
      </details>

      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Source approval</h2>
            <p className="muted-text">Approve a source before the assistant can use it.</p>
          </div>
        </div>
        {error ? <p className="muted-text" style={{ color: "var(--red)" }}>{error}</p> : null}
        {sources.length === 0 ? (
          <div className="empty-card"><b>No sources</b><span>Upload and ingest documents first.</span></div>
        ) : (
          <div className="table-frame">
            <table className="data-table">
              <thead>
                <tr><th>Title</th><th>Review state</th><th>State</th><th>Approval</th><th /></tr>
              </thead>
              <tbody>
                {sources.map((s) => {
                  const sum = report?.source_summary?.[s.id];
                  const externalOpen = openComplianceFindings.filter((finding) => finding.internal_evidence?.source_id === s.id);
                  const externalResolved = complianceResolutions?.source_summary?.[s.id];
                  return (
                  <tr key={s.id}>
                    <td>{s.title}</td>
                    <td style={{ whiteSpace: "nowrap" }}>
                      {sum?.active ? <span className="status-pill status-pill--warn" title="Actionable issues">{sum.active} to review</span> : null}
                      {sum?.structural ? <span className="status-pill" title="Boilerplate shared across documents (titles, disclaimers) — expected, excluded from the list">{sum.structural} structural</span> : null}
                      {sum?.accepted ? <span className="status-pill" title="Issues you accepted">{sum.accepted} accepted</span> : null}
                      {externalOpen.length ? <span className="status-pill status-pill--warn" title="Open external-source compliance findings">{externalOpen.length} external open</span> : null}
                      {externalResolved?.resolved ? <span className="status-pill status-pill--good" title="Recorded compliance decisions">{externalResolved.resolved} external resolved</span> : null}
                      {externalResolved?.superseded_by_source_edit ? <span className="status-pill" title="Findings made stale by source edits">{externalResolved.superseded_by_source_edit} superseded</span> : null}
                      {!sum?.active && !sum?.structural && !sum?.accepted && !externalOpen.length && !externalResolved?.resolved && !externalResolved?.superseded_by_source_edit ? <span className="status-pill status-pill--good">clear</span> : null}
                    </td>
                    <td>{s.processing_state}</td>
                    <td>
                      <span className={`status-pill${s.approval_status === "approved" ? " status-pill--good" : s.approval_status === "rejected" ? " status-pill--warn" : ""}`}>
                        {s.approval_status}
                      </span>
                    </td>
                    <td style={{ whiteSpace: "nowrap" }}>
                      {s.approval_status !== "approved" ? (
                        <button type="button" className="mini-button" disabled={busy} onClick={() => act(approveSource, s.id)}>Approve</button>
                      ) : null}
                      {s.approval_status !== "rejected" ? (
                        <button type="button" className="text-button" disabled={busy} onClick={() => act(rejectSource, s.id)}>Reject</button>
                      ) : null}
                    </td>
                  </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <details className="legacy-governance-details">
        <summary>Legacy re-analysis audit snapshot</summary>
      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Governance re-analysis</h2>
            <p className="muted-text">
              Last analysed: {formatDate(reanalysis?.analysed_at)}
            </p>
          </div>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 8, flexWrap: "wrap", justifyContent: "flex-end" }}>
            <span className={reanalysisStatusClass}>{reanalysisStatus}</span>
            <button type="button" className="mini-button" disabled={busy || reanalysisBusy} onClick={runReanalysis}>
              {reanalysisBusy ? "Running..." : "Re-analyse Governance"}
            </button>
          </span>
        </div>
        {reanalysis?.has_run ? (
          <>
            <div className="governance-reanalysis-grid">
              <div className="result-card">
                <div className="result-head"><b>{reanalysis.external_snapshot_count ?? 0}</b></div>
                <p className="result-cite">External snapshots</p>
              </div>
              <div className="result-card">
                <div className="result-head"><b>{reanalysis.external_matched_count ?? 0}</b></div>
                <p className="result-cite">Matched external sources</p>
              </div>
              <div className="result-card">
                <div className="result-head"><b>{reanalysis.external_unmatched_count ?? 0}</b></div>
                <p className="result-cite">Unmatched external sources</p>
              </div>
              <div className="result-card">
                <div className="result-head"><b>{reanalysis.new_issue_count ?? 0}</b></div>
                <p className="result-cite">New active issues</p>
              </div>
              <div className="result-card">
                <div className="result-head"><b>{reanalysis.new_candidate_count ?? 0}</b></div>
                <p className="result-cite">New candidates</p>
              </div>
              <div className="result-card">
                <div className="result-head"><b>{reanalysis.previous_decisions_preserved ?? 0}</b></div>
                <p className="result-cite">Preserved decisions</p>
              </div>
            </div>
            {reanalysis.needs_reanalysis ? (
              <p className="result-cite" style={{ marginTop: 10, color: "#b45309" }}>
                Pending: {reanalysis.pending_external_snapshot_count} external snapshot(s), {reanalysis.pending_internal_change_count} internal source change(s).
              </p>
            ) : null}
            {coveragePreview.length ? (
              <div className="result-list governance-coverage-list">
                {coveragePreview.map((item) => (
                  <div className="result-card" key={item.snapshot_id}>
                    <div className="result-head">
                      <b>{item.title}</b>
                      <span className={`status-pill${item.status === "matched" ? " status-pill--good" : ""}`}>
                        {item.status === "matched" ? `${item.matched_candidate_count} match${item.matched_candidate_count === 1 ? "" : "es"}` : "No match"}
                      </span>
                    </div>
                    <p className="result-cite">{item.provider} v{item.version} · {item.url}</p>
                    {item.matched_candidates.length ? (
                      <p className="result-text">
                        {item.matched_candidates.map((candidate) => `${candidate.label} in ${candidate.source_title}`).join("; ")}
                      </p>
                    ) : null}
                    {item.matched_terms.length ? (
                      <p className="result-cite">Terms: {item.matched_terms.slice(0, 10).join(", ")}</p>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : (
              <p className="muted-text" style={{ marginTop: 12 }}>
                No external snapshots were included in the latest run.
              </p>
            )}
          </>
        ) : reanalysis ? (
          <>
            <p className="muted-text">Run re-analysis to create the first audit snapshot.</p>
            {reanalysis.needs_reanalysis ? (
              <p className="result-cite" style={{ marginTop: 10, color: "#b45309" }}>
                Pending: {reanalysis.pending_external_snapshot_count} external snapshot(s), {reanalysis.pending_internal_change_count} internal source change(s).
              </p>
            ) : null}
          </>
        ) : (
          <p className="muted-text">Loading re-analysis status...</p>
        )}
      </div>
      </details>
    </div>
  );
}
