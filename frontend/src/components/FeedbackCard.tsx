import { useState, type FormEvent } from "react";

import { api } from "../api";

/** My Profile: send the developer a note. */
export default function FeedbackCard() {
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.sendFeedback(message, "/account");
      setSent(true);
      setMessage("");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card" id="feedback">
      <form className="stack" onSubmit={submit}>
        <h2>Feedback</h2>
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
    </section>
  );
}
