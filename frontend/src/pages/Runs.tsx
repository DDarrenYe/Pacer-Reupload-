import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api";
import UploadForm from "../components/UploadForm";
import { formatDate, formatDistance, formatDuration, formatPace } from "../format";
import type { Run } from "../types";
import { useSlowNotice } from "../useSlowNotice";

export default function Runs() {
  const [runs, setRuns] = useState<Run[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const slow = useSlowNotice(runs === null && !error);

  const load = useCallback(() => {
    api.listRuns().then(setRuns, (e: Error) => setError(e.message));
  }, []);
  useEffect(load, [load]);

  return (
    <main>
      <UploadForm onUploaded={load} />
      <section className="card">
        <h2>Your runs</h2>
        {error && <p className="error">{error}</p>}
        {runs === null && !error && (
          <p className="muted">{slow ? "Waking up the server; this can take up to a minute…" : "Loading…"}</p>
        )}
        {runs?.length === 0 && <p className="muted">No runs yet. Upload one above.</p>}
        {runs && runs.length > 0 && (
          <div className="table-scroll">
            <table>
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
                {runs.map((r) => (
                  <tr key={r.id}>
                    <td>{formatDate(r.started_at)}</td>
                    <td>
                      <Link to={`/runs/${r.id}`}>{r.name ?? "Untitled run"}</Link>
                      <span className="tag">{r.surface}</span>
                      {r.is_race && <span className="tag">race</span>}
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
      </section>
    </main>
  );
}
