import { useEffect, useMemo, useState } from "react";
import { getProcessStressTest, type ProcessStressReport, type ProcessStressResult } from "./api";

function scoreTone(score: number): "good" | "warn" {
  return score >= 70 ? "warn" : "good";
}

function ScoreCard({ label, value, note, tone }: { label: string; value: string; note: string; tone?: "good" | "warn" }) {
  return (
    <div className="result-card stress-score-card">
      <div className="result-head">
        <b>{value}</b>
        {tone ? <span className={`status-pill status-pill--${tone}`}>{tone}</span> : null}
      </div>
      <p className="result-cite">{label}</p>
      <p className="muted-text">{note}</p>
    </div>
  );
}

function riskLevel(row: ProcessStressResult): string {
  const score = Math.round((row.queue_pressure_score + row.rework_risk_score) / 2);
  if (score >= 75) return "High";
  if (score >= 50) return "Watch";
  return "Stable";
}

function sortByRisk(rows: ProcessStressResult[]) {
  return [...rows].sort((a, b) => {
    const bScore = b.queue_pressure_score + b.rework_risk_score + b.cycle_time_index;
    const aScore = a.queue_pressure_score + a.rework_risk_score + a.cycle_time_index;
    return bScore - aScore;
  });
}

export function ProcessStressLabPage() {
  const [stress, setStress] = useState<ProcessStressReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [scenario, setScenario] = useState<string>("all");

  useEffect(() => {
    getProcessStressTest()
      .then((report) => {
        setStress(report);
        setError(null);
      })
      .catch(() => {
        setStress(null);
        setError("Could not load process stress-test data.");
      });
  }, []);

  const filteredResults = useMemo(() => {
    if (!stress) return [];
    const rows = scenario === "all" ? stress.results : stress.results.filter((row) => row.scenario_id === scenario);
    return sortByRisk(rows);
  }, [scenario, stress]);

  if (error) {
    return (
      <div className="view-stack">
        <div className="page-intro">
          <h1>Process Stress Lab</h1>
          <p>Scenario testing for process pressure, bottlenecks and rework risk.</p>
        </div>
        <div className="empty-card"><b>Stress lab unavailable</b><span>{error}</span></div>
      </div>
    );
  }

  if (!stress) {
    return (
      <div className="view-stack">
        <div className="page-intro">
          <h1>Process Stress Lab</h1>
          <p>Scenario testing for process pressure, bottlenecks and rework risk.</p>
        </div>
        <div className="empty-card"><b>Loading stress lab</b><span>Building scenario results from the approved process registry.</span></div>
      </div>
    );
  }

  const highest = stress.highest_risk;
  const highRiskCount = stress.results.filter((row) => row.queue_pressure_score >= 70 || row.rework_risk_score >= 70).length;
  const averageQueue = stress.results.length
    ? Math.round(stress.results.reduce((total, row) => total + row.queue_pressure_score, 0) / stress.results.length)
    : 0;
  const averageRework = stress.results.length
    ? Math.round(stress.results.reduce((total, row) => total + row.rework_risk_score, 0) / stress.results.length)
    : 0;

  return (
    <div className="view-stack">
      <div className="page-intro">
        <h1>Process Stress Lab</h1>
        <p>Run deterministic scenario pressure tests across approved process records and use the metric guide to explain the result.</p>
      </div>

      <div className="analytics-metric-grid">
        <ScoreCard label="Processes" value={String(stress.process_count)} note="Approved process records included in the simulation." />
        <ScoreCard label="Scenarios" value={String(stress.scenario_count)} note="Baseline, demand, exception and staffing variants." />
        <ScoreCard label="High-risk rows" value={String(highRiskCount)} note="Scenario rows with queue or rework risk of 70+." tone={highRiskCount ? "warn" : "good"} />
        <ScoreCard label="Average queue" value={String(averageQueue)} note="Mean queue-pressure score across all scenario rows." tone={scoreTone(averageQueue)} />
        <ScoreCard label="Average rework" value={String(averageRework)} note="Mean rework-risk score across all scenario rows." tone={scoreTone(averageRework)} />
      </div>

      <div className="analytics-grid analytics-grid--two">
        <div className="panel">
          <div className="panel-heading">
            <div>
              <h2>Highest-risk signal</h2>
              <p className="muted-text">The strongest pressure point found across all current scenarios.</p>
            </div>
            <span className={`status-pill${highest && highest.queue_pressure_score >= 70 ? " status-pill--warn" : " status-pill--good"}`}>
              {highest ? riskLevel(highest) : "none"}
            </span>
          </div>
          {highest ? (
            <div className="result-list">
              <div className="result-card">
                <div className="result-head">
                  <b>{highest.process_name}</b>
                  <span className="status-pill">{highest.scenario_label}</span>
                </div>
                <p className="result-text">{highest.bottleneck_reason}</p>
                <p className="result-cite">
                  Queue {highest.queue_pressure_score} · Rework {highest.rework_risk_score} · Cycle index {highest.cycle_time_index}
                </p>
              </div>
              {highest.optimisation_actions.map((action) => (
                <div className="result-card" key={action}><p className="result-text">{action}</p></div>
              ))}
            </div>
          ) : (
            <p className="muted-text">No process records available for stress testing.</p>
          )}
        </div>

        <div className="panel">
          <div className="panel-heading">
            <div>
              <h2>Metric guide</h2>
              <p className="muted-text">How to explain the stress-lab numbers during UAT or stakeholder playback.</p>
            </div>
          </div>
          <div className="result-list stress-guide-list">
            {Object.entries(stress.rubric).map(([metric, description]) => (
              <div className="result-card" key={metric}>
                <div className="result-head"><b>{metric.replace(/_/g, " ")}</b></div>
                <p className="result-text">{description}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Scenario controls</h2>
            <p className="muted-text">Filter the result matrix by scenario and compare the simulated operating pressure.</p>
          </div>
          <label className="field-label stress-scenario-select">
            Scenario
            <select value={scenario} onChange={(event) => setScenario(event.target.value)}>
              <option value="all">All scenarios</option>
              {stress.scenarios.map((item) => <option key={item.scenario_id} value={item.scenario_id}>{item.label}</option>)}
            </select>
          </label>
        </div>
        <div className="stress-scenario-grid">
          {stress.scenarios.map((item) => (
            <button
              key={item.scenario_id}
              type="button"
              className={`stress-scenario-card${scenario === item.scenario_id ? " stress-scenario-card--active" : ""}`}
              onClick={() => setScenario(item.scenario_id)}
            >
              <b>{item.label}</b>
              <span>Demand x{item.demand_multiplier}</span>
              <span>Exception {Math.round(item.exception_rate * 100)}%</span>
              <span>Staffing x{item.staffing_factor}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Stress result matrix</h2>
            <p className="muted-text">Sorted by combined queue, rework and cycle-time pressure.</p>
          </div>
          <span className="status-pill">{filteredResults.length} rows</span>
        </div>
        <div className="table-frame stress-table-frame">
          <table className="data-table stress-result-table">
            <thead>
              <tr>
                <th>Process</th><th>Scenario</th><th>Cycle</th><th>Queue</th><th>Rework</th><th>Bottleneck</th><th>Recommended action</th>
              </tr>
            </thead>
            <tbody>
              {filteredResults.map((row) => (
                <tr key={`${row.process_id}-${row.scenario_id}`}>
                  <td><b>{row.process_name}</b><p className="result-cite">{row.bottleneck_reason}</p></td>
                  <td>{row.scenario_label}</td>
                  <td>{row.cycle_time_index}</td>
                  <td><span className={`status-pill status-pill--${scoreTone(row.queue_pressure_score)}`}>{row.queue_pressure_score}</span></td>
                  <td><span className={`status-pill status-pill--${scoreTone(row.rework_risk_score)}`}>{row.rework_risk_score}</span></td>
                  <td>{row.bottleneck_role}</td>
                  <td>{row.optimisation_actions.join("; ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Rule-set diagnostics</h2>
            <p className="muted-text">Signals used to score each process before scenario pressure is applied.</p>
          </div>
        </div>
        <div className="result-list stress-rule-grid">
          {stress.rules.map((rule) => (
            <div className="result-card" key={rule.process_id}>
              <div className="result-head">
                <b>{rule.process_name}</b>
                <span className="status-pill">{rule.handoff_count} hand-offs</span>
              </div>
              <p className="result-cite">{rule.source_title}</p>
              <p className="result-text">
                Roles {rule.role_count} · systems {rule.system_count} · dependencies {rule.dependency_count} · controls {rule.control_count} · validation gates {rule.validation_gate_count}
              </p>
              <p className="result-cite">Bottleneck candidate: {rule.dominant_role || "unassigned"}</p>
              <div className="stress-factor-list">
                {rule.stress_factors.map((factor) => <span className="status-pill" key={factor}>{factor}</span>)}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
