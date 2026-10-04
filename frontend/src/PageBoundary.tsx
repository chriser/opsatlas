import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  onHome: () => void;
  /** The address within the page: when it changes, a shown error is cleared and the page tried again. */
  resetKey: string;
}

/** One page's error stays on that page (AUDIT F4): the menu, the service status and every other page keep working. */
export class PageBoundary extends Component<Props, { error: Error | null }> {
  state: { error: Error | null } = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidUpdate(previous: Props) {
    if (previous.resetKey !== this.props.resetKey && this.state.error) this.setState({ error: null });
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("A page failed to render", error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="view-stack">
        <div className="page-intro">
          <h1>This page could not be shown</h1>
          <p>The rest of OpsAtlas still works. Try the page again, or go to the dashboard.</p>
        </div>
        <div className="panel">
          <div className="empty-card">
            <b>{this.state.error.message || "Unexpected error"}</b>
            <span>
              <button type="button" className="mini-button" onClick={() => this.setState({ error: null })}>
                Try again
              </button>{" "}
              <button type="button" className="mini-button" onClick={this.props.onHome}>
                Dashboard
              </button>
            </span>
          </div>
        </div>
      </div>
    );
  }
}
