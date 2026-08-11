import { useState } from "react";
import {
  approveOntologyProposal,
  askQuestion,
  declineOntologyProposal,
  resolveProcessDiagram,
  runOntologyInvestigation,
  type AgentRunTrace,
  type AnswerResponse,
  type PendingActionProposal,
  type ProcessDiagramContext,
} from "./api";
import { Markdown } from "./Markdown";
import { ProcessDiagramPanel } from "./ProcessDiagramPanel";

function answerPathLabel(path?: string): string {
  if (path === "oag") return "OAG";
  if (path === "rag+ontology") return "RAG + ontology";
  return "RAG";
}

export function AskPage() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<AnswerResponse | null>(null);
  const [investigation, setInvestigation] = useState<AgentRunTrace | null>(null);
  const [investigate, setInvestigate] = useState(false);
  const [diagram, setDiagram] = useState<ProcessDiagramContext | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [diagramBusy, setDiagramBusy] = useState(false);
  const [proposalBusy, setProposalBusy] = useState<string | null>(null);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!question.trim()) return;
    const asked = question.trim();
    setBusy(true);
    setDiagram(null);
    setInvestigation(null);
    setError(null);
    try {
      if (investigate) {
        setResult(null);
        setInvestigation(await runOntologyInvestigation(asked));
        return;
      }
      const answer = await askQuestion(asked);
      setResult(answer);
      setBusy(false);
      setDiagramBusy(true);
      try {
        setDiagram(await resolveProcessDiagram(asked, answer.citations));
      } catch (err) {
        setDiagram({
          status: "unavailable",
          message: err instanceof Error ? err.message : "Could not load process map.",
          process_id: "",
          process_name: "",
          source_title: "",
          service_url: "",
          chart: null,
          svg: "",
        });
      } finally {
        setDiagramBusy(false);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed.");
      setResult(null);
      setDiagram(null);
    } finally {
      setBusy(false);
    }
  }

  async function onApproveProposal(proposalId: string) {
    setProposalBusy(proposalId);
    setError(null);
    try {
      const response = await approveOntologyProposal(proposalId);
      updateProposal(response.proposal);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not approve proposal.");
    } finally {
      setProposalBusy(null);
    }
  }

  async function onDeclineProposal(proposalId: string) {
    setProposalBusy(proposalId);
    setError(null);
    try {
      const response = await declineOntologyProposal(proposalId, "Declined from Ask investigation.");
      updateProposal(response.proposal);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not decline proposal.");
    } finally {
      setProposalBusy(null);
    }
  }

  function updateProposal(proposal: PendingActionProposal) {
    setInvestigation((current) => {
      if (!current) return current;
      const persisted = current.persisted_proposals ?? [];
      return {
        ...current,
        persisted_proposals: persisted.map((item) => (item.proposal_id === proposal.proposal_id ? proposal : item)),
        proposed_actions: current.proposed_actions.map((item) =>
          item.proposal_id === proposal.proposal_id ? { ...item, status: proposal.status } : item,
        ),
      };
    });
  }

  return (
    <div className="view-stack">
      <div className="page-intro">
        <h1>Written Query</h1>
        <p>Ask a written question and receive a grounded answer drawn only from the approved knowledge base, with citations.</p>
      </div>

      <div className="panel">
        <form className="search-row" onSubmit={onSubmit}>
          <input
            className="search-input"
            type="text"
            placeholder="e.g. What checks must pass before a supplier can be onboarded?"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
          />
          <button type="submit" className="primary-button" disabled={busy || !question.trim()}>
            {busy ? "Thinking…" : investigate ? "Investigate" : "Ask"}
          </button>
        </form>
        <label className="muted-text" style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 10 }}>
          <input type="checkbox" checked={investigate} onChange={(event) => setInvestigate(event.target.checked)} />
          Investigate with ontology agent
        </label>

        {error ? (
          <p className="muted-text" style={{ color: "var(--red)", marginTop: 12 }}>
            {error}
          </p>
        ) : null}

        {busy ? <p className="muted-text" style={{ marginTop: 14 }}>Generating a grounded answer…</p> : null}

        {investigation && !busy ? (
          <div className="result-list" style={{ marginTop: 16 }}>
            <div className="answer-card">
              <div className="result-head">
                <b>Investigation result</b>
                <span className="status-pill">{investigation.stopped_reason.replace("_", " ")}</span>
              </div>
              <div className="answer-text"><Markdown text={investigation.final_answer} /></div>
              <p className="result-cite">
                {investigation.steps.length} steps · {investigation.total_latency_ms} ms · run {investigation.run_id}
              </p>
            </div>

            {investigation.steps.length ? (
              <div className="result-card">
                <div className="result-head">
                  <b>Trace</b>
                  <span className="status-pill">{investigation.steps.length}</span>
                </div>
                <div className="result-list">
                  {investigation.steps.map((step, index) => (
                    <details className="result-card" key={`${step.tool}-${index}`}>
                      <summary>
                        <b>{step.tool}</b> · {step.result_summary}
                      </summary>
                      <pre className="result-cite" style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(step.args, null, 2)}</pre>
                    </details>
                  ))}
                </div>
              </div>
            ) : null}

            {(investigation.persisted_proposals ?? []).length ? (
              <div className="result-card">
                <div className="result-head">
                  <b>Proposed actions</b>
                  <span className="status-pill">{investigation.persisted_proposals?.length ?? 0}</span>
                </div>
                <div className="result-list">
                  {(investigation.persisted_proposals ?? []).map((proposal) => (
                    <div className="result-card" key={proposal.proposal_id}>
                      <div className="result-head">
                        <b>{proposal.action.replace(/_/g, " ")}</b>
                        <span className={`status-pill${proposal.status === "approved" ? " status-pill--good" : proposal.status === "declined" ? " status-pill--warn" : ""}`}>
                          {proposal.status}
                        </span>
                      </div>
                      <p className="result-text">{proposal.rationale}</p>
                      <pre className="result-cite" style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(proposal.params, null, 2)}</pre>
                      {proposal.execution_id ? <p className="result-cite">Execution: {proposal.execution_id}</p> : null}
                      {proposal.status === "pending" ? (
                        <div className="settings-service-actions">
                          <button
                            type="button"
                            className="primary-button"
                            disabled={proposalBusy === proposal.proposal_id}
                            onClick={() => void onApproveProposal(proposal.proposal_id)}
                          >
                            {proposalBusy === proposal.proposal_id ? "Approving..." : "Approve"}
                          </button>
                          <button
                            type="button"
                            className="secondary-button"
                            disabled={proposalBusy === proposal.proposal_id}
                            onClick={() => void onDeclineProposal(proposal.proposal_id)}
                          >
                            Decline
                          </button>
                        </div>
                      ) : null}
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        ) : null}

        {result && !busy ? (
          <div className="answer-diagram-grid" style={{ marginTop: 16 }}>
            <div>
              <div className={`answer-card${result.refused ? " answer-card--refused" : ""}`}>
                <div className="answer-text"><Markdown text={result.answer} /></div>
              </div>
              <p className="muted-text" style={{ marginTop: 10, display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                {result.refused ? (
                  <>No grounded answer · mode: <b>{result.mode}</b></>
                ) : (
                  <>
                    <span
                      className={`status-pill${result.confidence === "grounded" ? " status-pill--good" : " status-pill--warn"}`}
                    >
                      {result.confidence === "grounded" ? "grounded" : "unverified"}
                    </span>
                    <span className={`status-pill${result.answer_path === "oag" ? " status-pill--good" : ""}`}>
                      {answerPathLabel(result.answer_path)}
                    </span>
                    <span>mode: <b>{result.mode}</b></span>
                    {result.grounding && result.grounding !== "n/a" ? (
                      <span>· grounding: <b>{result.grounding}</b> ({Math.round(result.grounding_score * 100)}%)</span>
                    ) : null}
                    {result.faithfulness && result.faithfulness !== "n/a" ? (
                      <span>· faithfulness: <b>{result.faithfulness.replace("_", " ")}</b></span>
                    ) : null}
                  </>
                )}
              </p>
              {result.citations.length > 0 ? (
                <div style={{ marginTop: 8 }}>
                  <p className="muted-text" style={{ marginBottom: 8, fontWeight: 700 }}>Sources</p>
                  <div className="result-list">
                    {result.citations.map((c, i) => (
                      <div className="result-card" key={`${c.source_id}-${c.ordinal}-${i}`}>
                        <div className="result-head">
                          <b>{c.heading}</b>
                          <span className="status-pill">
                            {c.citation_type === "ontology_object" ? "object" : `section ${c.ordinal}`}
                          </span>
                        </div>
                        <p className="result-cite">{c.source_title}</p>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
            </div>
            <ProcessDiagramPanel diagram={diagram} loading={diagramBusy} />
          </div>
        ) : null}
      </div>
    </div>
  );
}
