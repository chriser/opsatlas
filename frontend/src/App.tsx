import { lazy, Suspense, useCallback, useEffect, useRef, useState } from "react";
import {
  AUTH_INVALID_EVENT,
  getComplianceReasoningStatus,
  getScorecard,
  getTibiStatus,
  isAuthenticated,
  logout,
  restartServices,
  type ComplianceReasoningStatus,
  type HealthResponse,
  type Scorecard,
  type TibiStatus,
} from "./api";
import { AnalyticsPage } from "./AnalyticsPage";
import { AskPage } from "./AskPage";
import { AvatarLabPage } from "./AvatarLabPage";
import { BrandMark } from "./BrandMark";
import { EnterpriseActivityModelPage } from "./EnterpriseActivityModelPage";
import { ExternalSourcesPage } from "./ExternalSourcesPage";
import { GovernancePage } from "./GovernancePage";
import { KnowledgeSourcesPage } from "./KnowledgeSourcesPage";
import { LoginScreen } from "./LoginScreen";
import { ProcessRegistryPage } from "./ProcessRegistryPage";
import { ProcessStressLabPage } from "./ProcessStressLabPage";
import { RetrievalPage } from "./RetrievalPage";
import { SystemPage } from "./SettingsPage";
import { SimulatorPage } from "./SimulatorPage";
import { TibiKnowledgePage } from "./TibiKnowledgePage";
import { ConversationsPage } from "./ConversationsPage";
import { TibiPage, type TibiMode } from "./TibiPage";
import { endTibiIfActive } from "./tibi/voice";
import { OPERATOR } from "./operator";

// The document workspace carries the editor; it loads when a document is first opened.
const DocumentPage = lazy(() => import("./content/DocumentPage").then((m) => ({ default: m.DocumentPage })));
import "./App.css";

type ViewKey =
  | "dashboard"
  | "sources"
  | "ask"
  | "avatar"
  | "rag"
  | "governance"
  | "processes"
  | "operating-model"
  | "stress-lab"
  | "analytics"
  | "simulator"
  | "external"
  | "system"
  | "tibi"
  | "tibi-knowledge"
  | "tibi-conversations"
  | "document";

interface NavItem {
  type: "item";
  key: ViewKey;
  label: string;
  summary: string;
  icon: string;
  section?: string;
}

interface NavGroup {
  type: "group";
  id: string;
  label: string;
  summary: string;
  icon: string;
  section?: string;
  children: Omit<NavItem, "type">[];
}

type NavEntry = NavItem | NavGroup;

const NAV_ITEMS: NavEntry[] = [
  { type: "item", key: "dashboard", label: "Dashboard", summary: "Platform overview & metrics", icon: "D", section: "MAIN" },
  {
    type: "group",
    id: "ask",
    label: "Ask Assistant",
    summary: "Digital SME, written & citation checks",
    icon: "A",
    section: "INTELLIGENCE & SPEECH",
    children: [
      { key: "avatar", label: "Ask Digital SME", summary: "Spoken answers through avatar", icon: "D" },
      { key: "ask", label: "Written Query", summary: "Grounded written answers", icon: "W" },
      { key: "rag", label: "Citation Check", summary: "Inspect retrieved evidence", icon: "C" },
    ],
  },
  {
    type: "group",
    id: "tibi",
    label: "Tibi Voice",
    summary: "Voice companion & knowledge base",
    icon: "T",
    section: "INTELLIGENCE & SPEECH",
    children: [
      { key: "tibi", label: "Talk with Tibi", summary: "Voice chat, interviews & governance", icon: "T" },
      { key: "tibi-knowledge", label: "Tibi Knowledge", summary: "Spoken knowledge & conversation rules", icon: "K" },
      { key: "tibi-conversations", label: "Conversation Log", summary: "Review turns & mark what to improve", icon: "L" },
    ],
  },
  { type: "item", key: "governance", label: "Governance Review", summary: "Duplicates, conflicts & regulation checks", icon: "G", section: "GOVERNANCE & ARCHITECTURE" },
  { type: "item", key: "operating-model", label: "Enterprise Activity Model", summary: "Ontology-backed activity canvas", icon: "E", section: "GOVERNANCE & ARCHITECTURE" },
  { type: "item", key: "analytics", label: "Analytics & Telemetry", summary: "Demand, quality & insight charts", icon: "I", section: "GOVERNANCE & ARCHITECTURE" },
  {
    type: "group",
    id: "system",
    label: "Platform Services",
    summary: "Models, sources & diagnostics",
    icon: "S",
    section: "SYSTEM & CONFIGURATION",
    children: [
      { key: "system", label: "System Overview", summary: "Local models & diagnostics", icon: "S" },
      { key: "sources", label: "Knowledge Sources", summary: "Upload & manage source documents", icon: "K" },
      { key: "external", label: "External Sources", summary: "Public UK regulatory snapshots", icon: "E" },
      { key: "processes", label: "Process Registry", summary: "Structured process knowledge", icon: "P" },
      { key: "simulator", label: "Simulator", summary: "Synthetic persona journeys", icon: "M" },
      { key: "stress-lab", label: "Process Stress Lab", summary: "Scenario pressure and metric guide", icon: "L" },
    ],
  },
];

const VIEW_TITLE: Record<ViewKey, string> = {
  dashboard: "Dashboard",
  sources: "Knowledge Sources",
  ask: "Written Query",
  avatar: "Ask Digital SME",
  rag: "Citation Check",
  governance: "Governance",
  processes: "Process Registry",
  "operating-model": "Enterprise Activity Model",
  "stress-lab": "Process Stress Lab",
  analytics: "Analytics",
  simulator: "Simulator",
  external: "External Sources",
  system: "System",
  tibi: "Talk with Tibi",
  "tibi-knowledge": "Tibi knowledge",
  "tibi-conversations": "Conversation log",
  document: "Document",
};

const VIEWS = new Set<string>(Object.keys(VIEW_TITLE));

/** "#tibi-knowledge:overview" opens Tibi knowledge at the record "overview"; links from Tibi use it. */
function viewFromHash(): { view: ViewKey; anchor?: string } | null {
  const [view, anchor] = decodeURIComponent(window.location.hash.slice(1)).split(":");
  return VIEWS.has(view) ? { view: view as ViewKey, anchor } : null;
}

type Health = "checking" | "online" | "offline";

/** The core API's answer to /api/health: whether it is up, and what it reports (sources, configured models). */
interface BackendHealth {
  state: Health;
  info: HealthResponse | null;
}

/** Supporting services as they answer now, checked again every 30 seconds while the control panel is open. */
interface ServiceStatus {
  backend: BackendHealth;
  compliance: ComplianceReasoningStatus | "error" | null;
  voice: TibiStatus | "error" | null;
  checkedAt: Date | null;
}

const STATUS_EVERY_MS = 30_000;

function useServiceStatus(authed: boolean, tibi: boolean): [ServiceStatus, () => void] {
  const [again, setAgain] = useState(0);
  const [status, setStatus] = useState<ServiceStatus>({
    backend: { state: "checking", info: null },
    compliance: null,
    voice: null,
    checkedAt: null,
  });
  useEffect(() => {
    let active = true;
    async function check() {
      const backend = await fetch("/api/health")
        .then(async (r): Promise<BackendHealth> => ({
          state: r.ok ? "online" : "offline",
          info: r.ok ? ((await r.json().catch(() => null)) as HealthResponse | null) : null,
        }))
        .catch((): BackendHealth => ({ state: "offline", info: null }));
      // The other two need a signed-in operator.
      const compliance = authed ? await getComplianceReasoningStatus().catch(() => "error" as const) : null;
      const voice = authed && tibi ? await getTibiStatus().then((v) => v ?? ("error" as const)).catch(() => "error" as const) : null;
      if (active) setStatus({ backend, compliance, voice, checkedAt: new Date() });
    }
    void check();
    const timer = window.setInterval(() => void check(), STATUS_EVERY_MS);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [authed, tibi, again]);
  return [status, useCallback(() => setAgain((n) => n + 1), [])];
}

type ServiceState = "good" | "warn" | "off" | "checking";

interface ServiceRow {
  name: string;
  detail: string;
  state: ServiceState;
  icon: "api" | "shield" | "voice";
  title?: string;
}

/** Only services that are actually checked are listed; a configured model name is not a health check. */
function serviceRows(status: ServiceStatus, tibi: boolean): ServiceRow[] {
  const { backend, compliance, voice } = status;
  const models = backend.info?.models;
  const rows: ServiceRow[] = [
    {
      name: "Core API",
      icon: "api",
      state: backend.state === "online" ? "good" : backend.state === "offline" ? "warn" : "checking",
      detail:
        backend.state === "online"
          ? `Online · ${backend.info?.sources ?? "?"} sources`
          : backend.state === "offline"
            ? "Not answering"
            : "Checking…",
      title: models ? `Answers by ${models.llm ?? "not set"}; embeddings by ${models.embed ?? "not set"}` : undefined,
    },
    {
      name: "Compliance reasoning",
      icon: "shield",
      state:
        compliance === null ? "checking" : compliance === "error" || compliance.status === "unavailable" ? "warn" : compliance.status === "available" ? "good" : "off",
      detail:
        compliance === null
          ? "Checking…"
          : compliance === "error" || compliance.status === "unavailable"
            ? "Not answering"
            : compliance.status === "available"
              ? "Ready"
              : "Not configured here",
    },
  ];
  if (tibi) {
    const up = voice !== null && voice !== "error" && voice.available;
    rows.push({
      name: "Tibi voice",
      icon: "voice",
      state: voice === null ? "checking" : up ? "good" : "warn",
      detail: voice === null ? "Checking…" : up ? (voice.busy ? "Ready · may be slow to start" : "Ready") : "Voice service not running",
      title: voice !== null && voice !== "error" && voice.busy ? voice.busy : undefined,
    });
  }
  return rows;
}

function ServiceIcon({ icon }: { icon: ServiceRow["icon"] }) {
  const paths = {
    api: "M4 5h16v5H4zM4 14h16v5H4zM8 7.5h.01M8 16.5h.01",
    shield: "M12 3l7 3v5c0 4.4-3 8.3-7 10-4-1.7-7-5.6-7-10V6z M9 12l2 2 4-4",
    voice: "M12 3a3 3 0 0 1 3 3v6a3 3 0 0 1-6 0V6a3 3 0 0 1 3-3z M5 11a7 7 0 0 0 14 0 M12 18v3",
  };
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={paths[icon]} />
    </svg>
  );
}

const LIGHT_WORDS: Record<ServiceState, string> = { good: "running", warn: "not answering", off: "switched off", checking: "being checked" };

const RESTART_WAIT_MS = 90_000;

/** Wait until ``ready`` answers true, having first seen it answer false (the service went down) or waited 4 s. */
async function waitForRestart(ready: () => Promise<boolean>): Promise<boolean> {
  const started = Date.now();
  let wentDown = false;
  while (Date.now() - started < RESTART_WAIT_MS) {
    await new Promise((r) => window.setTimeout(r, 1500));
    const up = await ready().catch(() => false);
    if (!up) wentDown = true;
    else if (wentDown || Date.now() - started > 4000) return true;
  }
  return false;
}

/** Restart services from the control panel: Tibi alone when a conversation will not start, or everything. */
function RestartServices({ onRestarted }: { onRestarted: () => void }) {
  const [choosing, setChoosing] = useState(false);
  const [state, setState] = useState<{ phase: "restarting" | "done" | "failed"; message: string } | null>(null);

  async function restart(which: "tibi" | "all") {
    setChoosing(false);
    setState({ phase: "restarting", message: which === "all" ? "Restarting OpsAtlas and Tibi…" : "Restarting Tibi…" });
    try {
      await restartServices(which);
    } catch (error) {
      setState({ phase: "failed", message: error instanceof Error ? error.message : "The restart was refused." });
      return;
    }
    if (which === "all") {
      const back = await waitForRestart(() => fetch("/api/health").then((r) => r.ok));
      if (back) window.location.reload(); // sign-ins were held by the old process: sign in again
      else setState({ phase: "failed", message: "OpsAtlas did not come back within 90 seconds." });
      return;
    }
    const back = await waitForRestart(() => getTibiStatus().then((s) => Boolean(s?.available)));
    onRestarted();
    setState(back ? { phase: "done", message: "Tibi restarted. Start the conversation again." } : { phase: "failed", message: "Tibi did not come back within 90 seconds." });
    if (back) window.setTimeout(() => setState((s) => (s?.phase === "done" ? null : s)), 8000);
  }

  return (
    <div className="sidebar-restart">
      {state ? <p className={`sidebar-restart-note sidebar-restart-note--${state.phase}`}>{state.message}</p> : null}
      {choosing ? (
        <div className="sidebar-restart-choices">
          <button type="button" onClick={() => void restart("tibi")}>
            <b>Restart Tibi</b>
            <small>Ends a conversation in progress. You stay signed in.</small>
          </button>
          <button type="button" onClick={() => void restart("all")}>
            <b>Restart all</b>
            <small>OpsAtlas and Tibi. Sign in again afterwards.</small>
          </button>
          <button type="button" className="sidebar-restart-cancel" onClick={() => setChoosing(false)}>
            Cancel
          </button>
        </div>
      ) : (
        <button type="button" className="sidebar-restart-button" disabled={state?.phase === "restarting"} onClick={() => setChoosing(true)}>
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M3 12a9 9 0 0 1 15.5-6.2L21 8M21 3v5h-5M21 12a9 9 0 0 1-15.5 6.2L3 16M3 21v-5h5" />
          </svg>
          {state?.phase === "restarting" ? "Restarting…" : "Restart services"}
        </button>
      )}
    </div>
  );
}

/** The sidebar's live status: a light per service, green running, red not answering, grey off or being checked. */
function SidebarStatus({ status, tibi, onRefresh }: { status: ServiceStatus; tibi: boolean; onRefresh: () => void }) {
  const rows = serviceRows(status, tibi);
  const checked = status.checkedAt;
  return (
    <section className="sidebar-status" aria-label="Service status">
      <div className="sidebar-status-head">
        <span className="sidebar-status-title">Status</span>
        <span
          className={`sidebar-status-live${checked ? "" : " sidebar-status-live--checking"}`}
          title={checked ? `Checked ${checked.toLocaleTimeString()}; checked again every 30 seconds` : "First check running"}
        >
          {checked ? "Live" : "Checking"}
        </span>
      </div>
      {rows.map((row) => (
        <div className="sidebar-status-row" key={row.name} title={row.title}>
          <span className="sidebar-status-icon">
            <ServiceIcon icon={row.icon} />
            <span className={`sidebar-status-light sidebar-status-light--${row.state}`} aria-label={`${row.name} ${LIGHT_WORDS[row.state]}`} />
          </span>
          <span className="sidebar-status-text">
            <b>{row.name}</b>
            <small>{row.detail}</small>
          </span>
        </div>
      ))}
      {tibi ? <RestartServices onRestarted={onRefresh} /> : null}
    </section>
  );
}

function HealthPill({ health }: { health: Health }) {
  const label = health === "online" ? "Backend online" : health === "offline" ? "Backend offline" : "Checking backend";
  const cls = health === "online" ? "status-pill status-pill--good" : health === "offline" ? "status-pill status-pill--warn" : "status-pill";
  return <span className={cls}>{label}</span>;
}

function findNavItem(view: ViewKey): Omit<NavItem, "type"> | undefined {
  for (const item of NAV_ITEMS) {
    if (item.type === "group") {
      const child = item.children.find((entry) => entry.key === view);
      if (child) return child;
    } else if (item.key === view) {
      return item;
    }
  }
}

const HEALTH_WORDS: Record<Health, string> = { online: "Backend online", offline: "Backend offline", checking: "Checking backend" };

function Sidebar({
  view,
  onSelect,
  hidden,
  status,
  onRefreshStatus,
}: {
  view: ViewKey;
  onSelect: (v: ViewKey) => void;
  hidden: string[];
  status: ServiceStatus;
  onRefreshStatus: () => void;
}) {
  const [openGroup, setOpenGroup] = useState<string | null>(null);

  useEffect(() => {
    const activeGroup = NAV_ITEMS.find(
      (item): item is NavGroup => item.type === "group" && item.children.some((child) => child.key === view),
    );
    setOpenGroup(activeGroup?.id ?? null);
  }, [view]);

  function onItemSelect(nextView: ViewKey) {
    const parentGroup = NAV_ITEMS.find(
      (item): item is NavGroup => item.type === "group" && item.children.some((child) => child.key === nextView),
    );
    setOpenGroup(parentGroup?.id ?? null);
    onSelect(nextView);
  }

  function onGroupClick(item: NavGroup) {
    if (item.children.length === 1) {
      onItemSelect(item.children[0].key);
      return;
    }
    setOpenGroup((current) => (current === item.id ? null : item.id));
  }

  let lastSection: string | undefined = undefined;

  return (
    <aside className="sidebar">
      <div className="brand-block">
        <BrandMark />
      </div>

      <div className="operator-card">
        <div className="operator-avatar">
          <img src={OPERATOR.photo} alt={OPERATOR.name} />
          <span
            className={`operator-status-square operator-status-square--${status.backend.state}`}
            title={HEALTH_WORDS[status.backend.state]}
          />
        </div>
        <div className="operator-meta">
          <span className="operator-role">{OPERATOR.role}</span>
          <span className="operator-name">{OPERATOR.name}</span>
        </div>
      </div>

      <div className="sidebar-scroll">
        <nav className="sidebar-nav">
          {NAV_ITEMS.filter((item) => !hidden.includes(item.type === "group" ? item.id : item.key)).map((item) => {
            const showSection = item.section && item.section !== lastSection;
            if (item.section) lastSection = item.section;

            if (item.type === "group") {
              const active = item.children.some((child) => child.key === view);
              const open = openGroup === item.id;
              return (
                <div key={item.id} className="sidebar-group-wrapper">
                  {showSection ? <div className="sidebar-section-heading">{item.section}</div> : null}
                  <div className={`sidebar-group${open ? " sidebar-group--open" : ""}`}>
                    <button
                      type="button"
                      className={`sidebar-link sidebar-link--group${active ? " sidebar-link--active" : ""}`}
                      aria-expanded={open}
                      onClick={() => onGroupClick(item)}
                    >
                      <span className="nav-icon">{item.icon}</span>
                      <span className="nav-text">
                        <span className="nav-label">{item.label}</span>
                        <span className="nav-summary">{item.summary}</span>
                      </span>
                      <span className={`nav-chevron${open ? " nav-chevron--open" : ""}`}>›</span>
                    </button>
                    <div className="sidebar-subnav" aria-hidden={!open}>
                      {item.children.map((child) => (
                        <button
                          key={child.key}
                          type="button"
                          className={`sidebar-sublink${child.key === view ? " sidebar-sublink--active" : ""}`}
                          onClick={() => onItemSelect(child.key)}
                        >
                          <span className="sidebar-sublink-dot" />
                          <span className="sidebar-sublink-text">
                            <b>{child.label}</b>
                            <small>{child.summary}</small>
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              );
            }
            return (
              <div key={item.key} className="sidebar-item-wrapper">
                {showSection ? <div className="sidebar-section-heading">{item.section}</div> : null}
                <button
                  type="button"
                  className={`sidebar-link${item.key === view ? " sidebar-link--active" : ""}`}
                  onClick={() => onItemSelect(item.key)}
                >
                  <span className="nav-icon">{item.icon}</span>
                  <span className="nav-text">
                    <span className="nav-label">{item.label}</span>
                    <span className="nav-summary">{item.summary}</span>
                  </span>
                  {item.key === view ? (
                    <span className="nav-active-dot">
                      <span />
                    </span>
                  ) : null}
                </button>
              </div>
            );
          })}
        </nav>

        <SidebarStatus status={status} tibi={!hidden.includes("tibi")} onRefresh={onRefreshStatus} />

        <div className="sidebar-footer">
          <span>OpsAtlas</span>
          <b>Control Panel</b>
        </div>
      </div>
    </aside>
  );
}

function DashboardView({ onSelect }: { onSelect: (v: ViewKey) => void }) {
  const quick: { key: ViewKey; icon: string; title: string; sub: string; primary?: boolean }[] = [
    { key: "sources", icon: "+", title: "Upload Knowledge Source", sub: "Ingest anonymised source material", primary: true },
    { key: "governance", icon: "!", title: "Review Governance Conflicts", sub: "Detect duplicates & statement clashes" },
    { key: "rag", icon: "C", title: "Citation & Evidence Check", sub: "Inspect retrieved knowledge evidence" },
    { key: "operating-model", icon: "E", title: "Enterprise Activity Model", sub: "Navigate ontology activity graph" },
  ];
  const [card, setCard] = useState<Scorecard | null>(null);
  useEffect(() => {
    getScorecard().then(setCard).catch(() => setCard(null));
  }, []);

  return (
    <div className="view-stack">
      <div className="page-intro">
        <div>
          <h1>Welcome back, Operator</h1>
          <p>OpsAtlas local control center: ingest, govern, verify citations and query enterprise knowledge.</p>
        </div>
        <span className="status-pill status-pill--good">
          Local-First Architecture
        </span>
      </div>

      {/* Inspiration 1: Floating KPI Metric Cards */}
      <div className="kpi-strip">
        <div className="kpi-card">
          <div className="kpi-card-head">
            <span className="kpi-label">Total Queries</span>
            <span className="kpi-badge status-pill--blue">Lifetime</span>
          </div>
          <div className="kpi-value">{card ? card.total_queries : "—"}</div>
          <div className="kpi-sub">Questions processed</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-card-head">
            <span className="kpi-label">Answer Rate</span>
            <span className="kpi-badge status-pill--good">Resolution</span>
          </div>
          <div className="kpi-value">{card && card.total_queries > 0 ? `${Math.round(card.answer_rate * 100)}%` : "—"}</div>
          <div className="kpi-sub">Knowledge answers resolved</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-card-head">
            <span className="kpi-label">Grounded Rate</span>
            <span className="kpi-badge status-pill--purple">Evidence</span>
          </div>
          <div className="kpi-value">{card && card.total_queries > 0 ? `${Math.round(card.grounded_rate * 100)}%` : "—"}</div>
          <div className="kpi-sub">Grounded with citations</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-card-head">
            <span className="kpi-label">Avg Citations</span>
            <span className="kpi-badge status-pill--pink">Verified</span>
          </div>
          <div className="kpi-value">{card && card.total_queries > 0 ? card.avg_citations : "—"}</div>
          <div className="kpi-sub">Sources per answer</div>
        </div>
      </div>

      <div className="dashboard-grid">
        <div className="column-stack">
          <div className="panel">
            <div className="panel-heading">
              <div>
                <h2>Quick Workflows</h2>
                <p className="muted-text">Jump into common operational tasks.</p>
              </div>
            </div>
            <div className="quick-list">
              {quick.map((q) => (
                <button
                  key={q.title}
                  type="button"
                  className={`quick-card${q.primary ? " quick-card--primary" : ""}`}
                  onClick={() => onSelect(q.key)}
                >
                  <span className="quick-icon">{q.icon}</span>
                  <span>
                    <b>{q.title}</b>
                    <small>{q.sub}</small>
                  </span>
                  <span className="quick-chevron">›</span>
                </button>
              ))}
            </div>
          </div>

        </div>

        <div className="column-stack">
          <div className="panel">
            <div className="panel-heading">
              <div>
                <h2>Assistant Scorecard</h2>
                <p className="muted-text">Synthesis quality across operator inquiries.</p>
              </div>
              <span className="status-pill">{card ? `${card.total_queries} queries` : "Ready"}</span>
            </div>
            {card && card.total_queries > 0 ? (
              <div className="result-list" style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 12 }}>
                <div className="result-card">
                  <div className="result-head">
                    <b style={{ fontSize: 24 }}>{card.total_queries}</b>
                    <span className="status-pill status-pill--blue">Total</span>
                  </div>
                  <p className="result-cite">Questions Asked</p>
                </div>
                <div className="result-card">
                  <div className="result-head">
                    <b style={{ fontSize: 24 }}>{Math.round(card.answer_rate * 100)}%</b>
                    <span className="status-pill status-pill--good">Resolved</span>
                  </div>
                  <p className="result-cite">Answer Rate</p>
                </div>
                <div className="result-card">
                  <div className="result-head">
                    <b style={{ fontSize: 24 }}>{Math.round(card.grounded_rate * 100)}%</b>
                    <span className="status-pill status-pill--purple">Verified</span>
                  </div>
                  <p className="result-cite">Grounded Rate</p>
                </div>
                <div className="result-card">
                  <div className="result-head">
                    <b style={{ fontSize: 24 }}>{card.avg_citations}</b>
                    <span className="status-pill status-pill--pink">Sources</span>
                  </div>
                  <p className="result-cite">Avg Citations</p>
                </div>
              </div>
            ) : (
              <div className="empty-card" style={{ padding: "28px" }}>
                <b>Assistant telemetry standing by</b>
                <span>Submit questions via Written Query or Ask Digital SME to build telemetry and verify grounded citations.</span>
                <button
                  type="button"
                  className="primary-button"
                  style={{ marginTop: 12 }}
                  onClick={() => onSelect("ask")}
                >
                  Ask a Question →
                </button>
              </div>
            )}
          </div>

          {card && Object.keys(card.by_topic).length > 0 ? (
            <div className="panel">
              <div className="panel-heading">
                <div>
                  <h2>Questions by Topic</h2>
                  <p className="muted-text">Distribution of operator inquiries.</p>
                </div>
              </div>
              <div className="result-list">
                {Object.entries(card.by_topic).map(([topic, n]) => (
                  <div className="result-card" key={topic}>
                    <div className="result-head">
                      <b>{topic.replace(/_/g, " ")}</b>
                      <span className="status-pill status-pill--blue">{n} queries</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function PlaceholderView({ view }: { view: ViewKey }) {
  const item = findNavItem(view)!;
  return (
    <div className="view-stack">
      <div className="page-intro">
        <h1>{item.label}</h1>
        <p>{item.summary}</p>
      </div>
      <div className="panel">
        <div className="empty-card">
          <b>Coming soon</b>
          <span>This area is part of a later sprint. The shell and design system are in place.</span>
        </div>
      </div>
    </div>
  );
}

export function App() {
  const initial = viewFromHash();
  const [view, setView] = useState<ViewKey>(initial?.view ?? "dashboard");
  const [anchor, setAnchor] = useState<string | undefined>(initial?.anchor);
  // A document opens over the page that listed it; Back returns there.
  const openedFrom = useRef<ViewKey>(initial?.view && initial.view !== "document" ? initial.view : "governance");
  useEffect(() => {
    if (view !== "document") openedFrom.current = view;
  }, [view]);
  const [authed, setAuthed] = useState(isAuthenticated());
  const [tibi, setTibi] = useState<TibiStatus | null>(null);
  const [tibiMode, setTibiMode] = useState<TibiMode>("recall");
  const [status, refreshStatus] = useServiceStatus(authed, Boolean(tibi));

  useEffect(() => {
    if (!authed) return;
    getTibiStatus()
      .then(setTibi)
      .catch(() => setTibi(null));
  }, [authed]);

  useEffect(() => {
    // Keep the address in step with the page, so Tibi and bookmarks can link straight to it.
    const hash = `#${view}${anchor ? `:${anchor}` : ""}`;
    if (window.location.hash !== hash) window.history.replaceState(null, "", hash);
  }, [view, anchor]);

  useEffect(() => {
    const onHash = () => {
      const next = viewFromHash();
      if (next) {
        setView(next.view);
        setAnchor(next.anchor);
      }
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  function select(next: ViewKey) {
    if (next === "tibi" && view !== "tibi") setTibiMode("recall");
    setAnchor(undefined);
    setView(next);
  }

  function resolveWithTibi() {
    setTibiMode("governance");
    setAnchor(undefined);
    setView("tibi");
  }

  useEffect(() => {
    const onInvalid = () => setAuthed(false);
    window.addEventListener(AUTH_INVALID_EVENT, onInvalid);
    return () => window.removeEventListener(AUTH_INVALID_EVENT, onInvalid);
  }, []);

  async function onLogout() {
    // Signing out ends a conversation with Tibi first: nothing keeps listening for a signed-out page (audit F09).
    endTibiIfActive();
    await logout();
    setAuthed(false);
  }

  if (!authed) {
    return <LoginScreen onSuccess={() => setAuthed(true)} />;
  }

  return (
    <div className="console-shell">
      <Sidebar view={view} onSelect={select} hidden={tibi ? [] : ["tibi"]} status={status} onRefreshStatus={refreshStatus} />
      <main className="content-shell">
        <div className="topbar">
          <div className="topbar-breadcrumb">
            <span className="breadcrumb-root">OpsAtlas</span>
            <span className="breadcrumb-sep">/</span>
            <b className="breadcrumb-current">{VIEW_TITLE[view]}</b>
          </div>
          <div className="topbar-actions">
            <HealthPill health={status.backend.state} />
            <button type="button" className="secondary-button topbar-signout-btn" onClick={onLogout}>
              Sign out
            </button>
          </div>
        </div>
        {view === "dashboard" ? (
          <DashboardView onSelect={select} />
        ) : view === "document" && anchor ? (
          <Suspense fallback={<div className="cm-canvas-loading">Opening the document…</div>}>
            <DocumentPage sourceId={anchor} backLabel={VIEW_TITLE[openedFrom.current]} onBack={() => select(openedFrom.current)} />
          </Suspense>
        ) : view === "sources" ? (
          <KnowledgeSourcesPage />
        ) : view === "ask" ? (
          <AskPage />
        ) : view === "avatar" ? (
          <AvatarLabPage />
        ) : view === "rag" ? (
          <RetrievalPage />
        ) : view === "governance" ? (
          <GovernancePage onResolveWithTibi={tibi ? resolveWithTibi : undefined} />
        ) : view === "processes" ? (
          <ProcessRegistryPage />
        ) : view === "operating-model" ? (
          <EnterpriseActivityModelPage />
        ) : view === "stress-lab" ? (
          <ProcessStressLabPage />
        ) : view === "analytics" ? (
          <AnalyticsPage />
        ) : view === "simulator" ? (
          <SimulatorPage />
        ) : view === "external" ? (
          <ExternalSourcesPage />
        ) : view === "system" ? (
          <SystemPage />
        ) : view === "tibi" ? (
          <TibiPage
            status={status.voice && status.voice !== "error" ? status.voice : tibi}
            mode={tibiMode}
            onOpenKnowledge={(record) => {
              setAnchor(record);
              setView("tibi-knowledge");
            }}
          />
        ) : view === "tibi-knowledge" ? (
          <TibiKnowledgePage focus={anchor} />
        ) : view === "tibi-conversations" ? (
          <ConversationsPage />
        ) : (
          <PlaceholderView view={view} />
        )}
      </main>
    </div>
  );
}
