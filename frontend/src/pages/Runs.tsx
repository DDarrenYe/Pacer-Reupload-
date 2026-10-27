import { useCallback, useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { api } from "../api";
import { useAuth } from "../auth";
import ManualRunForm from "../components/ManualRunForm";
import RunnerCard from "../components/RunnerCard";
import UploadForm from "../components/UploadForm";
import { formatDate, formatDistance, formatDuration, formatPace } from "../format";
import { runMeta } from "../runMeta";
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

  const shown = runs ? (showAll ? runs : runs.slice(0, RECENT)) : [];

  return (
    <main>
      {runs && runs.length > 0 && <RunnerCard runs={runs} />}
      <section className="card">
        <div className="section-head">
          <h2>{runs && runs.length > 0 ? "Recent runs" : "Your runs"}</h2>
          {!demo && (
            <div className="actions">
              {strava?.connected && (
                <button className="secondary" onClick={syncStrava} disabled={stravaSync.busy}>
                  {stravaSync.busy ? "Syncing…" : "Sync Strava"}
                </button>
              )}
              <button className={addOpen ? "secondary" : undefined} aria-expanded={addOpen} aria-controls="add-run" onClick={() => setAdding(!addOpen)}>
                {addOpen ? "Close" : "+ Add a run"}
              </button>
            </div>
          )}
        </div>
        {!demo && addOpen && (
          <div id="add-run" className="add-panel stack">
            <div className="tabs" role="tablist" aria-label="Add a run">
              <button role="tab" aria-selected={mode === "file"} className={mode === "file" ? "tab active" : "tab"} onClick={() => setMode("file")}>
                Upload a file
              </button>
              <button role="tab" aria-selected={mode === "manual"} className={mode === "manual" ? "tab active" : "tab"} onClick={() => setMode("manual")}>
                Enter manually
              </button>
            </div>
            {mode === "file" ? <UploadForm onUploaded={load} /> : <ManualRunForm onSaved={(run) => navigate(`/runs/${run.id}`)} />}
          </div>
        )}
        {error && <p className="error">{error}</p>}
        {runs === null && !error && (
          <p className="muted">{slow ? "Waking up the server; this can take up to a minute…" : "Loading…"}</p>
        )}
        {runs?.length === 0 && (
          <p className="muted">
            No runs yet. Upload a GPX, enter a treadmill run manually, or connect Strava on My Profile.{" "}
            <Link to="/welcome#export">How to get your runs out of Strava or Garmin</Link>
          </p>
        )}
        {recalc.message && <p className="info" role="status">{recalc.message}</p>}
        {stravaSync.message && <p className="info" role="status">{stravaSync.message}</p>}
        {runs && runs.length > 0 && (
          <ul id="runs-list" className="run-list" aria-label="Runs, newest first">
            {shown.map((r) => {
              const d = new Date(r.started_at);
              return (
                <li key={r.id} className="run-row">
                  <span className="run-date" aria-label={formatDate(r.started_at)}>
                    <span className="run-day" aria-hidden="true">{d.getDate()}</span>
                    <span className="run-month" aria-hidden="true">{d.toLocaleDateString(undefined, { month: "short" })}</span>
                  </span>
                  <span className="run-main">
                    <Link to={`/runs/${r.id}`}>{r.name ?? "Untitled run"}</Link>
                    <span className="run-meta">{runMeta(r)}</span>
                  </span>
                  <span className="run-num strong">{formatDistance(r.distance_m)}</span>
                  <span className="run-num run-time">{formatDuration(r.moving_time_s)}</span>
                  <span className="run-num run-pace">{formatPace(r.avg_pace_s_per_km)}</span>
                </li>
              );
            })}
          </ul>
        )}
        {runs && runs.length > 0 && (
          <div className="list-foot">
            {runs.length > RECENT ? (
              <button className="link" aria-expanded={showAll} aria-controls="runs-list" onClick={() => setShowAll((v) => !v)}>
                {showAll ? `Show only the ${RECENT} most recent ▴` : `Show all ${runs.length} runs ▾`}
              </button>
            ) : (
              <span className="muted small">{runs.length} run{runs.length === 1 ? "" : "s"}</span>
            )}
            {!demo && (
              <button className="link" onClick={recalculateAll} disabled={recalc.busy}>
                {recalc.busy ? "Recalculating…" : "Recalculate all runs"}
              </button>
            )}
          </div>
        )}
      </section>
    </main>
  );
}
