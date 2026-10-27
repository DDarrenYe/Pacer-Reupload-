import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api } from "../api";
import { useAuth } from "../auth";
import ManualRunForm from "../components/ManualRunForm";
import { describeDrift, formatDate, formatDistance, formatDuration, formatPace } from "../format";
import { stravaActivityUrl } from "../strava";
import type { RunDetail as RunDetailType, Split } from "../types";
import { useSlowNotice } from "../useSlowNotice";
import { useTitle } from "../useTitle";

const SPLIT_TYPE_TEXT = {
  negative: "Negative split: second half faster",
  even: "Even split: both halves within 1%",
  positive: "Positive split: second half slower",
};

function splitLabel(s: Split): string {
  const unit = s.split_length_m === 1000 ? "km" : `${s.split_length_m} m`;
  return `${unit} ${s.split_no}${s.is_partial ? "*" : ""}`;
}

export default function RunDetail() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const [run, setRun] = useState<RunDetailType | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(false);
  const { demo } = useAuth();
  const slow = useSlowNotice(run === null && !error);

  useTitle(run ? (run.name ?? "Run") : "Run");

  useEffect(() => {
    api.getRun(id).then(setRun, (e: Error) => setError(e.message));
  }, [id]);

  async function reprocess() {
    setBusy(true);
    try {
      setRun(await api.reprocessRun(id));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!confirm("Delete this run? This can't be undone.")) return;
    setBusy(true);
    try {
      await api.deleteRun(id);
      navigate("/");
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  if (error) return <main><p className="error">{error}</p><Link to="/">Back to runs</Link></main>;
  if (!run) return <main><p className="muted">{slow ? "Waking up the server; this can take up to a minute…" : "Loading…"}</p></main>;

  const hasHr = run.splits.some((s) => s.avg_hr !== null);
  const paces = run.splits.map((s) => s.pace_s_per_km);
  const [fastestPace, slowestPace] = [Math.min(...paces), Math.max(...paces)];
  // Longer bar = faster km. The slowest still gets a visible bar, scaled from 55% up.
  const barWidth = (pace: number) =>
    slowestPace === fastestPace ? 100 : 55 + ((slowestPace - pace) / (slowestPace - fastestPace)) * 45;
  const sameFastSlow = run.fastest_split_no === run.slowest_split_no;
  const partial = run.splits.find((s) => s.is_partial);
  const full = run.splits.filter((s) => !s.is_partial && s.avg_hr !== null);
  const hrDrift = full.length >= 3 ? Math.round((full[full.length - 1].avg_hr as number) - (full[0].avg_hr as number)) : null;

  return (
    <main>
      <div>
        <Link to="/" className="crumb">← Runs</Link>
        <div className="run-title" style={{ marginTop: 8 }}>
          <div>
            <h1>{run.name ?? "Untitled run"}</h1>
            <div className="chips">
              <span className="muted">{formatDate(run.started_at)}</span>
              <span className="chip">{run.surface.charAt(0).toUpperCase() + run.surface.slice(1)}</span>
              {run.split_type && <span className="chip accent">{SPLIT_CHIP[run.split_type]}</span>}
              {run.is_race && <span className="chip">Race</span>}
              {run.source === "manual" && <span className="chip">{run.strava_activity_id === null ? "Entered manually" : "No GPS"}</span>}
              {run.strava_activity_id !== null && (
                <a className="strava-link" href={stravaActivityUrl(run.strava_activity_id)} target="_blank" rel="noreferrer">
                  View on Strava
                </a>
              )}
            </div>
          </div>
          {!demo && (
            <div className="actions">
              {run.source === "manual" && !editing && (
                <button className="secondary" onClick={() => setEditing(true)} disabled={busy}>Edit</button>
              )}
              {run.source !== "manual" && (
                <button className="secondary" onClick={reprocess} disabled={busy}>{busy ? "Working…" : "Recalculate"}</button>
              )}
              <button className="danger" onClick={remove} disabled={busy}>Delete</button>
            </div>
          )}
        </div>
      </div>

      <section className="card" aria-label="Summary">
        <dl className="stat-strip even">
          <Stat label="Distance" value={formatDistance(run.distance_m)} />
          <Stat label={run.source === "manual" ? "Time" : "Moving time"} value={formatDuration(run.moving_time_s)} />
          <Stat label="Avg pace" value={formatPace(run.avg_pace_s_per_km)} />
          <Stat label="Avg heart rate" value={run.avg_hr ? `${Math.round(run.avg_hr)} bpm` : "–"} />
          <Stat label="Elevation gain" value={run.elevation_gain_m !== null ? `${Math.round(run.elevation_gain_m)} m` : "–"} />
        </dl>
      </section>

      {editing ? (
        <section className="card">
          <h2>Edit run</h2>
          <ManualRunForm
            run={run}
            onSaved={(updated) => {
              setRun(updated);
              setEditing(false);
            }}
            onCancel={() => setEditing(false)}
          />
        </section>
      ) : run.source === "manual" ? (
        <section className="card">
          <p className="muted" style={{ margin: 0 }}>
            Entered manually, so there are no splits or best efforts: with only a total distance and time, a per-km
            breakdown would be made up. It still counts towards your weekly distance and training load
            {run.is_race ? ", and as a race for predictions" : ""}.
          </p>
        </section>
      ) : run.splits.length === 0 ? (
        <section className="card">
          <p>This run was uploaded before analytics existed.</p>
          {!demo && <button onClick={reprocess} disabled={busy}>{busy ? "Working…" : "Calculate splits now"}</button>}
        </section>
      ) : (
        <div className="run-grid">
          <section className="card">
            <div className="section-head">
              <h2>Splits</h2>
              <span className="muted small">Longer bar = faster</span>
            </div>
            <ol className="split-bars">
              {run.splits.map((s) => {
                const kind =
                  s.split_no === run.fastest_split_no ? "fastest" : s.split_no === run.slowest_split_no && !sameFastSlow ? "slowest" : "";
                return (
                  <li key={s.split_no} className={hasHr ? "split-bar" : "split-bar no-hr"}>
                    <span className="split-label">{splitLabel(s)}</span>
                    <span className="split-track" aria-hidden="true">
                      <span className={`split-fill ${kind}`} style={{ display: "block", width: `${barWidth(s.pace_s_per_km)}%` }} />
                    </span>
                    <span className="split-pace">
                      {formatDuration(s.pace_s_per_km)}
                      {kind && <span className="sr-only"> ({kind})</span>}
                    </span>
                    {hasHr && <span className="split-hr">{s.avg_hr ? `${Math.round(s.avg_hr)} bpm` : "–"}</span>}
                  </li>
                );
              })}
            </ol>
            <div className="legend" aria-hidden="true">
              <span><i style={{ background: "var(--accent)" }} />Fastest</span>
              {!sameFastSlow && <span><i style={{ background: "var(--slow)" }} />Slowest</span>}
              <span><i style={{ background: "var(--accent-soft)" }} />Others</span>
              {partial && <span>* Last split: {formatDistance(partial.distance_m)}, pace still per km</span>}
            </div>
          </section>

          <div className="stack" style={{ gap: 20 }}>
            <section className="card stack">
              <h2 style={{ margin: 0 }}>How it went</h2>
              <ul className="insights">
                {run.split_type && <li>{SPLIT_TYPE_TEXT[run.split_type]}.</li>}
                <li>{describeDrift(run.pace_drift_s_per_km)}</li>
                {hrDrift !== null && Math.abs(hrDrift) >= 10 && (
                  <li className="note">
                    Heart rate {hrDrift > 0 ? "rose" : "fell"} {Math.abs(hrDrift)} bpm from the first km to the last
                    {hrDrift > 0 ? ": normal on a warm day, a long run or a tired week." : "."}
                  </li>
                )}
              </ul>
            </section>
            {run.best_efforts.length > 0 && (
              <section className="card stack">
                <h2 style={{ margin: 0 }}>Best efforts</h2>
                <div className="effort-grid">
                  {run.best_efforts.map((e) => (
                    <div key={e.name} className="effort" title={`Started ${formatDistance(e.start_offset_m)} into the run`}>
                      <span className="tile-label">{e.name}</span>
                      <span className="effort-time">{formatDuration(e.duration_s)}</span>
                      <span className="muted small">{formatPace((e.duration_s / e.distance_m) * 1000)}</span>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </div>
        </div>
      )}
    </main>
  );
}

const SPLIT_CHIP = { negative: "Negative split", even: "Even split", positive: "Positive split" };

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}
