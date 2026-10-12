import { useEffect, useState } from "react";

import { api } from "../api";
import { formatDate } from "../format";
import { describeSync, startStravaConnect } from "../strava";
import type { StravaStatus } from "../types";

/** Account page: connect Strava, sync runs from it, or disconnect. Hidden when the
 * server has no Strava app configured. */
export default function StravaCard() {
  const [status, setStatus] = useState<StravaStatus | null>(null);
  const [busy, setBusy] = useState<"sync" | "disconnect" | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => api.stravaStatus().then(setStatus, () => setStatus(null));
  useEffect(() => {
    load();
  }, []);

  if (!status?.enabled) return null;

  async function sync() {
    setBusy("sync");
    setError(null);
    setMessage(null);
    try {
      setMessage(describeSync(await api.stravaSync()));
      await load();
    } catch (e) {
      setError((e as Error).message);
      await load();
    } finally {
      setBusy(null);
    }
  }

  async function disconnect() {
    if (!confirm("Disconnect Strava? This also deletes every run imported from Strava. Runs you uploaded yourself stay.")) return;
    setBusy("disconnect");
    setError(null);
    setMessage(null);
    try {
      await api.stravaDisconnect();
      setMessage("Strava disconnected and its runs removed.");
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="card stack">
      <h2>Strava</h2>
      {status.connected ? (
        <>
          <p>
            Connected{status.athlete_name && <> as <strong>{status.athlete_name}</strong></>}.{" "}
            {status.last_synced_at ? `Last synced ${formatDate(status.last_synced_at)}.` : "Not synced yet."}
          </p>
          <p className="muted small">
            Sync imports your runs from the last 180 days, then anything new. Runs with GPS get full splits; treadmill
            runs come in with distance and time. Strava runs are only ever shown to you and aren't used in the shared
            prediction model.
          </p>
          <div className="actions">
            <button onClick={sync} disabled={busy !== null}>{busy === "sync" ? "Syncing…" : "Sync now"}</button>
            <button className="secondary" onClick={disconnect} disabled={busy !== null}>
              {busy === "disconnect" ? "Disconnecting…" : "Disconnect"}
            </button>
          </div>
        </>
      ) : (
        <>
          <p>Connect Strava to import your runs automatically instead of exporting GPX files.</p>
          <div className="actions">
            <button className="strava-button" onClick={() => status.client_id && startStravaConnect(status.client_id)}>
              Connect with Strava
            </button>
          </div>
        </>
      )}
      {message && <p className="info" role="status">{message}</p>}
      {error && <p className="error" role="alert">{error}</p>}
      <p className="muted small">Powered by Strava</p>
    </section>
  );
}
