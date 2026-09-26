import { useEffect, useState } from "react";
import { AUTH_INVALID_EVENT, getScorecard, getTibiStatus, isAuthenticated, logout, type Scorecard, type TibiStatus } from "./api";
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
import { TibiPage, type TibiMode } from "./TibiPage";
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
  | "tibi-knowledge";

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
};

const VIEWS = new Set<string>(Object.keys(VIEW_TITLE));

/** "#tibi-knowledge:overview" opens Tibi knowledge at the record "overview"; links from Tibi use it. */
function viewFromHash(): { view: ViewKey; anchor?: string } | null {
  const [view, anchor] = decodeURIComponent(window.location.hash.slice(1)).split(":");
  return VIEWS.has(view) ? { view: view as ViewKey, anchor } : null;
}

type Health = "checking" | "online" | "offline";

function useBackendHealth(): Health {
  const [health, setHealth] = useState<Health>("checking");
  useEffect(() => {
    let active = true;
    fetch("/api/health")
      .then((r) => {
        if (active) setHealth(r.ok ? "online" : "offline");
      })
      .catch(() => {
        if (active) setHealth("offline");
      });
    return () => {
      active = false;
    };
  }, []);
  return health;
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

function Sidebar({ view, onSelect, hidden }: { view: ViewKey; onSelect: (v: ViewKey) => void; hidden: string[] }) {
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
          <span>OP</span>
          <span className="operator-status-square" title="System Online" />
        </div>
        <div className="operator-meta">
          <span className="operator-role">PLATFORM OPERATOR</span>
          <span className="operator-name">OpsAtlas Console</span>
        </div>
      </div>

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

      <div className="sidebar-docked-card">
        <div className="sidebar-docked-header">
          <span className="sidebar-docked-badge">LOCAL READY</span>
        </div>
        <b>Local Architecture</b>
        <p>Local Ollama, vector search & compliance reasoner online.</p>
        <button
          type="button"
          className="sidebar-docked-button"
          onClick={() => onSelect(hidden.includes("tibi") ? "ask" : "tibi")}
        >
          {hidden.includes("tibi") ? "Test Query →" : "Talk with Tibi →"}
        </button>
      </div>

      <div className="sidebar-footer">
        <span>OpsAtlas</span>
        <b>Control Panel</b>
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
          <div className="kpi-value">{card ? card.total_queries : 0}</div>
          <div className="kpi-sub">Questions processed</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-card-head">
            <span className="kpi-label">Answer Rate</span>
            <span className="kpi-badge status-pill--good">Resolution</span>
          </div>
          <div className="kpi-value">{card && card.total_queries > 0 ? `${Math.round(card.answer_rate * 100)}%` : "100%"}</div>
          <div className="kpi-sub">Knowledge answers resolved</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-card-head">
            <span className="kpi-label">Grounded Rate</span>
            <span className="kpi-badge status-pill--purple">Evidence</span>
          </div>
          <div className="kpi-value">{card && card.total_queries > 0 ? `${Math.round(card.grounded_rate * 100)}%` : "100%"}</div>
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

          <div className="panel">
            <div className="panel-heading">
              <div>
                <h2>Local Engine Status</h2>
                <p className="muted-text">Subsystem & microservice readiness.</p>
              </div>
              <span className="status-pill status-pill--good">All Active</span>
            </div>
            <div style={{ display: "grid", gap: 10 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 12px", background: "var(--soft)", border: "1px solid var(--line)" }}>
                <div>
                  <b style={{ fontSize: 13, display: "block" }}>FastAPI Gateway</b>
                  <small className="muted-text">Port :8010 • Auth & Core APIs</small>
                </div>
                <span className="status-pill status-pill--good">Online</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 12px", background: "var(--soft)", border: "1px solid var(--line)" }}>
                <div>
                  <b style={{ fontSize: 13, display: "block" }}>Compliance Microservice</b>
                  <small className="muted-text">Port :5310 • Reasoning engine</small>
                </div>
                <span className="status-pill status-pill--good">Ready</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 12px", background: "var(--soft)", border: "1px solid var(--line)" }}>
                <div>
                  <b style={{ fontSize: 13, display: "block" }}>Knowledge & Vector Index</b>
                  <small className="muted-text">SQLite & Document store</small>
                </div>
                <span className="status-pill status-pill--blue">Mounted</span>
              </div>
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
  const [authed, setAuthed] = useState(isAuthenticated());
  const [tibi, setTibi] = useState<TibiStatus | null>(null);
  const [tibiMode, setTibiMode] = useState<TibiMode>("recall");
  const health = useBackendHealth();

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
    await logout();
    setAuthed(false);
  }

  if (!authed) {
    return <LoginScreen onSuccess={() => setAuthed(true)} />;
  }

  return (
    <div className="console-shell">
      <Sidebar view={view} onSelect={select} hidden={tibi ? [] : ["tibi"]} />
      <main className="content-shell">
        <div className="topbar">
          <div className="topbar-breadcrumb">
            <span className="breadcrumb-root">OpsAtlas</span>
            <span className="breadcrumb-sep">/</span>
            <b className="breadcrumb-current">{VIEW_TITLE[view]}</b>
          </div>
          <div className="topbar-actions">
            <HealthPill health={health} />
            <button type="button" className="secondary-button topbar-signout-btn" onClick={onLogout}>
              Sign out
            </button>
          </div>
        </div>
        {view === "dashboard" ? (
          <DashboardView onSelect={select} />
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
            status={tibi}
            mode={tibiMode}
            onOpenKnowledge={(record) => {
              setAnchor(record);
              setView("tibi-knowledge");
            }}
          />
        ) : view === "tibi-knowledge" ? (
          <TibiKnowledgePage focus={anchor} />
        ) : (
          <PlaceholderView view={view} />
        )}
      </main>
    </div>
  );
}
