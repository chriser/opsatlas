import { useEffect, useState } from "react";
import { AUTH_INVALID_EVENT, getScorecard, isAuthenticated, logout, type Scorecard } from "./api";
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
  | "system";

interface NavItem {
  type: "item";
  key: ViewKey;
  label: string;
  summary: string;
  icon: string;
}

interface NavGroup {
  type: "group";
  id: string;
  label: string;
  summary: string;
  icon: string;
  children: Omit<NavItem, "type">[];
}

type NavEntry = NavItem | NavGroup;

const NAV_ITEMS: NavEntry[] = [
  { type: "item", key: "dashboard", label: "Dashboard", summary: "Platform overview & quick actions", icon: "D" },
  {
    type: "group",
    id: "ask",
    label: "Ask",
    summary: "Digital, written & citation workflows",
    icon: "A",
    children: [
      { key: "avatar", label: "Ask Digital SME", summary: "Spoken answers through the avatar", icon: "D" },
      { key: "ask", label: "Written Query", summary: "Grounded written answers", icon: "W" },
      { key: "rag", label: "Citation Check", summary: "Inspect retrieved evidence", icon: "C" },
    ],
  },
  { type: "item", key: "governance", label: "Governance", summary: "Duplicates, conflicts & regulation checks", icon: "G" },
  { type: "item", key: "operating-model", label: "Enterprise Activity Model", summary: "Ontology-backed activity canvas", icon: "E" },
  { type: "item", key: "analytics", label: "Analytics", summary: "Demand, quality & insight charts", icon: "I" },
  {
    type: "group",
    id: "system",
    label: "System",
    summary: "Models, sources & diagnostics",
    icon: "S",
    children: [
      { key: "system", label: "System Overview", summary: "Models & diagnostics", icon: "S" },
      { key: "sources", label: "Knowledge Sources", summary: "Upload & manage source documents", icon: "K" },
      { key: "external", label: "External Sources", summary: "Public UK source snapshots", icon: "E" },
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
};

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

function Sidebar({ view, onSelect }: { view: ViewKey; onSelect: (v: ViewKey) => void }) {
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

  return (
    <aside className="sidebar">
      <div className="brand-block">
        <BrandMark />
      </div>
      <nav className="sidebar-nav">
        {NAV_ITEMS.map((item) => {
          if (item.type === "group") {
            const active = item.children.some((child) => child.key === view);
            const open = openGroup === item.id;
            return (
              <div key={item.id} className={`sidebar-group${open ? " sidebar-group--open" : ""}`}>
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
            );
          }
          return (
            <button
              key={item.key}
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
          );
        })}
      </nav>
      <div className="sidebar-footer">
        <span>OpsAtlas</span>
        <b>Control Panel</b>
      </div>
    </aside>
  );
}

function DashboardView({ onSelect }: { onSelect: (v: ViewKey) => void }) {
  const quick: { key: ViewKey; icon: string; title: string; sub: string; primary?: boolean }[] = [
    { key: "sources", icon: "+", title: "Upload a document", sub: "Add anonymised source material", primary: true },
    { key: "governance", icon: "!", title: "Review conflicts", sub: "Duplicates & regulation flags" },
    { key: "rag", icon: "C", title: "Check citations", sub: "Inspect retrieved evidence" },
  ];
  const [card, setCard] = useState<Scorecard | null>(null);
  useEffect(() => {
    getScorecard().then(setCard).catch(() => setCard(null));
  }, []);
  const metrics = card
    ? [
        { label: "Queries", value: String(card.total_queries) },
        { label: "Answer rate", value: `${Math.round(card.answer_rate * 100)}%` },
        { label: "Grounded rate", value: `${Math.round(card.grounded_rate * 100)}%` },
        { label: "Avg citations", value: String(card.avg_citations) },
      ]
    : [];
  return (
    <div className="view-stack">
      <div className="page-intro">
        <h1>Welcome back</h1>
        <p>Manage the knowledge base lifecycle: ingest, govern and make source material queryable.</p>
      </div>
      <div className="dashboard-grid">
        <div className="column-stack">
          <div className="panel">
            <div className="panel-heading">
              <div>
                <h2>Quick actions</h2>
                <p className="muted-text">Jump into the most common tasks.</p>
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
                <h2>Assistant scorecard</h2>
                <p className="muted-text">Usage quality across all questions asked.</p>
              </div>
              <span className="status-pill">{card ? `${card.total_queries} queries` : "…"}</span>
            </div>
            {card && card.total_queries > 0 ? (
              <div className="result-list" style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 12 }}>
                {metrics.map((m) => (
                  <div className="result-card" key={m.label}>
                    <div className="result-head">
                      <b style={{ fontSize: 24 }}>{m.value}</b>
                    </div>
                    <p className="result-cite">{m.label}</p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty-card">
                <b>No questions asked yet</b>
                <span>Ask the assistant something to start building the scorecard.</span>
              </div>
            )}
          </div>
          {card && Object.keys(card.by_topic).length > 0 ? (
            <div className="panel">
              <div className="panel-heading">
                <div>
                  <h2>Questions by topic</h2>
                  <p className="muted-text">What people ask about most.</p>
                </div>
              </div>
              <div className="result-list">
                {Object.entries(card.by_topic).map(([topic, n]) => (
                  <div className="result-card" key={topic}>
                    <div className="result-head">
                      <b>{topic.replace(/_/g, " ")}</b>
                      <span className="status-pill">{n}</span>
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
  const [view, setView] = useState<ViewKey>("dashboard");
  const [authed, setAuthed] = useState(isAuthenticated());
  const health = useBackendHealth();

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
      <Sidebar view={view} onSelect={setView} />
      <main className="content-shell">
        <div className="topbar">
          <b>{VIEW_TITLE[view]}</b>
          <div className="topbar-actions">
            <HealthPill health={health} />
          </div>
          <button type="button" className="secondary-button" onClick={onLogout}>
            Sign out
          </button>
        </div>
        {view === "dashboard" ? (
          <DashboardView onSelect={setView} />
        ) : view === "sources" ? (
          <KnowledgeSourcesPage />
        ) : view === "ask" ? (
          <AskPage />
        ) : view === "avatar" ? (
          <AvatarLabPage />
        ) : view === "rag" ? (
          <RetrievalPage />
        ) : view === "governance" ? (
          <GovernancePage />
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
        ) : (
          <PlaceholderView view={view} />
        )}
      </main>
    </div>
  );
}
