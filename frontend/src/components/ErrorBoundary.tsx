import { Component, type ReactNode } from "react";

/** A crash in any page shows this instead of a blank screen. */
export default class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: unknown) {
    console.error("Pacer crashed:", error);
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <main className="narrow">
        <h1>Something went wrong</h1>
        <p className="muted">Sorry, that page hit an error. Reloading usually fixes it.</p>
        <button onClick={() => window.location.reload()}>Reload</button>
      </main>
    );
  }
}
