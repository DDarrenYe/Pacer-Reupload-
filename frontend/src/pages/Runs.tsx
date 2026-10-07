import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api";
import ManualRunForm from "../components/ManualRunForm";
import UploadForm from "../components/UploadForm";
import { formatDate, formatDistance, formatDuration, formatPace } from "../format";
import type { Run } from "../types";
import { useSlowNotice } from "../useSlowNotice";

export default function Runs() {
  const [runs, setRuns] = useState<Run[] | null>(null);
  const [mode, setMode] = useState<"file" | "manual">("file");
  const [error, setError] = useState<string | null>(null);
  const [recalc, setRecalc] = useState<{ busy: boolean; message: string | null }>({ busy: false, message: null });
  const slow = useSlowNotice(runs === null && !error);

  const load = useCallback(() => {
    api.listRuns().then(setRuns, (e: Error) => setError(e.message));
  }, []);
  useEffect(load, [load]);

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

  return (
    <main>
      <section className="card stack">
        <div className="tabs" role="tablist" aria-label="Add a run">
          <button role="tab" aria-selected={mode === "file"} className={mode === "file" ? "tab active" : "tab"} onClick={() => setMode("file")}>
            Upload a file
          </button>
          <button role="tab" aria-selected={mode === "manual"} className={mode === "manual" ? "tab active" : "tab"} onClick={() => setMode("manual")}>
            Enter manually
          </button>
        </div>
        {mode === "file" ? <UploadForm onUploaded={load} /> : <ManualRunForm onSaved={load} />}
      </section>
      <section className="card">
        <h2>Your runs</h2>
        {error && <p className="error">{error}</p>}
        {runs === null && !error && (
          <p className="muted">{slow ? "Waking up the server; this can take up to a minute…" : "Loading…"}</p>
        )}
        {runs?.length === 0 && <p className="muted">No runs yet. Upload one above.</p>}
        {recalc.message && <p className="info" role="status">{recalc.message}</p>}
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
        {runs && runs.length > 0 && (
          <div className="actions" style={{ marginTop: 12 }}>
            <button className="secondary" onClick={recalculateAll} disabled={recalc.busy}>
              {recalc.busy ? "Recalculating…" : "Recalculate all runs"}
            </button>
          </div>
        )}
      </section>
    </main>
  );
}
