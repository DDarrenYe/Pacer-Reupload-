import { useState, type FormEvent } from "react";

import { api, type ManualRunInput } from "../api";
import { defaultManualName, formatPace, paceFrom, splitDuration, toSeconds } from "../format";
import type { RunDetail, Surface } from "../types";
import { useSlowNotice } from "../useSlowNotice";

/** A Date -> the value a datetime-local input expects, in local time. */
function toLocalInput(d: Date): string {
  const local = new Date(d);
  local.setMinutes(local.getMinutes() - local.getTimezoneOffset());
  return local.toISOString().slice(0, 16);
}

interface Props {
  /** Pass a run to edit it; leave out to add a new one. */
  run?: RunDetail;
  onSaved: (run: RunDetail) => void;
  onCancel?: () => void;
}

export default function ManualRunForm({ run, onSaved, onCancel }: Props) {
  const editing = run !== undefined;
  const [h0, m0, s0] = run ? splitDuration(run.moving_time_s) : ["", "", ""];
  const startKm = run ? run.distance_m / 1000 : null;
  // Keep a hand-picked name; clear an automatic one so it follows the new distance.
  const startName = run?.name && startKm !== null && run.name !== defaultManualName(startKm, run.surface) ? run.name : "";

  const [distance, setDistance] = useState(startKm !== null ? String(Number(startKm.toFixed(3))) : "");
  const [hours, setHours] = useState(h0);
  const [minutes, setMinutes] = useState(m0);
  const [seconds, setSeconds] = useState(s0);
  const [when, setWhen] = useState(() => toLocalInput(run ? new Date(run.started_at) : new Date()));
  const [surface, setSurface] = useState<Surface>(run?.surface ?? "treadmill");
  const [name, setName] = useState(startName);
  const [hr, setHr] = useState(run?.avg_hr ? String(Math.round(run.avg_hr)) : "");
  const [isRace, setIsRace] = useState(run?.is_race ?? false);
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
    const input: ManualRunInput = {
      distance_km: distanceKm,
      duration_s: totalSeconds,
      started_at: new Date(when).toISOString(),
      surface,
      name: name || undefined,
      is_race: isRace,
      avg_hr: hr ? Number(hr) : undefined,
    };
    try {
      onSaved(editing ? await api.updateManualRun(run.id, input) : await api.createManualRun(input));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save the run.");
    } finally {
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
          <input value={name} maxLength={200} onChange={(e) => setName(e.target.value)} placeholder={pace !== null ? defaultManualName(distanceKm, surface) : "Treadmill intervals"} />
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
      <div className="actions">
        <button type="submit" disabled={pace === null || busy}>
          {busy ? "Saving…" : editing ? "Save changes" : "Save run"}
        </button>
        {onCancel && (
          <button type="button" className="secondary" onClick={onCancel} disabled={busy}>
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}
