// Security & audit (IAM F7): live sessions, the security settings, solo-operator mode per space, and the audit trail.
import { useState } from "react";
import type { Me } from "../api";
import { getSettings, listAudit, listSessions, revokeSession, securityOverview, SETTING_LABELS, setSoloOperator, updateSettings, verifyAudit, type AuditEvent } from "./api";
import { ConfirmDialog, EmptyCard, Field, formatWhen, Notice, Pill, Tabs, useLoad, useReauth } from "./ui";

type Tab = "overview" | "sessions" | "settings" | "audit";

export function SecurityPage({ me }: { me: Me }) {
  const [tab, setTab] = useState<Tab>("overview");
  return (
    <div className="view-stack">
      <div className="page-intro">
        <div>
          <h1>Security &amp; Audit</h1>
          <p>Sessions across the installation, the security settings, and the record of every identity and access change.</p>
        </div>
      </div>
      <Tabs tabs={[{ key: "overview", label: "Overview" }, { key: "sessions", label: "Sessions" }, { key: "settings", label: "Settings" }, { key: "audit", label: "Audit trail" }]} active={tab} onChange={setTab} />
      {tab === "overview" ? <Overview /> : tab === "sessions" ? <Sessions me={me} /> : tab === "settings" ? <Settings me={me} /> : <Audit me={me} />}
    </div>
  );
}

function Overview() {
  const overview = useLoad(securityOverview);
  const chain = useLoad(verifyAudit);
  return (
    <div className="view-stack">
      <div className="kpi-strip">
        <div className="kpi-card"><div className="kpi-card-head"><span className="kpi-label">Audit chain</span><span className={`kpi-badge ${chain.data?.intact ? "status-pill--good" : "status-pill--warn"}`}>{chain.data ? (chain.data.intact ? "Intact" : "Broken") : "…"}</span></div><div className="kpi-value">{chain.data?.events ?? "—"}</div><div className="kpi-sub">events, each hashed onto the last</div></div>
        <div className="kpi-card"><div className="kpi-card-head"><span className="kpi-label">Refusals</span><span className="kpi-badge status-pill--blue">Recent</span></div><div className="kpi-value">{overview.data?.refusals.length ?? "—"}</div><div className="kpi-sub">latest refused sign-ins and checks</div></div>
        <div className="kpi-card"><div className="kpi-card-head"><span className="kpi-label">Throttled</span><span className="kpi-badge status-pill--purple">Now</span></div><div className="kpi-value">{overview.data?.attacks.length ?? "—"}</div><div className="kpi-sub">accounts or addresses with repeated failures</div></div>
        <div className="kpi-card"><div className="kpi-card-head"><span className="kpi-label">Policy version</span><span className="kpi-badge status-pill--pink">Live</span></div><div className="kpi-value">{overview.data?.policy_version ?? "—"}</div><div className="kpi-sub">changes with every grant, deny or role edit</div></div>
      </div>
      <div className="dashboard-grid">
        <div className="panel">
          <div className="panel-heading"><div><h2>Repeated failures</h2><p className="muted-text">Per account and per network address; delays grow and cap, never a permanent lockout.</p></div></div>
          {overview.data && overview.data.attacks.length === 0 ? <p className="muted-text">None.</p> : (
            <table className="data-table"><thead><tr><th>Key</th><th>Failures</th><th>Blocked until</th></tr></thead>
              <tbody>{(overview.data?.attacks ?? []).map((a) => <tr key={a.key}><td><code>{a.key}</code></td><td>{a.count}</td><td>{a.blocked_until ? formatWhen(a.blocked_until) : "—"}</td></tr>)}</tbody></table>
          )}
        </div>
        <div className="panel">
          <div className="panel-heading"><div><h2>Emergency recovery</h2><p className="muted-text">Run on the host: <code>python -m assistant.iam recover</code>. Shown here afterwards.</p></div></div>
          {overview.data && overview.data.recovery_events.length === 0 ? <p className="muted-text">Never used.</p> : (
            <table className="data-table"><thead><tr><th>When</th><th>What</th><th>Reason</th><th>By</th></tr></thead>
              <tbody>{(overview.data?.recovery_events ?? []).map((r) => <tr key={r.id}><td>{formatWhen(r.at)}</td><td>{r.kind}</td><td>{r.reason}</td><td>{r.host_user}</td></tr>)}</tbody></table>
          )}
        </div>
      </div>
      <div className="panel">
        <div className="panel-heading"><div><h2>Latest refusals</h2></div></div>
        {overview.data && overview.data.refusals.length === 0 ? <p className="muted-text">None.</p> : <AuditTable events={overview.data?.refusals ?? []} />}
      </div>
    </div>
  );
}

function Sessions({ me }: { me: Me }) {
  const sessions = useLoad(listSessions);
  const [revoking, setRevoking] = useState<string | null>(null);
  return (
    <div className="panel">
      <div className="panel-heading"><div><h2>Live sessions</h2><p className="muted-text">Everyone signed in now. Ending a session takes effect on their next request.</p></div></div>
      {sessions.error ? <Notice tone="danger">{sessions.error}</Notice> : null}
      {sessions.data && sessions.data.length === 0 ? <EmptyCard title="No live sessions" /> : (
        <table className="data-table">
          <thead><tr><th>Person</th><th>Since</th><th>Last seen</th><th>Ends</th><th>Device</th><th /></tr></thead>
          <tbody>
            {(sessions.data ?? []).map((s) => (
              <tr key={s.id}>
                <td><div className="iam-cell-main"><b>{s.display_name}{s.current ? " (this session)" : ""}</b><small>{s.login}{s.privileged ? " · administrator session" : ""}</small></div></td>
                <td>{formatWhen(s.created_at)}</td><td>{formatWhen(s.last_seen_at)}</td><td>{formatWhen(s.absolute_expires_at)}</td>
                <td className="muted-text">{s.device || "—"}{s.address ? ` · ${s.address}` : ""}</td>
                <td><div className="iam-actions">{!s.current ? <button type="button" className="text-button" onClick={() => setRevoking(s.id)}>End</button> : null}</div></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {revoking ? (
        <ConfirmDialog open title="End this session?" body={<p>The person signs in again with their password.</p>} confirmLabel="End the session" onClose={() => setRevoking(null)}
          onConfirm={async (reason) => { await revokeSession(revoking, reason); sessions.reload(); }} />
      ) : null}
      <p className="muted-text" style={{ marginTop: 10 }}>You: {me.user.display_name}, session started {formatWhen(me.session.created_at)}.</p>
    </div>
  );
}

function Settings({ me }: { me: Me }) {
  const settings = useLoad(getSettings);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [saved, setSaved] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reauthElement, withReauth] = useReauth();
  const canManage = me.platform_permissions.includes("platform.settings.manage");
  const [solo, setSolo] = useState<{ id: string; name: string; enabled: boolean } | null>(null);
  async function save() {
    const changes: Record<string, number> = {};
    for (const [k, v] of Object.entries(draft)) if (v !== "" && Number(v) !== settings.data?.settings[k]) changes[k] = Number(v);
    if (!Object.keys(changes).length) return;
    setError(null);
    try {
      await withReauth(() => updateSettings(changes));
      setSaved(`Saved ${Object.keys(changes).length} setting(s).`);
      setDraft({});
      settings.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Not saved.");
    }
  }
  return (
    <div className="view-stack">
      <div className="panel">
        <div className="panel-heading">
          <div><h2>Security settings</h2><p className="muted-text">Working defaults from the specification; a change needs your password again and is recorded.</p></div>
          {canManage ? <button type="button" className="primary-button" disabled={!Object.keys(draft).length} onClick={() => void save()}>Save changes</button> : null}
        </div>
        {saved ? <Notice tone="good">{saved}</Notice> : null}
        {error ? <Notice tone="danger">{error}</Notice> : null}
        <div className="iam-settings-grid">
          {Object.entries(settings.data?.settings ?? {}).map(([key, value]) => (
            <Field key={key} label={SETTING_LABELS[key] ?? key} hint={key}>
              <input className="iam-input" type="number" disabled={!canManage} value={draft[key] ?? String(value)} onChange={(e) => setDraft({ ...draft, [key]: e.target.value })} />
            </Field>
          ))}
        </div>
      </div>
      <div className="panel">
        <div className="panel-heading"><div><h2>Solo-operator mode</h2><p className="muted-text">Independent review is the default: the author of a revision does not approve it. A space in solo-operator mode lets one person do both, with the self-approval permission, and says so in the audit. Off for new organisations.</p></div></div>
        <table className="data-table">
          <thead><tr><th>Space</th><th>Kind</th><th>Status</th><th>Solo-operator</th><th /></tr></thead>
          <tbody>
            {(settings.data?.spaces ?? []).map((s) => (
              <tr key={s.id}>
                <td>{s.name}</td><td>{s.kind}</td><td>{s.status}</td>
                <td><Pill tone={s.solo_operator ? "warn" : "good"}>{s.solo_operator ? "on" : "off"}</Pill></td>
                <td><div className="iam-actions">{canManage ? <button type="button" className="text-button" onClick={() => setSolo({ id: s.id, name: s.name, enabled: !s.solo_operator })}>{s.solo_operator ? "Turn off" : "Turn on"}</button> : null}</div></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {solo ? (
        <ConfirmDialog open title={`${solo.enabled ? "Enable" : "Disable"} solo-operator mode for ${solo.name}?`}
          body={<p>{solo.enabled ? "One person may then approve their own work here. Recorded as incompatible with independent-review assurance." : "Independent review applies again."}</p>}
          confirmLabel={solo.enabled ? "Enable" : "Disable"} danger={solo.enabled} onClose={() => setSolo(null)}
          onConfirm={async (reason) => { await withReauth(() => setSoloOperator(solo.id, solo.enabled, reason)); settings.reload(); }} />
      ) : null}
      {reauthElement}
    </div>
  );
}

function Audit({ me }: { me: Me }) {
  const [action, setAction] = useState("");
  const [outcome, setOutcome] = useState("");
  const [spaceId, setSpaceId] = useState("");
  const [pages, setPages] = useState<AuditEvent[][]>([]);
  const [next, setNext] = useState<number | null>(null);
  const first = useLoad(async () => {
    const page = await listAudit({ limit: 50, action: action || undefined, outcome: outcome || undefined, space_id: spaceId || undefined });
    setPages([page.events]);
    setNext(page.next);
    return page;
  }, [action, outcome, spaceId]);
  async function more() {
    if (next === null) return;
    const page = await listAudit({ limit: 50, before: next, action: action || undefined, outcome: outcome || undefined, space_id: spaceId || undefined });
    setPages((p) => [...p, page.events]);
    setNext(page.next);
  }
  const events = pages.flat();
  return (
    <div className="panel">
      <div className="panel-heading">
        <div><h2>Audit trail</h2><p className="muted-text">Identity and access events only: no document text, prompts or conversations. Secrets are never written.</p></div>
        <div className="iam-toolbar">
          <input className="iam-input" placeholder="Action, e.g. sign_in or role.*" value={action} onChange={(e) => setAction(e.target.value)} aria-label="Action" />
          <select className="iam-input" value={outcome} onChange={(e) => setOutcome(e.target.value)} aria-label="Outcome"><option value="">Any outcome</option><option value="success">success</option><option value="refused">refused</option><option value="noted">noted</option></select>
          <select className="iam-input" value={spaceId} onChange={(e) => setSpaceId(e.target.value)} aria-label="Space"><option value="">Any space</option>{me.spaces.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select>
        </div>
      </div>
      {first.error ? <Notice tone="danger">{first.error}</Notice> : null}
      {events.length === 0 && !first.loading ? <EmptyCard title="Nothing recorded for this filter" /> : <AuditTable events={events} />}
      {next !== null ? <div className="iam-toolbar" style={{ marginTop: 10 }}><button type="button" className="secondary-button" onClick={() => void more()}>Load older</button></div> : null}
    </div>
  );
}

function AuditTable({ events }: { events: AuditEvent[] }) {
  return (
    <div className="iam-table-wrap">
      <table className="data-table">
        <thead><tr><th>When</th><th>Who</th><th>Action</th><th>Outcome</th><th>Target</th><th>Detail</th></tr></thead>
        <tbody>
          {events.map((e) => (
            <tr key={e.id}>
              <td>{formatWhen(e.at)}</td>
              <td>{e.actor_name ?? (e.actor_type === "host" ? "host procedure" : e.actor_type)}</td>
              <td><code>{e.action}</code></td>
              <td><Pill tone={e.outcome === "success" ? "good" : e.outcome === "refused" ? "warn" : "neutral"}>{e.outcome}</Pill></td>
              <td>{e.target_label ?? e.target_id ?? ""}{e.space_id ? <small className="muted-text"> · {e.space_id}</small> : null}</td>
              <td className="iam-audit-detail">{[e.reason, e.after ? JSON.stringify(e.after) : "", e.detail ? JSON.stringify(e.detail) : ""].filter(Boolean).join(" · ").slice(0, 240)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
