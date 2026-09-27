import { Fragment, useEffect, useMemo, useState } from "react";
import { openDocument } from "./content/api";
import { getLibrary, type Library } from "./content/library";
import { FolderIcon } from "./content/LibraryControls";
import {
  confirmTibiFact,
  draftTibiSpoken,
  getTibiContributions,
  getTibiOntology,
  getTibiRecords,
  getTibiSource,
  getTibiSpoken,
  proposeTibiClaim,
  resolveTibiRecord,
  reviewTibiRecord,
  reviewTibiSpoken,
  type TibiContribution,
  type TibiOntology,
  type TibiRecord,
  type TibiSpokenVariant,
} from "./api";

interface Loaded {
  records: TibiRecord[];
  spoken: TibiSpokenVariant[];
  turns: TibiContribution[];
  ontology: TibiOntology;
  library: Library | null;
}

type Tab = "product" | "conversation" | "spoken" | "contributions" | "ontology";
type Filter = "all" | "waiting" | "enabled" | "excluded";
type Act = (fn: () => Promise<unknown>, done?: string) => Promise<void>;

/** Whether Tibi may use a record, in a word and a tone (CM S33). */
function recordUse(row: TibiRecord): { key: Exclude<Filter, "all">; label: string; tone: string; why?: string } {
  if (row.eligible) return { key: "enabled", label: "Enabled", tone: "status-pill--good" };
  if (row.approval === "rejected") return { key: "excluded", label: "Excluded", tone: "status-pill--danger" };
  if (row.evidence_changed?.length)
    return {
      key: "waiting",
      label: "Reconfirm",
      tone: "status-pill--warn",
      why: `The evidence it cites changed since you enabled it (${row.evidence_changed.map((e) => e.title).join("; ")}). Check it still holds, then Enable it again.`,
    };
  if (row.approval === "approved")
    return { key: "waiting", label: "Unavailable", tone: "status-pill--warn", why: row.review_block ?? "Its wording or source changed since it was enabled." };
  return { key: "waiting", label: "To review", tone: "status-pill--blue" };
}

/** The spoken wording Tibi may use for a record: the current, not rejected, variant. */
function spokenFor(spoken: TibiSpokenVariant[], id: string) {
  return spoken.find((v) => v.record_id === id && v.current && v.status !== "rejected");
}

/** Each document's library group, as a path of titles, and the order the library shows them in (CM S33). */
function groupsOf(library: Library | null) {
  const groups = new Map((library?.groups ?? []).map((g) => [g.id, g]));
  const placements = library?.placements ?? {};
  const path = (id: string): string[] => {
    const titles: string[] = [];
    const seen = new Set<string>();
    for (let at: string | null = `group:${id}`; at?.startsWith("group:") && !seen.has(at); ) {
      seen.add(at);
      const g = groups.get(at.slice(6));
      if (!g) break;
      titles.unshift(g.title);
      at = g.parent;
    }
    return titles;
  };
  /** The nearest group above a document, climbing through documents it sits under. */
  const groupOfSource = (sourceId: string): string | null => {
    const seen = new Set<string>();
    for (let at = placements[sourceId]?.parent ?? null; at && !seen.has(at); ) {
      seen.add(at);
      if (at.startsWith("group:")) return groups.has(at.slice(6)) ? at.slice(6) : null;
      at = placements[at.slice(7)]?.parent ?? null;
    }
    return null;
  };
  // Depth-first order of the groups, as the Governance page shows them.
  const order = new Map<string, number>();
  const visit = (parent: string | null) =>
    [...groups.values()]
      .filter((g) => g.parent === parent)
      .sort((a, b) => a.position - b.position || a.title.localeCompare(b.title))
      .forEach((g) => {
        order.set(g.id, order.size);
        visit(`group:${g.id}`);
      });
  visit(null);
  return { path, groupOfSource, order, position: (sourceId: string) => placements[sourceId]?.position ?? Number.MAX_SAFE_INTEGER };
}

/** What Tibi may say and how it chats: every record, spoken answer and contribution is enabled here by the Human. */
export function TibiKnowledgePage({ focus }: { focus?: string }) {
  const [data, setData] = useState<Loaded | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [drafting, setDrafting] = useState(false);
  const [tab, setTab] = useState<Tab>("product");
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState<Set<string>>(new Set());

  async function load() {
    try {
      const [records, spoken, contributions, ontology, library] = await Promise.all([
        getTibiRecords(),
        getTibiSpoken(),
        // Contributions live in the Tibi service: the rest of the page works while it is stopped.
        getTibiContributions().catch(() => ({ turns: [] })),
        getTibiOntology(),
        getLibrary().catch(() => null),
      ]);
      setData({ records: records.records, spoken: spoken.variants, turns: contributions.turns, ontology, library });
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load Tibi's knowledge.");
    }
  }

  useEffect(() => {
    void load();
  }, []);

  // A link from Tibi ("#tibi-knowledge:overview") opens the record's tab with its row open.
  useEffect(() => {
    if (!data || !focus) return;
    const row = data.records.find((r) => r.id === focus);
    if (!row) return;
    setTab(row.kind === "conversation" ? "conversation" : "product");
    setFilter("all");
    setQuery("");
    setOpen((current) => new Set(current).add(focus));
    window.setTimeout(() => document.getElementById(`tibi-record-${focus}`)?.scrollIntoView({ behavior: "smooth", block: "center" }), 60);
  }, [data, focus]);

  const act: Act = async (fn, done) => {
    try {
      await fn();
      setMessage(done ?? null);
      setError(null);
      await load();
    } catch (e) {
      setMessage(null);
      setError(e instanceof Error ? e.message : "The request failed.");
    }
  };

  async function draft() {
    setDrafting(true);
    await act(async () => {
      const result = await draftTibiSpoken();
      setMessage(
        `${result.drafted.length} drafted for review` +
          (result.rejected.length ? `; ${result.rejected.length} drafts went beyond their record and were discarded` : "") +
          ".",
      );
    });
    setDrafting(false);
  }

  if (!data) {
    return (
      <div className="view-stack">
        <Intro />
        {error ? <p className="muted-text" style={{ color: "var(--red)" }}>{error}</p> : <p className="muted-text">Loading…</p>}
      </div>
    );
  }

  const product = data.records.filter((r) => r.kind !== "conversation");
  const conversation = data.records.filter((r) => r.kind === "conversation");
  const titles = Object.fromEntries(data.records.map((r) => [r.id, r.title]));
  const enabled = data.records.filter((r) => r.eligible).length;
  const waiting = data.records.filter((r) => recordUse(r).key === "waiting");
  const changed = waiting.filter((r) => r.approval === "approved").length;
  const spoken = data.spoken.filter((v) => v.status !== "rejected" && v.current);
  const spokenWaiting = spoken.filter((v) => v.status === "pending").length;
  const waitingIn = (rows: TibiRecord[]) => rows.filter((r) => recordUse(r).key === "waiting").length;

  const tabs: { key: Tab; label: string; count?: number; attention?: number }[] = [
    { key: "product", label: "Product records", count: product.length, attention: waitingIn(product) },
    { key: "conversation", label: "Conversation style", count: conversation.length, attention: waitingIn(conversation) },
    { key: "spoken", label: "Spoken answers", count: spoken.length, attention: spokenWaiting },
    { key: "contributions", label: "Interview contributions", count: data.turns.length, attention: data.turns.length },
    {
      key: "ontology",
      label: "Product ontology",
      count: data.ontology.objects.length,
      attention: data.ontology.unusable.filter((u) => u.changed?.length).length,
    },
  ];

  function showWaiting() {
    setTab(waitingIn(product) || !waitingIn(conversation) ? "product" : "conversation");
    setFilter("waiting");
    setQuery("");
  }

  return (
    <div className="view-stack">
      <Intro />

      <div className="panel tibi-review">
        <div className="tibi-review-head">
          <div>
            <h2>What Tibi may say</h2>
            <p className="muted-text">
              Tibi answers product questions only from enabled records, and uses approved spoken wording when it has it. Enabling permits
              internal rehearsal only; it is not approval for customer commitments.
            </p>
          </div>
        </div>
        <div className="tibi-tiles">
          <Tile label="Records Tibi can use" value={enabled} tone={enabled ? "good" : "neutral"} text={`of ${data.records.length} records enabled for internal rehearsal`} />
          <Tile
            label="Waiting for review"
            value={waiting.length}
            tone={waiting.length ? "amber" : "good"}
            text={waiting.length ? "Records to enable or exclude" : "Nothing waiting"}
            meta={changed ? `${changed} changed since ${changed === 1 ? "it was" : "they were"} enabled` : undefined}
          >
            {waiting.length ? (
              <button type="button" className="secondary-button tibi-tile-action" onClick={showWaiting}>
                Show them
              </button>
            ) : null}
          </Tile>
          <Tile
            label="Spoken answers"
            value={spoken.filter((v) => v.usable).length}
            tone="purple"
            text="approved for the live voice"
            meta={spokenWaiting ? `${spokenWaiting} draft${spokenWaiting === 1 ? "" : "s"} waiting for approval` : "No drafts waiting"}
          >
            <button type="button" className="secondary-button tibi-tile-action" disabled={drafting} onClick={() => void draft()}>
              {drafting ? "Drafting with the local model…" : "Draft spoken wording"}
            </button>
          </Tile>
          <Tile
            label="Interview contributions"
            value={data.turns.length}
            tone={data.turns.length ? "amber" : "neutral"}
            text={data.turns.length ? "Captured in product interviews, to check" : "None captured yet"}
            meta={data.turns.length ? undefined : "Start a product interview in Talk with Tibi"}
          />
        </div>
      </div>

      <div className="panel tk-panel">
        <div className="tk-tabs" role="tablist" aria-label="Tibi knowledge sections">
          {tabs.map((t) => (
            <button
              key={t.key}
              type="button"
              role="tab"
              aria-selected={tab === t.key}
              className={`tk-tab${tab === t.key ? " is-active" : ""}`}
              onClick={() => {
                setTab(t.key);
                setMessage(null);
              }}
            >
              {t.label}
              {t.count !== undefined ? <span className="tk-tab-count">{t.count}</span> : null}
              {t.attention ? <span className="tk-tab-dot" title={`${t.attention} waiting`} /> : null}
            </button>
          ))}
        </div>
        {error ? <p className="cm-inline-error">{error}</p> : null}
        {message ? <p className="tk-message">{message}</p> : null}

        {tab === "product" || tab === "conversation" ? (
          <RecordTable
            key={tab}
            rows={tab === "product" ? product : conversation}
            conversation={tab === "conversation"}
            spoken={data.spoken}
            library={data.library}
            filter={filter}
            setFilter={setFilter}
            query={query}
            setQuery={setQuery}
            open={open}
            setOpen={setOpen}
            act={act}
            note={
              tab === "product"
                ? "Inspect the wording and its supporting originals before enabling a record. Grouped as in the Governance Review library."
                : "How Tibi chats: its personality, small talk, everyday topics, the topics it keeps out of, and the purpose of a sales conversation. These records guide conversation only; they are never product evidence."
            }
          />
        ) : null}

        {tab === "spoken" ? <SpokenTable spoken={spoken} titles={titles} act={act} /> : null}

        {tab === "contributions" ? (
          <div className="tk-section">
            <p className="muted-text">
              Check the captured wording, including availability and qualifications. Save a proposal first; enable it separately under
              Product records after reviewing related records.
            </p>
            {data.turns.length ? (
              <div className="tk-contributions">
                {data.turns.map((turn) => (
                  <ContributionCard
                    key={`${turn.session_id}-${turn.id}`}
                    turn={turn}
                    existing={data.records.find((r) => r.provenance?.session_id === turn.session_id && r.provenance?.turn_id === turn.id)}
                    onSave={(body) => act(() => proposeTibiClaim(body), "Proposal saved for review.")}
                  />
                ))}
              </div>
            ) : (
              <div className="empty-card">
                <b>No interview contributions yet</b>
                <span>Start a product interview in Talk with Tibi; what people contribute appears here to check.</span>
              </div>
            )}
          </div>
        ) : null}

        {tab === "ontology" ? <Ontology ontology={data.ontology} titles={titles} act={act} /> : null}
      </div>
    </div>
  );
}

function Intro() {
  return (
    <div className="page-intro">
      <h1>Tibi knowledge</h1>
      <p>
        What Tibi may say and how it chats. Every record, spoken answer and interview contribution is enabled here by a person; nothing
        Tibi hears is approved automatically.
      </p>
    </div>
  );
}

function Tile({
  label,
  value,
  tone,
  text,
  meta,
  children,
}: {
  label: string;
  value: number;
  tone: "good" | "amber" | "purple" | "red" | "neutral";
  text: string;
  meta?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className={`tibi-tile tibi-tile--${tone}`}>
      <span className="tibi-tile-label">{label}</span>
      <b className="tibi-tile-value">{value}</b>
      <span className="tibi-tile-text">{text}</span>
      {meta ? <span className="tibi-tile-meta">{meta}</span> : null}
      {children}
    </div>
  );
}

/** Records in a grouped table: one row each, with the full wording, originals and decisions when opened (CM S33). */
function RecordTable({
  rows,
  conversation,
  spoken,
  library,
  filter,
  setFilter,
  query,
  setQuery,
  open,
  setOpen,
  act,
  note,
}: {
  rows: TibiRecord[];
  conversation: boolean;
  spoken: TibiSpokenVariant[];
  library: Library | null;
  filter: Filter;
  setFilter: (f: Filter) => void;
  query: string;
  setQuery: (q: string) => void;
  open: Set<string>;
  setOpen: (fn: (s: Set<string>) => Set<string>) => void;
  act: Act;
  note: string;
}) {
  const [closedGroups, setClosedGroups] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState<string | null>(null);
  const groups = useMemo(() => groupsOf(library), [library]);
  const counts = {
    all: rows.length,
    waiting: rows.filter((r) => recordUse(r).key === "waiting").length,
    enabled: rows.filter((r) => recordUse(r).key === "enabled").length,
    excluded: rows.filter((r) => recordUse(r).key === "excluded").length,
  };
  const words = query.trim().toLowerCase();
  const shown = rows.filter(
    (r) =>
      (filter === "all" || recordUse(r).key === filter) &&
      (!words || `${r.title} ${r.text} ${(r.topics ?? []).join(" ")}`.toLowerCase().includes(words)),
  );
  const sections = useMemo(() => {
    const byGroup = new Map<string, TibiRecord[]>();
    for (const row of shown) {
      const g = groups.groupOfSource(row.source_id) ?? "";
      byGroup.set(g, [...(byGroup.get(g) ?? []), row]);
    }
    return [...byGroup.entries()]
      .sort(([a], [b]) => (a ? groups.order.get(a) ?? 9999 : 10000) - (b ? groups.order.get(b) ?? 9999 : 10000))
      .map(([id, list]) => ({
        id,
        title: id ? groups.path(id).join(" › ") : "Not in a group",
        rows: list.sort((a, b) => groups.position(a.source_id) - groups.position(b.source_id) || a.title.localeCompare(b.title)),
      }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shown.map((r) => r.id).join(), groups]);

  async function decide(row: TibiRecord, approve: boolean) {
    setBusy(row.id);
    await act(() => reviewTibiRecord(row.id, row.sha256, approve), `${approve ? "Enabled" : "Excluded"} “${row.title}”.`);
    setBusy(null);
  }

  const toggleRow = (id: string) =>
    setOpen((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  const columns = conversation ? 4 : 5;

  return (
    <div className="tk-section">
      <p className="muted-text">{note}</p>
      <div className="tk-toolbar">
        <span className="segmented-control" role="group" aria-label="Show records">
          {(["all", "waiting", "enabled", "excluded"] as const).map((f) => (
            <button key={f} type="button" className={filter === f ? "is-active" : ""} onClick={() => setFilter(f)}>
              {{ all: "All", waiting: "Waiting", enabled: "Enabled", excluded: "Excluded" }[f]} ({counts[f]})
            </button>
          ))}
        </span>
        <input
          className="search-input tk-search"
          type="search"
          value={query}
          placeholder="Search titles, wording and topics"
          aria-label="Search records"
          onChange={(e) => setQuery(e.target.value)}
        />
        <span className="tk-toolbar-end">
          <button type="button" className="text-button" onClick={() => setOpen(() => new Set(shown.map((r) => r.id)))}>
            Open all
          </button>
          <button type="button" className="text-button" onClick={() => setOpen(() => new Set())}>
            Close all
          </button>
        </span>
      </div>
      {shown.length === 0 ? (
        <div className="empty-card">
          <b>No records match</b>
          <span>Clear the search or choose All.</span>
        </div>
      ) : (
        <div className="table-frame">
          <table className="data-table library-table tk-table">
            <thead>
              <tr>
                <th>Record</th>
                <th>Availability</th>
                <th>Tibi use</th>
                {conversation ? null : <th>Spoken</th>}
                <th />
              </tr>
            </thead>
            <tbody>
              {sections.map((section) => {
                const closed = closedGroups.has(section.id);
                const usable = section.rows.filter((r) => r.eligible).length;
                return (
                  <Fragment key={section.id || "none"}>
                    <tr className="library-group-row">
                      <td colSpan={columns}>
                        <div className="tree-cell">
                          <button
                            type="button"
                            className={`tree-toggle${closed ? "" : " is-open"}`}
                            aria-expanded={!closed}
                            aria-label={`${closed ? "Expand" : "Collapse"} ${section.title}`}
                            onClick={() =>
                              setClosedGroups((current) => {
                                const next = new Set(current);
                                if (next.has(section.id)) next.delete(section.id);
                                else next.add(section.id);
                                return next;
                              })
                            }
                          >
                            ›
                          </button>
                          <span className="tree-folder">
                            <FolderIcon open={!closed} />
                          </span>
                          <b className="tk-group-title">{section.title}</b>
                          <span className="tree-count">
                            {usable} of {section.rows.length} enabled
                          </span>
                        </div>
                      </td>
                    </tr>
                    {closed
                      ? null
                      : section.rows.map((row) => {
                          const state = recordUse(row);
                          const variant = spokenFor(spoken, row.id);
                          const expanded = open.has(row.id);
                          return (
                            <Fragment key={row.id}>
                              <tr id={`tibi-record-${row.id}`} className={`tk-row${expanded ? " is-open" : ""}`}>
                                <td>
                                  <div className="tree-cell" style={{ paddingLeft: 22 }}>
                                    <button
                                      type="button"
                                      className={`tree-toggle${expanded ? " is-open" : ""}`}
                                      aria-expanded={expanded}
                                      aria-label={`${expanded ? "Close" : "Open"} ${row.title}`}
                                      onClick={() => toggleRow(row.id)}
                                    >
                                      ›
                                    </button>
                                    <button type="button" className="tk-title" onClick={() => toggleRow(row.id)}>
                                      {row.title}
                                    </button>
                                    {row.provenance ? <span className="status-pill status-pill--purple tree-pill">contributed</span> : null}
                                    {row.disputed ? <span className="status-pill status-pill--danger tree-pill">disputed</span> : null}
                                  </div>
                                  {expanded ? null : <p className="tk-snippet">{row.text}</p>}
                                </td>
                                <td>
                                  <span className={`tk-availability tk-availability--${row.status}`}>{row.status}</span>
                                </td>
                                <td>
                                  <span className={`status-pill ${state.tone}`} title={state.why}>
                                    {state.label}
                                  </span>
                                </td>
                                {conversation ? null : (
                                  <td>
                                    {variant ? (
                                      <span
                                        className={`status-pill ${variant.usable ? "status-pill--good" : "status-pill--purple"}`}
                                        title={variant.text}
                                      >
                                        {variant.usable ? "Approved" : "Draft waiting"}
                                      </span>
                                    ) : (
                                      <span className="muted-text">—</span>
                                    )}
                                  </td>
                                )}
                                <td className="table-actions">
                                  <button type="button" className="secondary-button" onClick={() => openDocument(row.source_id)} title="Open the document this record comes from">
                                    Open
                                  </button>
                                  {row.eligible ? null : (
                                    <button
                                      type="button"
                                      className="approve-button"
                                      disabled={busy === row.id}
                                      title="Enable for internal rehearsal: Tibi may use this record in answers"
                                      onClick={() => void decide(row, true)}
                                    >
                                      Enable
                                    </button>
                                  )}
                                  {row.approval === "rejected" ? null : (
                                    <button
                                      type="button"
                                      className="reject-button"
                                      disabled={busy === row.id}
                                      title="Exclude from answers: Tibi will not use this record"
                                      onClick={() => void decide(row, false)}
                                    >
                                      Exclude
                                    </button>
                                  )}
                                </td>
                              </tr>
                              {expanded ? (
                                <tr className="tk-detail-row">
                                  <td colSpan={columns}>
                                    <RecordDetail row={row} variant={variant} why={state.why} act={act} />
                                  </td>
                                </tr>
                              ) : null}
                            </Fragment>
                          );
                        })}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

/** A record opened in its row: the full wording, its spoken wording, the originals behind it and any decision it needs. */
function RecordDetail({ row, variant, why, act }: { row: TibiRecord; variant?: TibiSpokenVariant; why?: string; act: Act }) {
  const [sources, setSources] = useState<Record<string, string>>({});
  const [decision, setDecision] = useState("distinct_scope");
  const [reason, setReason] = useState("");

  async function toggle(sourceId: string) {
    if (sources[sourceId] !== undefined) {
      setSources(({ [sourceId]: _, ...rest }) => rest);
      return;
    }
    const source = await getTibiSource(sourceId);
    setSources((current) => ({ ...current, [sourceId]: source.text }));
  }

  return (
    <div className="tk-detail">
      {why ? <p className="tk-why">{why}</p> : null}
      <div className="tk-detail-grid">
        <section>
          <h4>Wording</h4>
          <p>{row.text}</p>
          {row.pages ? <p className="result-cite">{row.pages}</p> : null}
          {row.topics?.length ? (
            <div className="tk-topics">
              {row.topics.map((t) => (
                <span key={t} className="tk-topic">
                  {t}
                </span>
              ))}
            </div>
          ) : null}
        </section>
        {variant ? (
          <section className="tk-spoken">
            <h4>Spoken wording {variant.usable ? "· approved for the live voice" : "· waiting for approval"}</h4>
            <p>{variant.text}</p>
            {variant.status === "pending" ? (
              <div className="tibi-actions">
                <button
                  type="button"
                  className="approve-button"
                  onClick={() => void act(() => reviewTibiSpoken(variant.id, variant.text_sha256, true), "Spoken wording approved.")}
                >
                  Approve spoken wording
                </button>
                <button
                  type="button"
                  className="reject-button"
                  onClick={() => void act(() => reviewTibiSpoken(variant.id, variant.text_sha256, false), "Spoken wording rejected.")}
                >
                  Reject
                </button>
              </div>
            ) : null}
          </section>
        ) : null}
      </div>
      {row.references.length ? (
        <section>
          <h4>Supporting originals</h4>
          <div className="tk-originals">
            {row.references.map((ref) => (
              <div key={ref.source_id}>
                <button type="button" className="icon-text-button" onClick={() => void toggle(ref.source_id)}>
                  {sources[ref.source_id] !== undefined ? "Hide" : "Show"} {ref.path}
                </button>
                {sources[ref.source_id] !== undefined ? <pre className="tibi-source">{sources[ref.source_id]}</pre> : null}
              </div>
            ))}
          </div>
        </section>
      ) : null}
      {row.provenance ? (
        <section className="tibi-resolution">
          <h4>Contributed claim</h4>
          <p className="result-cite">
            Attributed to {row.provenance.contributor} · {row.provenance.topic}
            {row.disputed ? " · DISPUTED" : ""}
          </p>
          <p className="muted-text">
            Related topic records are review candidates, not proven contradictions. Inspect their scope before enabling this claim.
          </p>
          {row.overlaps.map((other) => (
            <p key={other.id} className="result-cite">
              {other.title}: {other.text}
            </p>
          ))}
          {row.resolution ? (
            <p className="result-cite">
              Last decision: {row.resolution.decision} — {row.resolution.reason}
            </p>
          ) : null}
          <select aria-label="Relationship decision" value={decision} onChange={(e) => setDecision(e.target.value)}>
            <option value="distinct_scope">Compatible / distinct scope</option>
            <option value="supersede">Replace ALL related records shown above</option>
            <option value="dispute">Dispute this and ALL related records shown above</option>
          </select>
          <textarea
            aria-label="Resolution rationale"
            placeholder="Explain the scope, version or evidence behind your decision (at least 10 characters)."
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          <button
            type="button"
            className="secondary-button"
            onClick={() =>
              void act(
                () => resolveTibiRecord(row.id, row.sha256, decision, Object.fromEntries(row.overlaps.map((o) => [o.id, o.sha256])), reason),
                "Relationship decision saved.",
              )
            }
          >
            Save relationship decision
          </button>
        </section>
      ) : null}
    </div>
  );
}

function SpokenTable({ spoken, titles, act }: { spoken: TibiSpokenVariant[]; titles: Record<string, string>; act: Act }) {
  return (
    <div className="tk-section">
      <p className="muted-text">
        Approved spoken wording lets Tibi answer broad questions instantly in the live voice. Drafts are checked against their record and
        stay pending until you approve them; a changed record withdraws its spoken wording. Draft new wording from the tile above.
      </p>
      {spoken.length === 0 ? (
        <div className="empty-card">
          <b>No spoken wording yet</b>
          <span>Enable records, then use Draft spoken wording above.</span>
        </div>
      ) : (
        <div className="table-frame">
          <table className="data-table tk-table">
            <thead>
              <tr>
                <th>Record</th>
                <th>Spoken wording</th>
                <th>State</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {spoken.map((variant) => (
                <tr key={variant.id}>
                  <td className="tk-spoken-record">{titles[variant.record_id] ?? variant.record_id}</td>
                  <td className="tk-spoken-text">{variant.text}</td>
                  <td>
                    <span className={`status-pill ${variant.usable ? "status-pill--good" : "status-pill--purple"}`}>
                      {variant.usable ? "Approved" : variant.status === "pending" ? "Waiting" : variant.status}
                    </span>
                  </td>
                  <td className="table-actions">
                    {variant.status === "pending" ? (
                      <>
                        <button
                          type="button"
                          className="approve-button"
                          onClick={() => void act(() => reviewTibiSpoken(variant.id, variant.text_sha256, true), "Spoken wording approved.")}
                        >
                          Approve
                        </button>
                        <button
                          type="button"
                          className="reject-button"
                          onClick={() => void act(() => reviewTibiSpoken(variant.id, variant.text_sha256, false), "Spoken wording rejected.")}
                        >
                          Reject
                        </button>
                      </>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function ContributionCard({
  turn,
  existing,
  onSave,
}: {
  turn: TibiContribution;
  existing?: TibiRecord;
  onSave: (body: { session_id: string; turn_id: string; text: string; status: string; expected_hash: string | null; wording_confirmed: boolean }) => Promise<void>;
}) {
  const [text, setText] = useState(existing?.provenance?.text ?? (turn.issue === "none" ? turn.raw_text : turn.quote) ?? "");
  const [status, setStatus] = useState(existing?.status ?? turn.status);
  const [confirmed, setConfirmed] = useState(false);
  return (
    <div className="result-card tk-contribution">
      <div className="result-head">
        <b>
          {turn.contributor} · {turn.topic}
        </b>
        <span className="status-pill">{turn.issue === "none" ? "clear" : turn.issue}</span>
      </div>
      <p className="result-cite">Asked: {turn.question}</p>
      <p className="result-cite">Captured: {turn.raw_text}</p>
      <label className="tibi-field">
        Proposed wording (correct recognition errors; preserve qualifications)
        <textarea value={text} onChange={(e) => setText(e.target.value)} />
      </label>
      <div className="tk-contribution-foot">
        <select aria-label="Availability" value={status} onChange={(e) => setStatus(e.target.value)}>
          {["available", "planned", "uncertain"].map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>
        <label className="tibi-field tk-confirm">
          <input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} /> I checked this wording and its
          availability. This does not approve it as fact.
        </label>
        <button
          type="button"
          className="primary-button"
          disabled={!confirmed}
          onClick={() =>
            void onSave({
              session_id: turn.session_id,
              turn_id: turn.id,
              text,
              status,
              expected_hash: existing?.sha256 ?? null,
              wording_confirmed: true,
            })
          }
        >
          {existing ? "Save corrected version (withdraws old approval)" : "Save proposed claim"}
        </button>
      </div>
    </div>
  );
}

const GROUPS: [string, string][] = [
  ["capability", "Capabilities"],
  ["component", "Components"],
  ["limitation", "Proof-of-concept boundaries"],
  ["topic", "Broad topics Tibi narrows before answering"],
];

function Ontology({ ontology, titles, act }: { ontology: TibiOntology; titles: Record<string, string>; act: Act }) {
  const changed = ontology.unusable.filter((u) => u.changed?.length);
  const waiting = ontology.unusable.filter((u) => !u.changed?.length);
  // Facts withdrawn by the same edited record(s) are read and confirmed together.
  const groups = Object.values(
    changed.reduce<Record<string, { key: string; titles: string[]; facts: typeof changed }>>((all, u) => {
      const titles = (u.changed ?? []).map((c) => c.title);
      const key = titles.join("|");
      (all[key] ??= { key, titles, facts: [] }).facts.push(u);
      return all;
    }, {}),
  );
  const names = Object.fromEntries(ontology.objects.map((o) => [o.id, o.name]));
  const detail = (o: TibiOntology["objects"][number]) =>
    o.type === "capability"
      ? o.status
      : o.type === "component"
        ? `${o.technology}; ${o.runs}`
        : o.type === "topic"
          ? `Tibi first offers: ${ontology.links
              .filter((l) => l.type === "topic_has_aspect" && l.from === o.id)
              .map((l) => names[l.to])
              .join("; ")}`
          : "";
  return (
    <div className="tk-section">
      <p className="muted-text">
        Structured product facts Tibi uses alongside the records: {ontology.objects.length} objects and {ontology.links.length} relationships.
        Every object rests on curated records and exists only while all of them are enabled; it has no approval of its own.
      </p>
      <div className="tk-ontology">
        {GROUPS.map(([type, label]) => {
          const items = ontology.objects.filter((o) => o.type === type);
          return items.length ? (
            <section className="tk-ontology-group" key={type}>
              <h4>
                {label} <span className="tree-count">{items.length}</span>
              </h4>
              <ul>
                {items.map((o) => (
                  <li key={o.id}>
                    <b>{o.name}</b>
                    {detail(o) ? <span className="tk-ontology-detail"> · {detail(o)}</span> : null}
                    {o.evidence.length ? (
                      <span className="tk-ontology-from">from {o.evidence.map((id) => titles[id] ?? id).join(", ")}</span>
                    ) : null}
                  </li>
                ))}
              </ul>
            </section>
          ) : null;
        })}
      </div>
      {changed.length ? (
        <section className="tk-confirm-facts">
          <h4>Withdrawn until you confirm them ({changed.length})</h4>
          <p className="muted-text">
            A record behind each of these facts changed since the fact was written. Tibi does not use a fact until you confirm it
            still holds against the record as it now reads. Open the record to compare, then confirm the facts that still hold.
          </p>
          {groups.map((group) => (
            <div className="tk-confirm-group" key={group.key}>
              <div className="tk-confirm-group-head">
                <b>Changed: {group.titles.join(" and ")}</b>
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() =>
                    void act(async () => {
                      for (const u of group.facts) await confirmTibiFact(u.id, u.records ?? {});
                    }, `Confirmed ${group.facts.length} fact${group.facts.length === 1 ? "" : "s"} against ${group.titles.join(" and ")}.`)
                  }
                >
                  Confirm all {group.facts.length}
                </button>
              </div>
              {group.facts.map((u) => (
                <div className="tk-confirm-fact" key={u.id}>
                  <span>{u.fact ?? u.name}</span>
                  <button
                    type="button"
                    className="text-button"
                    onClick={() => void act(() => confirmTibiFact(u.id, u.records ?? {}), `Confirmed: ${u.name}.`)}
                  >
                    Confirm
                  </button>
                </div>
              ))}
            </div>
          ))}
        </section>
      ) : null}
      {waiting.length ? (
        <details className="tk-waiting-objects">
          <summary>Waiting on records ({waiting.length})</summary>
          <ul className="tibi-verification">
            {waiting.map((u) => (
              <li key={u.id}>
                {u.name} — needs: {u.missing.map((id) => titles[id] ?? id).join(", ")}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  );
}
