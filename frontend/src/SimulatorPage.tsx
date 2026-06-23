import { useEffect, useMemo, useState } from "react";
import {
  getSimulatorCatalogue,
  listSimulationRuns,
  runHistoricalSimulation,
  replaySimulationRun,
  runSimulation,
  type SimulationRun,
  type SimulatorCatalogue,
} from "./api";

function formatDate(iso: string): string {
  if (!iso) return "";
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString();
}

function pct(value: number, total: number): string {
  return total ? `${Math.round((value / total) * 100)}%` : "0%";
}

export function SimulatorPage() {
  const [catalogue, setCatalogue] = useState<SimulatorCatalogue | null>(null);
  const [runs, setRuns] = useState<SimulationRun[]>([]);
  const [latest, setLatest] = useState<SimulationRun | null>(null);
  const [scenarioId, setScenarioId] = useState("");
  const [personaId, setPersonaId] = useState("");
  const [seed, setSeed] = useState("42");
  const [maxQuestions, setMaxQuestions] = useState("6");
  const [topK, setTopK] = useState("5");
  const [periodPreset, setPeriodPreset] = useState<"last_7_days" | "last_30_days" | "last_90_days" | "custom">("last_30_days");
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [usageDensity, setUsageDensity] = useState<"light" | "moderate" | "heavy">("moderate");
  const [usagePattern, setUsagePattern] = useState<"steady" | "weekday_peak" | "ramp_up" | "month_end">("weekday_peak");
  const [periodCap, setPeriodCap] = useState("120");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    const [catalogueData, runRows] = await Promise.all([getSimulatorCatalogue(), listSimulationRuns()]);
    setCatalogue(catalogueData);
    setRuns(runRows);
    setLatest((current) => current ?? runRows[0] ?? null);
  }

  useEffect(() => {
    refresh().catch(() => setError("Could not load simulator data."));
  }, []);

  const personaById = useMemo(() => new Map((catalogue?.personas ?? []).map((persona) => [persona.persona_id, persona])), [catalogue]);
  const visibleScenarios = useMemo(() => {
    const scenarios = catalogue?.scenarios ?? [];
    return personaId ? scenarios.filter((scenario) => scenario.persona_id === personaId) : scenarios;
  }, [catalogue, personaId]);
  const selectedQuestionTotal = useMemo(() => {
    const scenarios = catalogue?.scenarios ?? [];
    const selected = scenarioId
      ? scenarios.filter((scenario) => scenario.scenario_id === scenarioId)
      : visibleScenarios;
    return selected.reduce((total, scenario) => total + scenario.questions.length, 0);
  }, [catalogue, scenarioId, visibleScenarios]);

  async function onRun(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const run = await runSimulation({
        scenario_ids: scenarioId ? [scenarioId] : [],
        persona_ids: !scenarioId && personaId ? [personaId] : [],
        seed: seed.trim() ? Number(seed) : undefined,
        max_questions: maxQuestions.trim() ? Number(maxQuestions) : undefined,
        top_k: topK.trim() ? Number(topK) : undefined,
      });
      setLatest(run);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Simulation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function onReplay(runId: string) {
    setBusy(true);
    setError(null);
    try {
      const run = await replaySimulationRun(runId);
      setLatest(run);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Simulation replay failed.");
    } finally {
      setBusy(false);
    }
  }

  async function onPeriodRun(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const run = await runHistoricalSimulation({
        scenario_ids: scenarioId ? [scenarioId] : [],
        persona_ids: !scenarioId && personaId ? [personaId] : [],
        seed: seed.trim() ? Number(seed) : undefined,
        max_questions: periodCap.trim() ? Number(periodCap) : undefined,
        preset_period: periodPreset,
        start_date: periodPreset === "custom" ? periodStart : "",
        end_date: periodPreset === "custom" ? periodEnd : "",
        usage_density: usageDensity,
        usage_pattern: usagePattern,
      });
      setLatest(run);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Historical simulation failed.");
    } finally {
      setBusy(false);
    }
  }

  function runType(run: SimulationRun): string {
    if (run.qa.synthetic_historical) return "Period batch";
    if (run.qa.replay_of_run_id) return "Replay";
    return "Single run";
  }

  const summary = latest?.summary;
  const qa = latest?.qa;
  const kpis = summary
    ? [
        { label: "Questions", value: String(summary.total_questions) },
        { label: "Answered", value: String(summary.answered) },
        { label: "Refused", value: String(summary.refused) },
        { label: "Declined", value: String(summary.declined) },
        { label: "Guardrails", value: String(summary.guardrail_blocks) },
        { label: "Matches", value: pct(summary.expectation_matches, summary.total_questions) },
        { label: "Avg latency", value: `${summary.average_latency_ms} ms` },
      ]
    : [
        { label: "Personas", value: String(catalogue?.personas.length ?? 0) },
        { label: "Scenarios", value: String(catalogue?.scenarios.length ?? 0) },
        { label: "Runs", value: String(runs.length) },
      ];

  return (
    <div className="view-stack">
      <div className="page-intro">
        <h1>Simulator</h1>
        <p>Run synthetic pilot journeys through the same grounded assistant path as normal Ask traffic.</p>
      </div>

      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Run configuration</h2>
            <p className="muted-text">{catalogue ? `${catalogue.personas.length} personas · ${catalogue.scenarios.length} scenarios` : "Loading catalogue..."}</p>
          </div>
          <span className="status-pill">{runs.length} runs</span>
        </div>
        <form
          onSubmit={onRun}
          style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr)) auto", gap: 10, alignItems: "end" }}
        >
          <label className="muted-text" style={{ display: "grid", gap: 6, fontSize: 12, fontWeight: 800 }}>
            Persona
            <select
              value={personaId}
              onChange={(event) => {
                setPersonaId(event.target.value);
                setScenarioId("");
              }}
              style={{ border: "1px solid var(--line)", borderRadius: 8, padding: "12px 14px" }}
            >
              <option value="">All personas</option>
              {(catalogue?.personas ?? []).map((persona) => (
                <option value={persona.persona_id} key={persona.persona_id}>{persona.display_name}</option>
              ))}
            </select>
          </label>
          <label className="muted-text" style={{ display: "grid", gap: 6, fontSize: 12, fontWeight: 800 }}>
            Scenario
            <select
              value={scenarioId}
              onChange={(event) => setScenarioId(event.target.value)}
              style={{ border: "1px solid var(--line)", borderRadius: 8, padding: "12px 14px" }}
            >
              <option value="">All matching scenarios</option>
              {visibleScenarios.map((scenario) => (
                <option value={scenario.scenario_id} key={scenario.scenario_id}>{scenario.journey}</option>
              ))}
            </select>
          </label>
          <label className="muted-text" style={{ display: "grid", gap: 6, fontSize: 12, fontWeight: 800 }}>
            Seed
            <input value={seed} onChange={(event) => setSeed(event.target.value)} style={{ border: "1px solid var(--line)", borderRadius: 8, padding: "12px 14px" }} />
          </label>
          <label className="muted-text" style={{ display: "grid", gap: 6, fontSize: 12, fontWeight: 800 }}>
            Question cap
            <input value={maxQuestions} onChange={(event) => setMaxQuestions(event.target.value)} style={{ border: "1px solid var(--line)", borderRadius: 8, padding: "12px 14px" }} />
          </label>
          <label className="muted-text" style={{ display: "grid", gap: 6, fontSize: 12, fontWeight: 800 }}>
            Top K
            <input value={topK} onChange={(event) => setTopK(event.target.value)} style={{ border: "1px solid var(--line)", borderRadius: 8, padding: "12px 14px" }} />
          </label>
          <button type="submit" className="primary-button" disabled={busy || !catalogue}>
            {busy ? "Running..." : "Run"}
          </button>
        </form>
        <p className="result-cite">
          {selectedQuestionTotal
            ? `${selectedQuestionTotal} matching catalogue questions are available. The cap limits the run; it does not create extra questions beyond the selected persona/scenario pool.`
            : "Select a persona or scenario to see how many catalogue questions are available for the run."}
        </p>
        {error ? <p className="muted-text" style={{ color: "var(--red)", marginTop: 12 }}>{error}</p> : null}
      </div>

      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Historical period batch</h2>
            <p className="muted-text">Generate synthetic dated usage for trend-chart and value-projection testing.</p>
          </div>
          <span className="status-pill">{usageDensity}</span>
        </div>
        <form
          onSubmit={onPeriodRun}
          style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr)) auto", gap: 10, alignItems: "end" }}
        >
          <label className="field-label">
            Period
            <select value={periodPreset} onChange={(event) => setPeriodPreset(event.target.value as typeof periodPreset)}>
              <option value="last_7_days">Last 7 days</option>
              <option value="last_30_days">Last 30 days</option>
              <option value="last_90_days">Last 90 days</option>
              <option value="custom">Custom range</option>
            </select>
          </label>
          <label className="field-label">
            Start date
            <input type="date" value={periodStart} disabled={periodPreset !== "custom"} onChange={(event) => setPeriodStart(event.target.value)} />
          </label>
          <label className="field-label">
            End date
            <input type="date" value={periodEnd} disabled={periodPreset !== "custom"} onChange={(event) => setPeriodEnd(event.target.value)} />
          </label>
          <label className="field-label">
            Density
            <select value={usageDensity} onChange={(event) => setUsageDensity(event.target.value as typeof usageDensity)}>
              <option value="light">Light</option>
              <option value="moderate">Moderate</option>
              <option value="heavy">Heavy</option>
            </select>
          </label>
          <label className="field-label">
            Pattern
            <select value={usagePattern} onChange={(event) => setUsagePattern(event.target.value as typeof usagePattern)}>
              <option value="steady">Steady</option>
              <option value="weekday_peak">Weekday peak</option>
              <option value="ramp_up">Ramp up</option>
              <option value="month_end">Month end</option>
            </select>
          </label>
          <label className="field-label">
            Batch cap
            <input value={periodCap} onChange={(event) => setPeriodCap(event.target.value)} />
          </label>
          <button type="submit" className="secondary-button" disabled={busy || !catalogue}>
            {busy ? "Generating..." : "Generate"}
          </button>
        </form>
        <p className="result-cite">
          Period batches use the selected persona/scenario filters above, write past synthetic timestamps, and are not replayable single-run QA tests.
        </p>
      </div>

      <div className="panel">
        <div className="result-list" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: 12 }}>
          {kpis.map((metric) => (
            <div className="result-card" key={metric.label}>
              <div className="result-head"><b style={{ fontSize: 22 }}>{metric.value}</b></div>
              <p className="result-cite">{metric.label}</p>
            </div>
          ))}
        </div>
      </div>

      {latest ? (
        <div className="panel">
          <div className="panel-heading">
            <div>
              <h2>Latest run</h2>
              <p className="muted-text">
                {formatDate(latest.completed_at)} · {runType(latest)} · {latest.scenario_count} scenarios · {latest.run_id.slice(0, 10)}
              </p>
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8, justifyContent: "flex-end" }}>
              <button type="button" className="secondary-button" disabled={busy || !latest.qa.replayable} onClick={() => onReplay(latest.run_id)}>
                {busy ? "Working..." : "Replay"}
              </button>
              <span className="status-pill status-pill--good">{latest.summary.expectation_matches} matches</span>
            </div>
          </div>
          {qa ? (
            <div className="result-list" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12, marginBottom: 14 }}>
              <div className="result-card">
                <div className="result-head"><b>{qa.synthetic_historical ? "Historical" : qa.synthetic_only ? "Synthetic" : "Mixed"}</b></div>
                <p className="result-cite">Traffic source</p>
              </div>
              <div className="result-card">
                <div className="result-head"><b>{qa.actor_type}</b></div>
                <p className="result-cite">Actor type</p>
              </div>
              <div className="result-card">
                <div className="result-head"><b>{qa.selected_question_ids.length}</b></div>
                <p className="result-cite">Replay questions</p>
              </div>
              <div className="result-card">
                <div className="result-head"><b>{qa.question_fingerprint.slice(0, 10)}</b></div>
                <p className="result-cite">Question set</p>
              </div>
              <div className="result-card">
                <div className="result-head"><b>{qa.replay_fingerprint.slice(0, 10)}</b></div>
                <p className="result-cite">Replay config</p>
              </div>
              <div className="result-card">
                <div className="result-head"><b>{qa.replay_of_run_id ? qa.replay_of_run_id.slice(0, 10) : "Original"}</b></div>
                <p className="result-cite">Replay link</p>
              </div>
              <div className="result-card">
                <div className="result-head"><b>{qa.synthetic_historical ? `${qa.period_start} to ${qa.period_end}` : "n/a"}</b></div>
                <p className="result-cite">Historical period</p>
              </div>
              <div className="result-card">
                <div className="result-head"><b>{qa.synthetic_historical ? `${qa.usage_density} / ${qa.usage_pattern.replace(/_/g, " ")}` : "n/a"}</b></div>
                <p className="result-cite">Density pattern</p>
              </div>
            </div>
          ) : null}
          <div className="table-frame">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Persona</th>
                  <th>Timestamp</th>
                  <th>Question</th>
                  <th>Expected</th>
                  <th>Observed</th>
                  <th>Citations</th>
                  <th>Latency</th>
                </tr>
              </thead>
              <tbody>
                {latest.results.map((result) => (
                  <tr key={`${result.scenario_id}-${result.question_id}`}>
                    <td>{personaById.get(result.persona_id)?.display_name ?? result.persona_id}</td>
                    <td>{result.timestamp ? formatDate(result.timestamp) : "n/a"}</td>
                    <td>{result.question}</td>
                    <td>{result.expected_behavior}</td>
                    <td>
                      <span className={`status-pill${result.matched_expectation ? " status-pill--good" : " status-pill--warn"}`}>
                        {result.observed_behavior}
                      </span>
                    </td>
                    <td>{result.citation_count}</td>
                    <td>{result.latency_ms} ms</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Recent runs</h2>
            <p className="muted-text">Single runs remain replayable; historical batches are synthetic trend data.</p>
          </div>
          <span className="status-pill">{runs.length} stored</span>
        </div>
        {runs.length ? (
          <div className="table-frame">
            <table className="data-table">
              <thead>
                <tr><th>Completed</th><th>Type</th><th>Period</th><th>Density</th><th>Questions</th><th>Replay</th></tr>
              </thead>
              <tbody>
                {runs.slice(0, 8).map((run) => (
                  <tr key={run.run_id}>
                    <td>{formatDate(run.completed_at)}</td>
                    <td>{runType(run)}</td>
                    <td>{run.qa.synthetic_historical ? `${run.qa.period_start} to ${run.qa.period_end}` : "n/a"}</td>
                    <td>{run.qa.synthetic_historical ? `${run.qa.usage_density} / ${run.qa.usage_pattern.replace(/_/g, " ")}` : "n/a"}</td>
                    <td>{run.summary.total_questions}</td>
                    <td>
                      <button
                        type="button"
                        className="text-button"
                        disabled={busy || !run.qa.replayable}
                        onClick={() => onReplay(run.run_id)}
                      >
                        Replay
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="muted-text">No simulator runs recorded yet.</p>
        )}
      </div>

      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Scenario catalogue</h2>
            <p className="muted-text">Personas, journeys, process areas and expected outcomes.</p>
          </div>
        </div>
        {catalogue ? (
          <div className="table-frame">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Journey</th>
                  <th>Persona</th>
                  <th>Process</th>
                  <th>Difficulty</th>
                  <th>Questions</th>
                  <th>Outcome</th>
                </tr>
              </thead>
              <tbody>
                {catalogue.scenarios.map((scenario) => (
                  <tr key={scenario.scenario_id}>
                    <td>{scenario.journey}</td>
                    <td>{personaById.get(scenario.persona_id)?.display_name ?? scenario.persona_id}</td>
                    <td>{scenario.process_area}</td>
                    <td>{scenario.difficulty}</td>
                    <td>{scenario.questions.length}</td>
                    <td>{scenario.expected_outcome.replace(/_/g, " ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="muted-text">Loading...</p>
        )}
      </div>
    </div>
  );
}
