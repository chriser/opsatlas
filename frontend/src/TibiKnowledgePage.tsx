import { useEffect, useState } from "react";
import {
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
}

/** What Tibi may say and how it chats: every record, spoken answer and contribution is enabled here by the Human. */
export function TibiKnowledgePage({ focus }: { focus?: string }) {
  const [data, setData] = useState<Loaded | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [drafting, setDrafting] = useState(false);

  async function load() {
    try {
      const [records, spoken, contributions, ontology] = await Promise.all([
        getTibiRecords(),
        getTibiSpoken(),
        getTibiContributions(),
        getTibiOntology(),
      ]);
      setData({ records: records.records, spoken: spoken.variants, turns: contributions.turns, ontology });
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load Tibi's knowledge.");
    }
  }

  useEffect(() => {
    void load();
  }, []);

  useEffect(() => {
    if (data && focus) document.getElementById(`tibi-record-${focus}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [data, focus]);

  async function act(fn: () => Promise<unknown>, done?: string) {
    try {
      await fn();
      setMessage(done ?? null);
      setError(null);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "The request failed.");
    }
  }

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

  return (
    <div className="view-stack">
      <Intro />
      <p className="muted-text">
        {enabled} of {data.records.length} records enabled for internal rehearsal.
      </p>
      {error ? <p className="muted-text" style={{ color: "var(--red)" }}>{error}</p> : null}
      {message ? <p className="muted-text" style={{ color: "var(--green)" }}>{message}</p> : null}

      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Interview contributions</h2>
            <p className="muted-text">
              Check the captured wording, including availability and qualifications. Save a proposal first; enable it separately
              after reviewing related records.
            </p>
          </div>
        </div>
        {data.turns.length ? (
          <div className="result-list" style={{ gap: 10 }}>
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
          <p className="muted-text">No interview contributions yet. Start a product interview in Talk with Tibi.</p>
        )}
      </div>

      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Spoken answers</h2>
            <p className="muted-text">
              Approved spoken wording lets Tibi answer broad questions instantly in the live voice. Drafts are checked against their
              record and stay pending until you approve them; a changed record withdraws its spoken wording.
            </p>
          </div>
          <button type="button" className="secondary-button" disabled={drafting} onClick={() => void draft()}>
            {drafting ? "Drafting with the local model…" : "Draft spoken wording for enabled records"}
          </button>
        </div>
        <div className="result-list" style={{ gap: 10 }}>
          {data.spoken.filter((v) => v.status !== "rejected" && v.current).map((variant) => (
            <div className="result-card" key={variant.id}>
              <div className="result-head">
                <b>{titles[variant.record_id] ?? variant.record_id}</b>
                <span className="status-pill">{variant.usable ? "approved for the live voice" : variant.status}</span>
              </div>
              <p>{variant.text}</p>
              {variant.status === "pending" ? (
                <div className="tibi-actions">
                  <button type="button" className="primary-button" onClick={() => void act(() => reviewTibiSpoken(variant.id, variant.text_sha256, true))}>
                    Approve spoken wording
                  </button>
                  <button type="button" className="secondary-button" onClick={() => void act(() => reviewTibiSpoken(variant.id, variant.text_sha256, false))}>
                    Reject
                  </button>
                </div>
              ) : null}
            </div>
          ))}
        </div>
      </div>

      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Conversation style</h2>
            <p className="muted-text">
              How Tibi chats: its personality, small talk, everyday topics, the topics it keeps out of, and the purpose of a sales
              conversation. These records guide conversation only; they are never used as product evidence.
            </p>
          </div>
        </div>
        <div className="result-list" style={{ gap: 10 }}>
          {conversation.map((row) => (
            <RecordCard key={row.id} row={row} act={act} />
          ))}
        </div>
      </div>

      <OntologyPanel ontology={data.ontology} titles={titles} />

      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Product records</h2>
            <p className="muted-text">
              Inspect the wording and supporting originals before enabling each record. Enabling permits internal rehearsal only;
              it is not approval for customer commitments.
            </p>
          </div>
        </div>
        <div className="result-list" style={{ gap: 10 }}>
          {product.map((row) => (
            <RecordCard key={row.id} row={row} act={act} />
          ))}
        </div>
      </div>
    </div>
  );
}

function Intro() {
  return (
    <div className="page-intro">
      <h1>Tibi knowledge</h1>
      <p>
        What Tibi may say and how it chats. Every record, spoken answer and interview contribution is enabled here by a person;
        nothing Tibi hears is approved automatically.
      </p>
    </div>
  );
}

function RecordCard({ row, act }: { row: TibiRecord; act: (fn: () => Promise<unknown>, done?: string) => Promise<void> }) {
  const [sources, setSources] = useState<Record<string, string>>({});
  const [decision, setDecision] = useState("distinct_scope");
  const [reason, setReason] = useState("");
  const state = row.eligible
    ? "enabled"
    : row.approval === "approved"
      ? row.review_block ?? "evidence changed — unavailable"
      : row.approval;

  async function toggle(sourceId: string) {
    if (sources[sourceId] !== undefined) {
      setSources(({ [sourceId]: _, ...rest }) => rest);
      return;
    }
    const source = await getTibiSource(sourceId);
    setSources((current) => ({ ...current, [sourceId]: source.text }));
  }

  return (
    <div className="result-card" id={`tibi-record-${row.id}`}>
      <div className="result-head">
        <b>{row.title}</b>
        <span className="status-pill">
          {row.status} · {state}
        </span>
      </div>
      <p>{row.text}</p>
      {row.pages ? <p className="result-cite">{row.pages}</p> : null}
      {row.references.length ? (
        <details>
          <summary>Inspect supporting originals</summary>
          {row.references.map((ref) => (
            <div key={ref.source_id}>
              <button type="button" className="secondary-button" onClick={() => void toggle(ref.source_id)}>
                {ref.path}
              </button>
              {sources[ref.source_id] !== undefined ? <pre className="tibi-source">{sources[ref.source_id]}</pre> : null}
            </div>
          ))}
        </details>
      ) : null}
      {row.provenance ? (
        <div className="tibi-resolution">
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
              void act(() =>
                resolveTibiRecord(row.id, row.sha256, decision, Object.fromEntries(row.overlaps.map((o) => [o.id, o.sha256])), reason),
              )
            }
          >
            Save relationship decision
          </button>
        </div>
      ) : null}
      <div className="tibi-actions">
        <button type="button" className="primary-button" disabled={row.eligible} onClick={() => void act(() => reviewTibiRecord(row.id, row.sha256, true))}>
          Enable for internal rehearsal
        </button>
        <button type="button" className="secondary-button" onClick={() => void act(() => reviewTibiRecord(row.id, row.sha256, false))}>
          Exclude from answers
        </button>
      </div>
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
    <div className="result-card">
      <div className="result-head">
        <b>
          {turn.contributor} · {turn.topic} · {turn.issue}
        </b>
      </div>
      <p className="result-cite">Asked: {turn.question}</p>
      <p className="result-cite">Captured: {turn.raw_text}</p>
      <label className="tibi-field">
        Proposed wording (correct recognition errors; preserve qualifications)
        <textarea value={text} onChange={(e) => setText(e.target.value)} />
      </label>
      <select aria-label="Availability" value={status} onChange={(e) => setStatus(e.target.value)}>
        {["available", "planned", "uncertain"].map((value) => (
          <option key={value} value={value}>
            {value}
          </option>
        ))}
      </select>
      <label className="tibi-field">
        <input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} /> I checked this wording and its
        availability. This does not approve it as fact.
      </label>
      <button
        type="button"
        className="secondary-button"
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
  );
}

const GROUPS: [string, string][] = [
  ["capability", "Capabilities"],
  ["component", "Components"],
  ["limitation", "Proof-of-concept boundaries"],
  ["topic", "Broad topics Tibi narrows before answering"],
];

function OntologyPanel({ ontology, titles }: { ontology: TibiOntology; titles: Record<string, string> }) {
  const names = Object.fromEntries(ontology.objects.map((o) => [o.id, o.name]));
  const describe = (o: TibiOntology["objects"][number]) =>
    o.type === "capability"
      ? `${o.name} (${o.status})`
      : o.type === "component"
        ? `${o.name} — ${o.technology}; ${o.runs}`
        : o.type === "topic"
          ? `${o.name} — Tibi first offers: ${ontology.links
              .filter((l) => l.type === "topic_has_aspect" && l.from === o.id)
              .map((l) => names[l.to])
              .join("; ")}`
          : o.name;
  return (
    <div className="panel">
      <div className="panel-heading">
        <div>
          <h2>Product ontology</h2>
          <p className="muted-text">
            Structured product facts Tibi uses alongside the records. Every object rests on curated records and exists only while all of
            them are enabled; it has no approval of its own.
          </p>
        </div>
        <span className="status-pill">
          {ontology.objects.length} objects · {ontology.links.length} relationships
        </span>
      </div>
      {GROUPS.map(([type, label]) => {
        const items = ontology.objects.filter((o) => o.type === type);
        return items.length ? (
          <div className="result-card" key={type} style={{ marginBottom: 10 }}>
            <div className="result-head">
              <b>{label}</b>
            </div>
            <ul className="tibi-verification">
              {items.map((o) => (
                <li key={o.id}>
                  {describe(o)}
                  {o.evidence.length ? <span className="muted-text"> · from: {o.evidence.map((id) => titles[id] ?? id).join(", ")}</span> : null}
                </li>
              ))}
            </ul>
          </div>
        ) : null;
      })}
      {ontology.unusable.length ? (
        <details>
          <summary>Waiting on records ({ontology.unusable.length})</summary>
          <ul className="tibi-verification">
            {ontology.unusable.map((u) => (
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
