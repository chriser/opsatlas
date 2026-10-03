// Content management API (CM E1): governed drafts, versions, comments and insights for any source.
import { apiRequest as request, apiUpload, getActiveSpace } from "../api";

// The document open on the Document page is in one space (KS S6): its requests go there. Other calls name their space,
// or use the active space.
let documentSpace: string | null = null;
export function setDocumentSpace(space: string | null) {
  documentSpace = space;
}
function apiRequest<T>(method: string, path: string, body?: unknown, space?: string | null): Promise<T> {
  return request<T>(method, path, body, space ?? documentSpace);
}
export const contentRequest = apiRequest;
export function getDocumentSpace(): string | null {
  return documentSpace;
}

export interface DocStats {
  words: number;
  sentences: number;
  reading_minutes: number;
  flesch: number | null;
  grade: number | null;
  readability: string | null;
}

export interface ActivityEntry {
  at: string;
  actor: string;
  action: string;
  detail: string | null;
}

export interface RecordInfo {
  id: string;
  title: string;
  status: string;
  kind: string;
  contributor: string | null;
  approval: string;
  eligible: boolean;
  review_block: string | null;
}

export interface ContentDocument {
  source: {
    id: string;
    title: string;
    filename: string;
    source_type: string;
    sensitivity: string;
    version: number;
    processing_state: string;
    approval_status: string;
    section_count: number;
    created_at: string;
    content_sha256: string;
    effective_from: string | null;
    effective_to: string | null;
    phases: string[];
    applies_to: string[];
    supersedes: string[];
    editable: boolean;
    format: string;
  };
  published: { text: string; sha: string; stats: DocStats };
  draft: { text: string; sha: string; base_sha: string; updated_at: string; author: string; stale: boolean; stats: DocStats } | null;
  status: "published" | "draft" | "submitted";
  submitted: { at: string; by: string; note: string | null } | null;
  comments: { open: number; resolved: number };
  versions: number;
  last_activity: ActivityEntry | null;
  operator: { name: string; role: string };
  // Added by the sales workspace.
  record?: RecordInfo | null;
  cites?: { source_id: string; title: string; path: string | null }[];
  cited_by?: { id: string; title: string; source_id: string }[];
  title_from_heading?: boolean;
}

export interface VersionEntry {
  n: number;
  sha: string;
  label: "imported" | "approved" | "restored" | string;
  author: string;
  role: string;
  at: string;
  note: string | null;
  source_version: number | null;
  chars: number;
  current: boolean;
}

export interface DiffOp {
  op: "equal" | "insert" | "delete";
  text: string;
}

export interface Reply {
  id: string;
  text: string;
  author: string;
  role: string;
  at: string;
}

export interface Comment {
  id: string;
  source_id: string;
  quote: string;
  prefix: string;
  suffix: string;
  text: string;
  author: string;
  role: string;
  at: string;
  status: "open" | "resolved";
  resolved_at: string | null;
  resolved_by: string | null;
  replies: Reply[];
  anchored: boolean;
}

export interface Suggestion {
  key: string;
  kind: string;
  check: string;
  label: string;
  text: string;
  quote: string | null;
  fix?: { find: string; replace: string; label: string } | null;
  other?: { title: string; text: string; source_id: string };
  answer: string | null;
  where?: string[];
  hint?: string | null;
  acronyms?: string[];
  note?: string;
}

/** A suggestion that is no longer open: corrected by an edit, accepted as it is, or resolved another way (CM S29). */
export interface SettledSuggestion {
  id: string;
  key: string;
  outcome: "corrected" | "accepted" | "resolved";
  label: string | null;
  text: string;
  quote: string | null;
  version: number | null;
  actor: string | null;
  role: string | null;
  at: string;
  note: string | null;
  /** "Corrected in version 2", "Accepted as it is", "Resolved". */
  words: string;
}

export interface SuggestionState {
  suggestions: Suggestion[];
  settled: SettledSuggestion[];
}

export interface SettledSummary {
  corrected: number;
  accepted: number;
  resolved: number;
  notes: string[];
}

export interface PublishResult {
  document: ContentDocument;
  version: number;
  source_version: number;
  record?: string | null;
  /** Records citing this document; ``reconfirm``: its wording changed, so they are unavailable until reconfirmed (audit F01). */
  records_citing?: { id: string; title: string; reconfirm?: boolean }[];
}

const base = (id: string) => `/api/content/documents/${encodeURIComponent(id)}`;

export const getDocumentSummary = (space?: string | null) =>
  apiRequest<{
    documents: Record<string, { status: string; draft_updated_at: string | null; submitted_at: string | null }>;
    suggestions: Record<string, number>;
    suggestion_notes: Record<string, string[]>;
    settled?: Record<string, SettledSummary>;
  }>("GET", "/api/content/documents", undefined, space);
export const getContentDocument = (id: string) => apiRequest<ContentDocument>("GET", base(id));
export const saveDraft = (id: string, text: string, baseSha?: string) =>
  apiRequest<ContentDocument>("PUT", `${base(id)}/draft`, { text, base_sha: baseSha ?? null });
export const discardDraft = (id: string) => apiRequest<ContentDocument>("DELETE", `${base(id)}/draft`);
export const submitDraft = (id: string, note: string) => apiRequest<ContentDocument>("POST", `${base(id)}/submit`, { note });
export const returnDraft = (id: string, note = "") => apiRequest<ContentDocument>("POST", `${base(id)}/return`, { note });
export const publishDraft = (id: string, draftSha: string, note: string) =>
  apiRequest<PublishResult>("POST", `${base(id)}/publish`, { draft_sha: draftSha, note });
export const approveDocument = (id: string, expectedSha: string) =>
  apiRequest<ContentDocument>("POST", `${base(id)}/approve`, { expected_sha: expectedSha });
export const rejectDocument = (id: string, expectedSha: string) =>
  apiRequest<ContentDocument>("POST", `${base(id)}/reject`, { expected_sha: expectedSha });
export const getVersions = (id: string) => apiRequest<{ versions: VersionEntry[] }>("GET", `${base(id)}/versions`);
export interface VersionText extends Omit<VersionEntry, "chars" | "current"> {
  text: string;
}
// One kept version's words: what a citation points at (REF S18).
export const getVersion = (id: string, n: number, space?: string | null) =>
  apiRequest<VersionText>("GET", `${base(id)}/versions/${n}`, undefined, space);
export const restoreVersion = (id: string, n: number) => apiRequest<ContentDocument>("POST", `${base(id)}/versions/${n}/restore`);
export const getDiff = (id: string, from: string, to: string) =>
  apiRequest<{ ops: DiffOp[]; inserted_words: number; deleted_words: number }>(
    "GET",
    `${base(id)}/diff?base=${encodeURIComponent(from)}&target=${encodeURIComponent(to)}`,
  );
export const getComments = (id: string) => apiRequest<{ comments: Comment[] }>("GET", `${base(id)}/comments`);
export const addComment = (id: string, quote: string, text: string, prefix: string, suffix: string) =>
  apiRequest<Comment>("POST", `${base(id)}/comments`, { quote, text, prefix, suffix });
export const replyToComment = (commentId: string, text: string) =>
  apiRequest<Comment>("POST", `/api/content/comments/${commentId}/replies`, { text });
export const setCommentResolved = (commentId: string, resolved: boolean) =>
  apiRequest<Comment>("POST", `/api/content/comments/${commentId}/${resolved ? "resolve" : "reopen"}`);
export const deleteComment = (commentId: string) => apiRequest<{ deleted: string }>("DELETE", `/api/content/comments/${commentId}`);
export const getActivity = (id: string) => apiRequest<{ activity: ActivityEntry[] }>("GET", `${base(id)}/activity`);
export const getSuggestions = (id: string) => apiRequest<SuggestionState>("GET", `${base(id)}/suggestions`);
export const acceptSuggestion = (id: string, key: string, note: string) =>
  apiRequest<SuggestionState>("POST", `${base(id)}/suggestions/accept`, { key, note });
export const reopenSuggestion = (id: string, settledId: string) =>
  apiRequest<SuggestionState>("POST", `${base(id)}/suggestions/settled/${encodeURIComponent(settledId)}/reopen`);
export const updateDetails = (id: string, fields: Record<string, unknown>) =>
  apiRequest<ContentDocument>("PATCH", `${base(id)}/details`, { fields });
export async function uploadImage(file: File) {
  const form = new FormData();
  form.append("file", file);
  const saved = await apiUpload<{ name: string; url: string }>("/api/content/assets", form, documentSpace);
  // An image request cannot carry the space header: outside the Product Guide, its address names the space.
  return documentSpace && documentSpace !== "product-guide" ? { ...saved, url: `${saved.url}?space=${encodeURIComponent(documentSpace)}` } : saved;
}

export type DocumentPanel = "overview" | "comments" | "versions" | "activity" | "details";
const PANEL_HINT = "cm-open-panel";

/** Open a document from anywhere: the control panel shows it at #document:<source id>@<space>, optionally at a panel.
 *  A link without a space opens the document in the Product Guide. */
export function openDocument(sourceId: string, panel?: DocumentPanel, space?: string | null) {
  try {
    if (panel) sessionStorage.setItem(PANEL_HINT, `${sourceId}:${panel}`);
  } catch {
    // Storage may be unavailable; the document still opens, at its Overview.
  }
  // The link always names its space, so it opens there whichever space is active (KS S5).
  window.location.hash = `#document:${encodeURIComponent(sourceId)}@${space ?? getActiveSpace()}`;
}

/** The panel a document was asked to open at, read once. */
export function takePanelHint(sourceId: string): DocumentPanel | null {
  try {
    const hint = sessionStorage.getItem(PANEL_HINT);
    sessionStorage.removeItem(PANEL_HINT);
    if (hint?.startsWith(`${sourceId}:`)) return hint.slice(sourceId.length + 1) as DocumentPanel;
  } catch {
    // ignore
  }
  return null;
}

export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "";
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 45) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min${minutes === 1 ? "" : "s"} ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} hr${hours === 1 ? "" : "s"} ago`;
  const days = Math.round(hours / 24);
  if (days < 14) return `${days} day${days === 1 ? "" : "s"} ago`;
  return new Date(iso).toLocaleDateString();
}
