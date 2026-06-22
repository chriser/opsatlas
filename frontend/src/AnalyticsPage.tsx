import { useEffect, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { getAnalyticsCharts, getScorecard, type ChartData, type Scorecard } from "./api";

const COLORS = ["#16a34a", "#dc2626", "#d97706", "#2563eb", "#7c3aed", "#db2777", "#0891b2", "#65a30d"];

function ChartCard({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div className="panel" style={{ minWidth: 0 }}>
      <div className="panel-heading">
        <div>
          <h2 style={{ fontSize: 15 }}>{title}</h2>
          {subtitle ? <p className="muted-text">{subtitle}</p> : null}
        </div>
      </div>
      <ResponsiveContainer width="100%" height={220}>{children as React.ReactElement}</ResponsiveContainer>
    </div>
  );
}

export function AnalyticsPage() {
  const [card, setCard] = useState<Scorecard | null>(null);
  const [data, setData] = useState<ChartData | null>(null);

  useEffect(() => {
    getScorecard().then(setCard).catch(() => setCard(null));
    getAnalyticsCharts().then(setData).catch(() => setData(null));
  }, []);

  const kpis = card
    ? [
        { label: "Queries", value: String(card.total_queries) },
        { label: "Answer rate", value: `${Math.round(card.answer_rate * 100)}%` },
        { label: "Grounded rate", value: `${Math.round(card.grounded_rate * 100)}%` },
        { label: "Avg citations", value: String(card.avg_citations) },
        { label: "Knowledge gaps", value: String(card.knowledge_gaps.length) },
      ]
    : [];

  return (
    <div className="view-stack">
      <div className="page-intro">
        <h1>Analytics</h1>
        <p>Descriptive insight into knowledge demand and answer quality. Diagnostic and predictive tiers follow.</p>
      </div>

      <div className="panel">
        <div className="result-list" style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 12 }}>
          {kpis.map((m) => (
            <div className="result-card" key={m.label}>
              <div className="result-head"><b style={{ fontSize: 22 }}>{m.value}</b></div>
              <p className="result-cite">{m.label}</p>
            </div>
          ))}
        </div>
      </div>

      {!data ? (
        <p className="muted-text">Loading charts…</p>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 16 }}>
          <ChartCard title="Query volume over time" subtitle="Daily demand">
            <LineChart data={data.volume_over_time}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border, #e2e8f0)" />
              <XAxis dataKey="date" fontSize={11} /><YAxis allowDecimals={false} fontSize={11} />
              <Tooltip /><Line type="monotone" dataKey="queries" stroke="#2563eb" strokeWidth={2} />
            </LineChart>
          </ChartCard>

          <ChartCard title="Demand by topic" subtitle="What people ask about">
            <BarChart data={data.by_topic}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border, #e2e8f0)" />
              <XAxis dataKey="topic" fontSize={10} interval={0} angle={-20} textAnchor="end" height={50} />
              <YAxis allowDecimals={false} fontSize={11} /><Tooltip />
              <Bar dataKey="count" fill="#7c3aed" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ChartCard>

          <ChartCard title="Outcomes" subtitle="Answered vs refused vs guardrail">
            <PieChart>
              <Pie data={data.outcomes} dataKey="value" nameKey="name" outerRadius={75} label>
                {data.outcomes.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Legend /><Tooltip />
            </PieChart>
          </ChartCard>

          <ChartCard title="Answer latency" subtitle="Response-time distribution">
            <BarChart data={data.latency}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border, #e2e8f0)" />
              <XAxis dataKey="bucket" fontSize={11} /><YAxis allowDecimals={false} fontSize={11} />
              <Tooltip /><Bar dataKey="count" fill="#0891b2" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ChartCard>

          <ChartCard title="Most-cited sources" subtitle="Evidence the assistant relies on">
            <BarChart data={data.top_sources} layout="vertical" margin={{ left: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border, #e2e8f0)" />
              <XAxis type="number" allowDecimals={false} fontSize={11} />
              <YAxis type="category" dataKey="source" width={150} fontSize={9} />
              <Tooltip /><Bar dataKey="citations" fill="#16a34a" radius={[0, 3, 3, 0]} />
            </BarChart>
          </ChartCard>

          <ChartCard title="Answer confidence" subtitle="Grounded vs unverified">
            <PieChart>
              <Pie data={data.confidence} dataKey="value" nameKey="name" outerRadius={75} label>
                {data.confidence.map((_, i) => <Cell key={i} fill={COLORS[(i + 2) % COLORS.length]} />)}
              </Pie>
              <Legend /><Tooltip />
            </PieChart>
          </ChartCard>
        </div>
      )}
    </div>
  );
}
