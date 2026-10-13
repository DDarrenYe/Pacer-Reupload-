import { useCallback, useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { api } from "../api";
import { useAuth } from "../auth";
import ManualRunForm from "../components/ManualRunForm";
import UploadForm from "../components/UploadForm";
import { formatDate, formatDistance, formatDuration, formatPace } from "../format";
import { describeSync } from "../strava";
import type { Run, StravaStatus } from "../types";
import { useSlowNotice } from "../useSlowNotice";
import { useTitle } from "../useTitle";

// The list starts with the most recent runs; the rest are one click away.
const RECENT = 10;

export default function Runs() {
  const [runs, setRuns] = useState<Run[] | null>(null);
  const [mode, setMode] = useState<"file" | "manual">("file");
  const [showAll, setShowAll] = useState(false);
  // The add-a-run section starts closed once you have runs, so the list comes first.
  const [adding, setAdding] = useState<boolean | null>(null);
  const navigate = useNavigate();
  const location = useLocation();
  const { demo } = useAuth();
  const [strava, setStrava] = useState<StravaStatus | null>(null);
  const [stravaSync, setStravaSync] = useState<{ busy: boolean; message: string | null }>({
    busy: false,
    // Set by the Strava callback page after connecting and the first import.
    message: (location.state as { notice?: string } | null)?.notice ?? null,
  });
  useTitle("Runs");
  const [error, setError] = useState<string | null>(null);
  const [recalc, setRecalc] = useState<{ busy: boolean; message: string | null }>({ busy: false, message: null });
  const slow = useSlowNotice(runs === null && !error);

  const load = useCallback(() => {
    api.listRuns().then(setRuns, (e: Error) => setError(e.message));
  }, []);
  useEffect(load, [load]);
  useEffect(() => {
    if (!demo) api.stravaStatus().then(setStrava, () => setStrava(null));
  }, [demo]);

  async function syncStrava() {
    setStravaSync({ busy: true, message: null });
    try {
      setStravaSync({ busy: false, message: describeSync(await api.stravaSync()) });
      load();
    } catch (e) {
      setStravaSync({ busy: false, message: (e as Error).message });
    }
  }

  async function recalculateAll() {
    if (!confirm("Recalculate every run from its original file? This picks up the latest fixes to distance, pace and splits.")) return;
    setRecalc({ busy: true, message: null });
    try {
      const { reprocessed, failed } = await api.reprocessAll();
      const note = failed ? ` ${failed} couldn't be recalculated (original file missing).` : "";
      setRecalc({ busy: false, message: `Recalculated ${reprocessed} run${reprocessed === 1 ? "" : "s"}.${note}` });
      load();
    } catch (e) {
      setRecalc({ busy: false, message: (e as Error).message });
    }
  }

  // Decided once, when the list first loads: open only for a new user with no runs, and
  // it then stays as it is (a first upload doesn't snap it shut).
  useEffect(() => {
    if (adding === null && runs !== null) setAdding(runs.length === 0);
  }, [adding, runs]);
  const addOpen = adding ?? false;

  return (
    <main>
      {!demo && <section className="card stack">
        <button
          className="disclosure"
          aria-expanded={addOpen}
          aria-controls="add-run"
          onClick={() => setAdding(!addOpen)}
        >
          <span>Add a run</span>
          <span aria-hidden="true">{addOpen ? "▴" : "▾"}</span>
        </button>
        {addOpen && <div id="add-run" className="stack">
        <div className="tabs" role="tablist" aria-label="Add a run">
          <button role="tab" aria-selected={mode === "file"} className={mode === "file" ? "tab active" : "tab"} onClick={() => setMode("file")}>
            Upload a file
          </button>
          <button role="tab" aria-selected={mode === "manual"} className={mode === "manual" ? "tab active" : "tab"} onClick={() => setMode("manual")}>
            Enter manually
          </button>
        </div>
        {mode === "file" ? <UploadForm onUploaded={load} /> : <ManualRunForm onSaved={(run) => navigate(`/runs/${run.id}`)} />}
        </div>}
      </section>}
      <section className="card">
        <h2>Your runs</h2>
        {error && <p className="error">{error}</p>}
        {runs === null && !error && (
          <p className="muted">{slow ? "Waking up the server; this can take up to a minute…" : "Loading…"}</p>
        )}
        {runs?.length === 0 && (
          <p className="muted">
            No runs yet. Upload a GPX above, enter a treadmill run manually, or connect Strava on My Profile.{" "}
            <Link to="/welcome#export">How to get your runs out of Strava or Garmin</Link>
          </p>
        )}
        {recalc.message && <p className="info" role="status">{recalc.message}</p>}
        {stravaSync.message && <p className="info" role="status">{stravaSync.message}</p>}
        {runs && runs.length > 0 && (
          <div className="table-scroll">
            <table id="runs-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Run</th>
                  <th className="num">Distance</th>
                  <th className="num">Moving time</th>
                  <th className="num">Pace</th>
                  <th>Splits</th>
                </tr>
              </thead>
              <tbody>
                {(showAll ? runs : runs.slice(0, RECENT)).map((r) => (
                  <tr key={r.id}>
                    <td>{formatDate(r.started_at)}</td>
                    <td>
                      <Link to={`/runs/${r.id}`}>{r.name ?? "Untitled run"}</Link>
                      <span className="tag">{r.surface}</span>
                      {r.is_race && <span className="tag">race</span>}
                      {r.strava_activity_id !== null && <span className="tag">Strava</span>}
                    </td>
                    <td className="num">{formatDistance(r.distance_m)}</td>
                    <td className="num">{formatDuration(r.moving_time_s)}</td>
                    <td className="num">{formatPace(r.avg_pace_s_per_km)}</td>
                    <td>{r.split_type ?? "–"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {runs && runs.length > RECENT && (
          <div className="list-toggle">
            <span className="muted">
              Showing {showAll ? runs.length : RECENT} of {runs.length}
            </span>
            <button
              className="link"
              aria-expanded={showAll}
              aria-controls="runs-table"
              onClick={() => setShowAll((v) => !v)}
            >
              {showAll ? `Show only the ${RECENT} most recent ▴` : `Show all ${runs.length} runs ▾`}
            </button>
          </div>
        )}
        {!demo && (strava?.connected || (runs && runs.length > 0)) && (
          <div className="actions" style={{ marginTop: 12 }}>
            {strava?.connected && (
              <button onClick={syncStrava} disabled={stravaSync.busy}>
                {stravaSync.busy ? "Syncing…" : "Sync from Strava"}
              </button>
            )}
            {runs && runs.length > 0 && (
              <button className="secondary" onClick={recalculateAll} disabled={recalc.busy}>
                {recalc.busy ? "Recalculating…" : "Recalculate all runs"}
              </button>
            )}
          </div>
        )}
      </section>
    </main>
  );
}
