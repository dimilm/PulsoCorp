import { Component, ErrorInfo, ReactNode } from "react";

interface Props {
  children: ReactNode;
  // Optional render-prop fallback so callers can swap the default UI without
  // having to subclass.
  fallback?: (error: Error, reset: () => void) => ReactNode;
}

interface State {
  error: Error | null;
}

// Top-level boundary that catches render-time exceptions in the route tree.
// Prevents a single crashing component from blanking the whole app and gives
// the user a way to recover (reset the boundary, reload the page).
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Surface the error in the dev console; production deployments can
    // forward to a logging endpoint here later.
    console.error("[ErrorBoundary]", error, info);
  }

  reset = () => {
    this.setState({ error: null });
  };

  render() {
    if (this.state.error) {
      if (this.props.fallback) {
        return this.props.fallback(this.state.error, this.reset);
      }
      return (
        <div className="page error-boundary-page" role="alert">
          <h2>Etwas ist schiefgelaufen</h2>
          <p>
            Die Seite konnte aufgrund eines unerwarteten Fehlers nicht angezeigt werden. Wenn das
            Problem bestehen bleibt, lade die Anwendung neu oder melde dich erneut an.
          </p>
          <pre className="error-boundary-stack">{this.state.error.message}</pre>
          <div className="error-boundary-actions">
            <button type="button" className="btn-secondary" onClick={this.reset}>
              Erneut versuchen
            </button>
            <button
              type="button"
              className="btn-primary"
              onClick={() => window.location.reload()}
            >
              Seite neu laden
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
