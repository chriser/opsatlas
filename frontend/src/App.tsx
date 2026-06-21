import { useEffect, useState } from "react";
import { getScorecard, isAuthenticated, logout, type Scorecard } from "./api";
import { AskPage } from "./AskPage";
import { GovernancePage } from "./GovernancePage";
import { KnowledgeSourcesPage } from "./KnowledgeSourcesPage";
import { LoginScreen } from "./LoginScreen";
import { RetrievalPage } from "./RetrievalPage";
import { SettingsPage } from "./SettingsPage";
import "./App.css";

type ViewKey = "dashboard" | "sources" | "ask" | "rag" | "governance" | "settings";

interface NavItem {
  key: ViewKey;
  label: string;
  summary: string;
  icon: string;
}

const NAV_ITEMS: NavItem[] = [
  { key: "dashboard", label: "Dashboard", summary: "Platform overview & knowledge health", icon: "D" },
  { key: "sources", label: "Knowledge Sources", summary: "Upload & manage source documents", icon: "K" },
  { key: "ask", label: "Ask", summary: "Grounded answers with citations", icon: "A" },
  { key: "rag", label: "Retrieval", summary: "Inspect passage retrieval (debug)", icon: "R" },
  { key: "governance", label: "Governance", summary: "Duplicates, conflicts & regulation checks", icon: "G" },
  { key: "settings", label: "Settings", summary: "Models, providers & diagnostics", icon: "S" },
];

const VIEW_TITLE: Record<ViewKey, string> = {
  dashboard: "Dashboard",
  sources: "Knowledge Sources",
  ask: "Ask",
  rag: "Retrieval",
  governance: "Governance",
  settings: "Settings",
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

function Sidebar({ view, onSelect }: { view: ViewKey; onSelect: (v: ViewKey) => void }) {
  return (
    <aside className="sidebar">
      <div className="brand-block">
        <p>
          Knowledge<span>.</span>
        </p>
      </div>
      <nav className="sidebar-nav">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.key}
            type="button"
            className={`sidebar-link${item.key === view ? " sidebar-link--active" : ""}`}
            onClick={() => onSelect(item.key)}
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
        ))}
      </nav>
      <div className="sidebar-footer">
        <span>Knowledge Platform</span>
        <b>Control Panel</b>
      </div>
    </aside>
  );
}

function DashboardView({ onSelect }: { onSelect: (v: ViewKey) => void }) {
  const quick: { key: ViewKey; icon: string; title: string; sub: string; primary?: boolean }[] = [
    { key: "sources", icon: "+", title: "Upload a document", sub: "Add anonymised source material", primary: true },
    { key: "governance", icon: "!", title: "Review conflicts", sub: "Duplicates & regulation flags" },
    { key: "rag", icon: "R", title: "Open RAG setup", sub: "Indexing & retrieval config" },
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
          <div className="panel">
            <div className="panel-heading">
              <div>
                <h2>Knowledge gaps</h2>
                <p className="muted-text">Questions the assistant could not answer from approved knowledge.</p>
              </div>
              <span className={`status-pill${card && card.knowledge_gaps.length ? " status-pill--warn" : " status-pill--good"}`}>
                {card ? card.knowledge_gaps.length : 0}
              </span>
            </div>
            {card && card.knowledge_gaps.length > 0 ? (
              <div className="result-list">
                {card.knowledge_gaps.map((q, i) => (
                  <div className="result-card" key={i}>
                    <p className="result-text">{q}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="muted-text">No knowledge gaps detected yet.</p>
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
  const item = NAV_ITEMS.find((n) => n.key === view)!;
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
        ) : view === "rag" ? (
          <RetrievalPage />
        ) : view === "governance" ? (
          <GovernancePage />
        ) : view === "settings" ? (
          <SettingsPage />
        ) : (
          <PlaceholderView view={view} />
        )}
      </main>
    </div>
  );
}
