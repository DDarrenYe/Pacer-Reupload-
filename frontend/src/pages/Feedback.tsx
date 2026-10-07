import { useState, type FormEvent } from "react";
import { useLocation } from "react-router-dom";

import { api } from "../api";
import { useTitle } from "../useTitle";

export default function Feedback() {
  useTitle("Feedback");
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? null;
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.sendFeedback(message, from ?? location.pathname);
      setSent(true);
      setMessage("");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main>
      <h1>Feedback</h1>
      <form className="card stack" onSubmit={submit}>
        <p className="muted">Something wrong, confusing or missing? A number that doesn't match Strava? Tell me here.</p>
        <label>
          Your message
          <textarea rows={6} maxLength={2000} required value={message} onChange={(e) => { setMessage(e.target.value); setSent(false); }} />
        </label>
        <p className="muted small">{message.length} / 2000</p>
        {sent && <p className="info" role="status">Thanks, your feedback was sent.</p>}
        {error && <p className="error" role="alert">{error}</p>}
        <div className="actions">
          <button type="submit" disabled={busy || !message.trim()}>{busy ? "Sending…" : "Send feedback"}</button>
        </div>
      </form>
    </main>
  );
}
