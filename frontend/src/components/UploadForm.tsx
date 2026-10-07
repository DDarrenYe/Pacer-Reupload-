import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError, api } from "../api";
import type { Surface } from "../types";
import { useSlowNotice } from "../useSlowNotice";

export default function UploadForm({ onUploaded }: { onUploaded: () => void }) {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [surface, setSurface] = useState<Surface | "">("");
  const [isRace, setIsRace] = useState(false);
  const [name, setName] = useState("");
  const [startedAt, setStartedAt] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [duplicateId, setDuplicateId] = useState<string | null>(null);
  const slow = useSlowNotice(busy);

  const isCsv = file?.name.toLowerCase().endsWith(".csv") ?? false;

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    setError(null);
    setDuplicateId(null);
    try {
      const run = await api.uploadRun({
        file,
        surface: surface || undefined,
        isRace,
        name: name || undefined,
        startedAt: startedAt ? new Date(startedAt).toISOString() : undefined,
      });
      onUploaded();
      navigate(`/runs/${run.id}`);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setDuplicateId((err.detail as { run_id?: string })?.run_id ?? null);
      }
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="card stack" onSubmit={submit}>
      <h2>Upload a run</h2>
      <label>
        GPX or CSV file
        <input type="file" accept=".gpx,.csv" required onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
      </label>
      <div className="row">
        <label>
          Surface
          <select value={surface} onChange={(e) => setSurface(e.target.value as Surface | "")}>
            <option value="">Automatic (GPX = road, CSV = treadmill)</option>
            <option value="road">Road</option>
            <option value="track">Track (400 m splits)</option>
            <option value="treadmill">Treadmill</option>
          </select>
        </label>
        <label>
          Name (optional)
          <input value={name} maxLength={200} onChange={(e) => setName(e.target.value)} placeholder="Sunday long run" />
        </label>
      </div>
      {isCsv && (
        <label>
          When did you run it? (CSV files have no date)
          <input type="datetime-local" value={startedAt} onChange={(e) => setStartedAt(e.target.value)} />
        </label>
      )}
      <label className="checkbox">
        <input type="checkbox" checked={isRace} onChange={(e) => setIsRace(e.target.checked)} />
        This was a race
      </label>
      {error && (
        <p className="error" role="alert">
          {error} {duplicateId && <Link to={`/runs/${duplicateId}`}>Open the existing run</Link>}
        </p>
      )}
      {slow && <p className="info">Waking up the server; the first request can take up to a minute.</p>}
      <button type="submit" disabled={!file || busy}>
        {busy ? "Uploading…" : "Upload"}
      </button>
    </form>
  );
}
