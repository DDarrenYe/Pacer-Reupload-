import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api } from "../api";
import { useAuth } from "../auth";
import { LineChart } from "../components/charts";
import ManualRunForm from "../components/ManualRunForm";
import { describeDrift, formatDate, formatDistance, formatDuration, formatPace } from "../format";
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
  const label = `${unit} ${s.split_no}`;
  return s.is_partial ? `${label} (${formatDistance(s.distance_m)})` : label;
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
  const labels = run.splits.map(splitLabel);

  return (
    <main>
      <p><Link to="/">← All runs</Link></p>
      <header className="run-header">
        <h1>{run.name ?? "Untitled run"}</h1>
        <p className="muted">
          {formatDate(run.started_at)} · {run.surface}
          {run.source === "manual" && " · entered manually"}
          {run.is_race && " · race"}
        </p>
      </header>

      <section className="tiles" aria-label="Summary">
        <Tile label="Distance" value={formatDistance(run.distance_m)} />
        <Tile label={run.source === "manual" ? "Time" : "Moving time"} value={formatDuration(run.moving_time_s)} />
        <Tile label="Average pace" value={formatPace(run.avg_pace_s_per_km)} />
        <Tile label="Average heart rate" value={run.avg_hr ? `${Math.round(run.avg_hr)} bpm` : "–"} />
        <Tile label="Elevation gain" value={run.elevation_gain_m !== null ? `${Math.round(run.elevation_gain_m)} m` : "–"} />
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
        <>
          <section className="card">
            <h2>How the run went</h2>
            <ul className="facts">
              {run.split_type && <li>{SPLIT_TYPE_TEXT[run.split_type]}.</li>}
              <li>{describeDrift(run.pace_drift_s_per_km)}</li>
            </ul>
            <div className="charts">
              <LineChart title="Pace per split" labels={labels} values={run.splits.map((s) => s.pace_s_per_km)} format={formatDuration} lowerIsBetter />
              {hasHr && (
                <LineChart title="Heart rate per split" labels={labels} values={run.splits.map((s) => s.avg_hr)} format={(v) => `${Math.round(v)} bpm`} />
              )}
            </div>
          </section>

          <section className="card">
            <h2>Splits</h2>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Split</th>
                    <th className="num">Distance</th>
                    <th className="num">Time</th>
                    <th className="num">Pace</th>
                    {hasHr && <th className="num">Heart rate</th>}
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {run.splits.map((s) => (
                    <tr key={s.split_no}>
                      <td>{s.split_no}</td>
                      <td className="num">{formatDistance(s.distance_m)}</td>
                      <td className="num">{formatDuration(s.duration_s)}</td>
                      <td className="num">{formatPace(s.pace_s_per_km)}</td>
                      {hasHr && <td className="num">{s.avg_hr ? Math.round(s.avg_hr) : "–"}</td>}
                      <td>
                        {s.split_no === run.fastest_split_no && <span className="tag">fastest</span>}
                        {s.split_no === run.slowest_split_no && run.fastest_split_no !== run.slowest_split_no && <span className="tag">slowest</span>}
                        {s.is_partial && <span className="tag">partial</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="card">
            <h2>Best efforts in this run</h2>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr><th>Distance</th><th className="num">Time</th><th className="num">Pace</th><th className="num">Started at</th></tr>
                </thead>
                <tbody>
                  {run.best_efforts.map((e) => (
                    <tr key={e.name}>
                      <td>{e.name}</td>
                      <td className="num">{formatDuration(e.duration_s)}</td>
                      <td className="num">{formatPace((e.duration_s / e.distance_m) * 1000)}</td>
                      <td className="num">{formatDistance(e.start_offset_m)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}

      {!demo && <section className="actions">
        {run.source === "manual" && !editing && (
          <button className="secondary" onClick={() => setEditing(true)} disabled={busy}>Edit run</button>
        )}
        {run.source !== "manual" && <button className="secondary" onClick={reprocess} disabled={busy}>Recalculate</button>}
        <button className="danger" onClick={remove} disabled={busy}>Delete run</button>
      </section>}
    </main>
  );
}

function Tile({ label, value }: { label: string; value: string }) {
  return (
    <div className="tile">
      <div className="tile-label">{label}</div>
      <div className="tile-value">{value}</div>
    </div>
  );
}
