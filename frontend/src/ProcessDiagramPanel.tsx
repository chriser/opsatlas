import type { ProcessDiagramContext } from "./api";

export function ProcessDiagramPanel({
  diagram,
  loading,
  title = "Related process map",
}: {
  diagram: ProcessDiagramContext | null;
  loading: boolean;
  title?: string;
}) {
  if (loading) {
    return (
      <div className="panel process-diagram-panel">
        <div className="panel-heading">
          <div>
            <h2>{title}</h2>
            <p className="muted-text">Checking for related process context...</p>
          </div>
          <span className="status-pill">loading</span>
        </div>
      </div>
    );
  }

  if (!diagram || diagram.status === "empty") {
    return (
      <div className="panel process-diagram-panel">
        <div className="panel-heading">
          <div>
            <h2>{title}</h2>
            <p className="muted-text">{diagram?.message || "No related process map is available for this answer."}</p>
          </div>
          <span className="status-pill">no map</span>
        </div>
      </div>
    );
  }

  if (diagram.status !== "available") {
    return (
      <div className="panel process-diagram-panel">
        <div className="panel-heading">
          <div>
            <h2>{title}</h2>
            <p className="muted-text">{diagram.message}</p>
          </div>
          <span className="status-pill status-pill--warn">unavailable</span>
        </div>
        {diagram.process_name ? <p className="result-cite">{diagram.process_name}</p> : null}
      </div>
    );
  }

  return (
    <div className="panel process-diagram-panel">
      <div className="panel-heading">
        <div>
          <h2>{title}</h2>
          <p className="muted-text">{diagram.process_name}</p>
        </div>
        <span className="status-pill status-pill--good">local</span>
      </div>
      <div className="process-diagram-frame" dangerouslySetInnerHTML={{ __html: diagram.svg }} />
      <p className="result-cite">
        {diagram.source_title || "Process registry"} · {diagram.service_url || "local diagram service"}
      </p>
    </div>
  );
}

