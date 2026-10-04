// The document workspace (CM S1): open any source at #document:<id>, edit it as a governed draft, and see its
// comments, suggestions, versions, activity and details beside it.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Editor } from "@tiptap/core";
import {
  acceptSuggestion,
  addComment,
  approveDocument,
  deleteComment,
  discardDraft,
  getActivity,
  getComments,
  getContentDocument,
  getDiff,
  getSuggestions,
  getVersions,
  openDocument,
  publishDraft,
  rejectDocument,
  reopenSuggestion,
  replyToComment,
  restoreVersion,
  returnDraft,
  saveDraft,
  setCommentResolved,
  submitDraft,
  takePanelHint,
  timeAgo,
  updateDetails,
  type ActivityEntry,
  type Comment,
  type ContentDocument,
  type DiffOp,
  type SettledSuggestion,
  type Suggestion,
  type VersionEntry,
  setDocumentSpace,
} from "./api";
import { DocumentEditor } from "./Editor";
import { replaceQuote, revealQuote, type Anchor } from "./extensions";
import { ActivityPanel, CommentsPanel, DetailsPanel, DiffView, OverviewPanel, VersionsPanel } from "./panels";
import { renameDocument } from "./library";
import { InlineTitle } from "./LibraryControls";
import "./content.css";

type Panel = "overview" | "comments" | "versions" | "activity" | "details";
type SaveState = "idle" | "unsaved" | "saving" | "saved" | "error";

const RAIL: { key: Panel; label: string; path: string }[] = [
  { key: "overview", label: "Overview", path: "M4 11l8-7 8 7v9H4zM10 20v-6h4v6" },
  { key: "comments", label: "Comments and suggestions", path: "M5 5h14v10H9l-4 4z" },
  { key: "versions", label: "Version history", path: "M4 12a8 8 0 1 0 2.3-5.6M4 4v4h4M12 8v4l3 2" },
  { key: "activity", label: "Recent activity", path: "M3 12h4l3-7 4 14 3-7h4" },
  { key: "details", label: "Details and scope", path: "M6 3h9l4 4v14H6zM14 3v5h5M9 13h7M9 17h7" },
];

const STATUS: Record<string, string> = { published: "Published", draft: "Draft", submitted: "Waiting for approval" };

export function DocumentPage({
  sourceId,
  space = null,
  backLabel,
  onBack,
}: {
  sourceId: string;
  space?: string | null;
  backLabel: string;
  onBack: () => void;
}) {
  // Every request for this document goes to its own space (KS S6), set before any of them is made.
  setDocumentSpace(space);
  useEffect(() => () => setDocumentSpace(null), []);
  const [doc, setDoc] = useState<ContentDocument | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<"viewing" | "editing">("viewing");
  const [panel, setPanel] = useState<Panel>("overview");
  const [comments, setComments] = useState<Comment[]>([]);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [settled, setSettled] = useState<SettledSuggestion[]>([]);
  const [versions, setVersions] = useState<VersionEntry[]>([]);
  const [activity, setActivity] = useState<ActivityEntry[]>([]);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [saveError, setSaveError] = useState<string | null>(null);
  const [compare, setCompare] = useState<{ n: number | null; title: string; ops: DiffOp[] } | null>(null);
  const [composer, setComposer] = useState<{ quote: string; prefix: string; suffix: string } | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [dialog, setDialog] = useState<"submit" | "publish" | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [editorKey, setEditorKey] = useState(0);
  const editorRef = useRef<Editor | null>(null);
  const pending = useRef<string | null>(null);
  const timer = useRef<number | null>(null);
  const docRef = useRef<ContentDocument | null>(null);
  const compareSeq = useRef(0);
  docRef.current = doc;

  const loadSide = useCallback(async () => {
    const [c, s, v, a] = await Promise.all([getComments(sourceId), getSuggestions(sourceId), getVersions(sourceId), getActivity(sourceId)]);
    setComments(c.comments);
    setSuggestions(s.suggestions);
    setSettled(s.settled ?? []);
    setVersions(v.versions);
    setActivity(a.activity);
  }, [sourceId]);

  useEffect(() => {
    let live = true;
    setDoc(null);
    setError(null);
    setMode("viewing");
    setPanel(takePanelHint(sourceId) ?? "overview");
    setCompare(null);
    setComposer(null);
    setNotice(null);
    setSaveState("idle");
    getContentDocument(sourceId)
      .then((d) => {
        if (!live) return;
        setDoc(d);
        setEditorKey((k) => k + 1);
        return loadSide();
      })
      .catch((e) => live && setError(e instanceof Error ? e.message : "Could not open the document."));
    return () => {
      live = false;
    };
  }, [sourceId, loadSide]);

  // Unsaved edits are not lost by leaving the page.
  useEffect(() => {
    const onLeave = (e: BeforeUnloadEvent) => {
      if (pending.current !== null) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", onLeave);
    return () => window.removeEventListener("beforeunload", onLeave);
  }, []);

  const flush = useCallback(async () => {
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = null;
    const text = pending.current;
    const current = docRef.current;
    if (text === null || !current) return;
    pending.current = null;
    setSaveState("saving");
    try {
      const saved = await saveDraft(sourceId, text, current.draft?.base_sha ?? current.published.sha);
      setDoc(saved);
      setSaveState(pending.current === null ? "saved" : "unsaved");
      setSaveError(null);
      const [c, a] = await Promise.all([getComments(sourceId), getActivity(sourceId)]);
      setComments(c.comments);
      setActivity(a.activity);
    } catch (e) {
      pending.current = pending.current ?? text;
      setSaveState("error");
      setSaveError(e instanceof Error ? e.message : "Could not save the draft");
    }
  }, [sourceId]);

  function onChange(markdown: string) {
    pending.current = markdown;
    setSaveState("unsaved");
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => void flush(), 1200);
  }

  useEffect(() => () => {
    if (timer.current) window.clearTimeout(timer.current);
    if (pending.current !== null) void flush();
  }, [flush]);

  const anchors: Anchor[] = useMemo(
    () => [
      ...comments
        .filter((c) => c.status === "open")
        .map((c) => ({ id: c.id, quote: c.quote, prefix: c.prefix, suffix: c.suffix, kind: "comment" as const, active: c.id === activeId })),
      ...suggestions
        .filter((s) => s.quote && !s.answer)
        .map((s) => ({ id: s.key, quote: s.quote as string, kind: "suggestion" as const, active: s.key === activeId })),
    ],
    [comments, suggestions, activeId],
  );

  function reveal(id: string) {
    setActiveId(id);
    const editor = editorRef.current;
    const anchor = anchors.find((a) => a.id === id);
    if (editor && anchor && !compare) revealQuote(editor, anchor.quote, anchor.prefix, anchor.suffix);
  }

  function activate(id: string) {
    setActiveId(id);
    setPanel("comments");
    window.setTimeout(() => document.getElementById(`cm-thread-${id}`)?.scrollIntoView({ block: "nearest", behavior: "smooth" }), 50);
  }

  async function run<T>(fn: () => Promise<T>): Promise<T | undefined> {
    setBusy(true);
    setNotice(null);
    try {
      return await fn();
    } catch (e) {
      setNotice(e instanceof Error ? e.message : "That did not work");
      return undefined;
    } finally {
      setBusy(false);
    }
  }

  async function refreshAll(next?: ContentDocument, remount = false) {
    const d = next ?? (await getContentDocument(sourceId));
    setDoc(d);
    if (remount) {
      setEditorKey((k) => k + 1);
      setSaveState("idle");
    }
    await loadSide();
  }

  async function submit() {
    await flush();
    const d = await run(() => submitDraft(sourceId, note));
    if (d) {
      setDialog(null);
      setNote("");
      await refreshAll(d);
    }
  }

  async function publish() {
    await flush();
    const current = docRef.current;
    if (!current?.draft) return;
    const result = await run(() => publishDraft(sourceId, current.draft!.sha, note));
    if (!result) return;
    setDialog(null);
    setNote("");
    setMode("viewing");
    setCompare(null);
    await refreshAll(result.document, true);
    const citing = result.records_citing ?? [];
    const reconfirm = citing.filter((c) => c.reconfirm);
    const kept = citing.filter((c) => !c.reconfirm);
    setNotice(
      `Version ${result.source_version} is live for answers and Tibi.` +
        (reconfirm.length
          ? ` Tibi stops using ${reconfirm.length === 1 ? "the record that cites" : `the ${reconfirm.length} records that cite`} it until you confirm ${reconfirm.length === 1 ? "it still holds" : "each still holds"} (Tibi Knowledge, Reconfirm): ${reconfirm.map((c) => c.title).join("; ")}.`
          : "") +
        (kept.length ? ` Only the formatting changed, so ${kept.map((c) => c.title).join("; ")} ${kept.length === 1 ? "keeps its" : "keep their"} approval.` : ""),
    );
  }

  async function discard() {
    if (!window.confirm("Discard the draft? The published version stays as it is.")) return;
    if (timer.current) window.clearTimeout(timer.current);
    pending.current = null;
    const d = await run(() => discardDraft(sourceId));
    if (d) {
      setSaveState("idle");
      setCompare(null);
      await refreshAll(d, true);
    }
  }

  /** Approve or reject the published version just read, without editing it. */
  async function decide(approve: boolean) {
    const current = docRef.current;
    if (!current) return;
    const d = await run(() => (approve ? approveDocument : rejectDocument)(sourceId, current.published.sha));
    if (!d) return;
    await refreshAll(d);
    setNotice(
      approve
        ? d.record
          ? `Approved. Tibi uses “${d.record.title}” in answers now.`
          : "Approved. Answers can use this document now."
        : d.record
          ? `Rejected. Tibi no longer uses “${d.record.title}”.`
          : "Rejected. Answers no longer use this document.",
    );
  }

  /** A new title. For a record this writes its heading as a new version, so the editor starts again from it. */
  async function rename(title: string): Promise<boolean> {
    await flush();
    const d = await run(() => renameDocument(sourceId, title));
    if (!d) return false;
    await refreshAll(d, true);
    setNotice(d.title_from_heading ? `Renamed. The heading is a new version; approval is ${d.source.approval_status}, as before.` : "Renamed.");
    return true;
  }

  async function returnToDraft() {
    const current = docRef.current;
    if (!current?.draft) return;
    const d = await run(() => returnDraft(sourceId, current.draft!.sha));  // the draft on screen (REF S23, S8)
    if (d) await refreshAll(d);
  }

  async function reviewChanges() {
    await flush();
    const seq = ++compareSeq.current;
    const ops = await run(() => getDiff(sourceId, "published", "draft"));
    if (ops && seq === compareSeq.current) setCompare({ n: null, title: "Changes in the draft, compared with the published version", ops: ops.ops });
  }

  async function compareVersion(n: number) {
    await flush();
    const target = docRef.current?.draft ? "draft" : "published";
    const seq = ++compareSeq.current;
    const ops = await run(() => getDiff(sourceId, String(n), target));
    if (ops && seq === compareSeq.current) setCompare({ n, title: `Version ${n} compared with ${target === "draft" ? "the draft" : "the current text"}`, ops: ops.ops });
  }

  async function restore(n: number) {
    await flush();
    const d = await run(() => restoreVersion(sourceId, n));
    if (d) {
      setCompare(null);
      setMode("editing");
      setNotice(`Version ${n} is now the draft. Nothing is live until it is approved.`);
      await refreshAll(d, true);
    }
  }

  function download() {
    const current = docRef.current;
    if (!current) return;
    const text = pending.current ?? current.draft?.text ?? current.published.text;
    const blob = new Blob([text], { type: "text/markdown;charset=utf-8" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `${current.source.title.replace(/[^\w\- ]+/g, "").trim() || "document"}.md`;
    link.click();
    URL.revokeObjectURL(link.href);
  }

  function applyFix(s: Suggestion) {
    const editor = editorRef.current;
    if (!editor || !s.fix) return;
    if (!replaceQuote(editor, s.fix.find, s.fix.replace, { avoidHeadings: true })) setNotice(`"${s.fix.find}" is no longer in the document.`);
  }

  if (error) {
    return (
      <div className="view-stack">
        <button type="button" className="cm-back" onClick={onBack}>
          ← {backLabel}
        </button>
        <div className="empty-card">
          <b>This document could not be opened</b>
          <span>{error}</span>
        </div>
      </div>
    );
  }
  if (!doc) return <div className="cm-canvas-loading">Opening the document…</div>;

  const editable = doc.source.editable && mode === "editing" && !compare;
  const saveText =
    saveState === "saving"
      ? "Saving…"
      : saveState === "unsaved"
        ? "Unsaved changes"
        : saveState === "saved"
          ? "Draft saved just now"
          : saveState === "error"
            ? `Not saved: ${saveError}`
            : doc.draft
              ? `Draft saved ${timeAgo(doc.draft.updated_at)}`
              : `Published v${doc.source.version}`;
  const openSuggestions = suggestions.filter((s) => !s.answer).length;

  return (
    <div className="cm-workspace">
      <div className="cm-header">
        <div className="cm-breadcrumb">
          <button type="button" className="cm-back" onClick={onBack}>
            {backLabel}
          </button>
          <span className="cm-crumb-sep">/</span>
          <InlineTitle value={doc.source.title} onSave={rename}>
            <b className="cm-title" title={doc.source.title}>
              {doc.source.title}
            </b>
          </InlineTitle>
          <span className={`cm-save cm-save--${saveState}`}>{saveText}</span>
          <span className={`status-pill cm-status cm-status--${doc.status}`}>{STATUS[doc.status]}</span>
        </div>
        <div className="cm-header-actions">
          <span className="segmented-control" role="group" aria-label="Mode">
            <button type="button" className={mode === "viewing" ? "is-active" : ""} onClick={() => setMode("viewing")}>
              Viewing
            </button>
            <button
              type="button"
              className={mode === "editing" ? "is-active" : ""}
              disabled={!doc.source.editable}
              title={doc.source.editable ? undefined : `${doc.source.format.toUpperCase()} documents are read-only here`}
              onClick={() => {
                setCompare(null);
                setMode("editing");
              }}
            >
              Editing
            </button>
          </span>
          {doc.status === "published" && doc.source.approval_status !== "approved" ? (
            <>
              {doc.source.approval_status !== "rejected" ? (
                <button type="button" className="reject-button" disabled={busy} onClick={() => void decide(false)}>
                  Reject
                </button>
              ) : null}
              <button
                type="button"
                className="approve-button"
                disabled={busy}
                title={doc.record ? "Approve this version; Tibi starts using the record" : "Approve this version for answers"}
                onClick={() => void decide(true)}
              >
                Approve
              </button>
            </>
          ) : null}
          {doc.status === "draft" ? (
            <>
              <button type="button" className="text-button" disabled={busy} onClick={() => void discard()}>
                Discard draft
              </button>
              <button type="button" className="secondary-button" disabled={busy} onClick={() => void reviewChanges()}>
                Review changes
              </button>
              <button type="button" className="primary-button" disabled={busy || saveState === "saving"} onClick={() => setDialog("submit")}>
                Submit for approval
              </button>
            </>
          ) : null}
          {doc.status === "submitted" ? (
            <>
              <button type="button" className="text-button" disabled={busy} onClick={() => void returnToDraft()}>
                Return to draft
              </button>
              <button type="button" className="secondary-button" disabled={busy} onClick={() => void reviewChanges()}>
                Review changes
              </button>
              <button type="button" className="approve-button" disabled={busy} onClick={() => setDialog("publish")}>
                Approve and publish
              </button>
            </>
          ) : null}
        </div>
      </div>
      {doc.draft?.stale ? (
        <div className="cm-banner cm-banner--warn">
          The published document changed after this draft was started. Compare the versions and restore what you need before approving.
        </div>
      ) : null}
      {doc.status === "submitted" && doc.submitted ? (
        <div className="cm-banner">
          Submitted by {doc.submitted.by} {timeAgo(doc.submitted.at)}
          {doc.submitted.note ? `: “${doc.submitted.note}”` : "."} Review the changes, then approve and publish, or return it to draft.
        </div>
      ) : null}
      {notice ? (
        <div className="cm-banner cm-banner--notice">
          <span>{notice}</span>
          <button type="button" className="cm-icon-button" aria-label="Dismiss" onClick={() => setNotice(null)}>
            ×
          </button>
        </div>
      ) : null}
      <div className="cm-body">
        <div className="cm-canvas">
          {compare ? (
            <DiffView ops={compare.ops} title={compare.title} onClose={() => setCompare(null)} />
          ) : (
            <DocumentEditor
              key={editorKey}
              markdown={doc.draft?.text ?? doc.published.text}
              editable={editable}
              anchors={anchors}
              onChange={onChange}
              onActivateAnchor={activate}
              onComment={(a) => {
                setComposer(a);
                setPanel("comments");
              }}
              onReady={(e) => {
                editorRef.current = e;
              }}
              onDownload={download}
            />
          )}
        </div>
        <aside className="cm-side" aria-label="Document panels">
          <div className="cm-side-head">
            <b>{RAIL.find((r) => r.key === panel)?.label}</b>
          </div>
          {panel === "overview" ? <OverviewPanel doc={doc} suggestions={suggestions} settled={settled} onShow={setPanel} /> : null}
          {panel === "comments" ? (
            <CommentsPanel
              comments={comments}
              suggestions={suggestions}
              settled={settled}
              draftText={doc.draft?.text ?? null}
              activeId={activeId}
              composer={composer}
              editable={editable}
              onReveal={reveal}
              onAdd={async (text) => {
                if (!composer) return;
                const added = await run(() => addComment(sourceId, composer.quote, text, composer.prefix, composer.suffix));
                if (added) {
                  setComposer(null);
                  setActiveId(added.id);
                  await refreshAll();
                }
              }}
              onCancelComposer={() => setComposer(null)}
              onReply={async (id, text) => {
                if (await run(() => replyToComment(id, text))) await loadSide();
              }}
              onResolve={async (id, resolved) => {
                if (await run(() => setCommentResolved(id, resolved))) await refreshAll();
              }}
              onDelete={async (id) => {
                if (window.confirm("Delete this comment and its replies?") && (await run(() => deleteComment(id)))) await refreshAll();
              }}
              onApplyFix={applyFix}
              onAccept={async (s, reason) => {
                const state = await run(() => acceptSuggestion(sourceId, s.key, reason));
                if (!state) return;
                setSuggestions(state.suggestions);
                setSettled(state.settled);
                setNotice(`Accepted as it is. Governance and Tibi no longer raise “${s.quote ?? s.label}” for this document; Reopen undoes it.`);
                void loadSide();
              }}
              onReopen={async (id) => {
                const state = await run(() => reopenSuggestion(sourceId, id));
                if (!state) return;
                setSuggestions(state.suggestions);
                setSettled(state.settled);
                void loadSide();
              }}
            />
          ) : null}
          {panel === "versions" ? (
            <VersionsPanel
              versions={versions}
              hasDraft={Boolean(doc.draft)}
              editable={doc.source.editable}
              comparing={compare?.n ?? null}
              onCompare={(n) => void compareVersion(n)}
              onRestore={(n) => void restore(n)}
            />
          ) : null}
          {panel === "activity" ? <ActivityPanel activity={activity} /> : null}
          {panel === "details" ? (
            <DetailsPanel
              key={`${doc.source.id}-${doc.source.version}-${doc.source.title}`}
              doc={doc}
              onOpen={openDocument}
              onRename={rename}
              onMoved={(message) => {
                setNotice(message);
                void loadSide();
              }}
              onSave={async (fields) => {
                const d = await run(() => updateDetails(sourceId, fields));
                if (d) {
                  await refreshAll(d);
                  setNotice("Details saved.");
                }
              }}
            />
          ) : null}
        </aside>
        <nav className="cm-rail" aria-label="Panels">
          {RAIL.map((r) => (
            <button
              key={r.key}
              type="button"
              className={`cm-rail-button${panel === r.key ? " cm-rail-button--active" : ""}`}
              title={r.label}
              aria-label={r.label}
              onClick={() => setPanel(r.key)}
            >
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d={r.path} />
              </svg>
              {r.key === "comments" && doc.comments.open + openSuggestions ? <span className="cm-rail-badge">{doc.comments.open + openSuggestions}</span> : null}
            </button>
          ))}
        </nav>
      </div>
      {dialog ? (
        <div className="cm-dialog-backdrop" role="presentation" onMouseDown={() => !busy && setDialog(null)}>
          <div className="cm-dialog" role="dialog" aria-modal="true" onMouseDown={(e) => e.stopPropagation()}>
            {dialog === "submit" ? (
              <>
                <h2>Submit for approval</h2>
                <p className="muted-text">The draft waits for approval; the published version stays live until then.</p>
              </>
            ) : (
              <>
                <h2>Approve and publish</h2>
                <p className="muted-text">
                  This makes the draft version {doc.source.version + 1} of “{doc.source.title}”. It is re-ingested and approved, and answers and
                  Tibi use it straight away.
                </p>
                {doc.record ? <p className="muted-text">The Tibi record “{doc.record.title}” is updated with it and enabled.</p> : null}
                {doc.cited_by?.length ? (
                  <p className="cm-inline-warn">
                    {doc.cited_by.length} record{doc.cited_by.length === 1 ? " cites" : "s cite"} this document: {doc.cited_by.map((c) => c.title).join("; ")}. They
                    will follow the new version.
                  </p>
                ) : null}
              </>
            )}
            <label className="cm-form">
              Note (optional)
              <textarea rows={3} value={note} placeholder={dialog === "submit" ? "What changed and why" : "Why this is approved"} onChange={(e) => setNote(e.target.value)} />
            </label>
            <div className="cm-thread-actions">
              <button type="button" className="secondary-button" disabled={busy} onClick={() => setDialog(null)}>
                Cancel
              </button>
              <button
                type="button"
                className={dialog === "submit" ? "primary-button" : "approve-button"}
                disabled={busy}
                onClick={() => void (dialog === "submit" ? submit() : publish())}
              >
                {busy ? "Working…" : dialog === "submit" ? "Submit" : "Approve and publish"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
