import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "../api";
import { formatPace, paceFrom, toSeconds } from "../format";
import type { Surface } from "../types";
import { useSlowNotice } from "../useSlowNotice";

function nowForInput(): string {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
}

export default function ManualRunForm({ onSaved }: { onSaved: () => void }) {
  const navigate = useNavigate();
  const [distance, setDistance] = useState("");
  const [hours, setHours] = useState("");
  const [minutes, setMinutes] = useState("");
  const [seconds, setSeconds] = useState("");
  const [when, setWhen] = useState(nowForInput);
  const [surface, setSurface] = useState<Surface>("treadmill");
  const [name, setName] = useState("");
  const [hr, setHr] = useState("");
  const [isRace, setIsRace] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const slow = useSlowNotice(busy);

  const distanceKm = Number(distance);
  const totalSeconds = toSeconds(hours, minutes, seconds);
  const pace = paceFrom(distanceKm, totalSeconds);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (pace === null) return;
    setBusy(true);
    setError(null);
    try {
      const run = await api.createManualRun({
        distance_km: distanceKm,
        duration_s: totalSeconds,
        started_at: new Date(when).toISOString(),
        surface,
        name: name || undefined,
        is_race: isRace,
        avg_hr: hr ? Number(hr) : undefined,
      });
      onSaved();
      navigate(`/runs/${run.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save the run.");
      setBusy(false);
    }
  }

  return (
    <form className="stack" onSubmit={submit}>
      <div className="row">
        <label>
          Distance (km)
          <input type="number" inputMode="decimal" min="0.01" step="0.01" required value={distance} onChange={(e) => setDistance(e.target.value)} placeholder="5.00" />
        </label>
        <fieldset className="duration">
          <legend>Time</legend>
          <input aria-label="Hours" type="number" inputMode="numeric" min="0" value={hours} onChange={(e) => setHours(e.target.value)} placeholder="h" />
          <span>:</span>
          <input aria-label="Minutes" type="number" inputMode="numeric" min="0" max="59" value={minutes} onChange={(e) => setMinutes(e.target.value)} placeholder="mm" />
          <span>:</span>
          <input aria-label="Seconds" type="number" inputMode="numeric" min="0" max="59" value={seconds} onChange={(e) => setSeconds(e.target.value)} placeholder="ss" />
        </fieldset>
      </div>
      <p className="pace-preview" aria-live="polite">
        Average pace: <strong>{pace === null ? "–" : formatPace(pace)}</strong>
      </p>
      <div className="row">
        <label>
          When
          <input type="datetime-local" required value={when} onChange={(e) => setWhen(e.target.value)} />
        </label>
        <label>
          Surface
          <select value={surface} onChange={(e) => setSurface(e.target.value as Surface)}>
            <option value="treadmill">Treadmill</option>
            <option value="road">Road</option>
            <option value="track">Track</option>
          </select>
        </label>
      </div>
      <div className="row">
        <label>
          Name (optional)
          <input value={name} maxLength={200} onChange={(e) => setName(e.target.value)} placeholder="Treadmill intervals" />
        </label>
        <label>
          Average heart rate (optional)
          <input type="number" inputMode="numeric" min="30" max="250" value={hr} onChange={(e) => setHr(e.target.value)} placeholder="bpm" />
        </label>
      </div>
      <label className="checkbox">
        <input type="checkbox" checked={isRace} onChange={(e) => setIsRace(e.target.checked)} />
        This was a race
      </label>
      {error && <p className="error" role="alert">{error}</p>}
      {slow && <p className="info">Waking up the server; the first request can take up to a minute.</p>}
      <button type="submit" disabled={pace === null || busy}>
        {busy ? "Saving…" : "Save run"}
      </button>
    </form>
  );
}
