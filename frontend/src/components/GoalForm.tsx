import { useState, type FormEvent } from "react";

import { api, type GoalInput } from "../api";
import { formatPace, paceFrom, splitDuration, toSeconds } from "../format";
import type { Goal } from "../types";
import { useSlowNotice } from "../useSlowNotice";

export const PRESETS = [
  { label: "5k", km: 5 },
  { label: "10k", km: 10 },
  { label: "Half marathon", km: 21.0975 },
  { label: "Marathon", km: 42.195 },
];

/** "Half marathon" for a standard distance, otherwise "15 km". */
export function goalDistanceLabel(km: number): string {
  return PRESETS.find((p) => Math.abs(p.km - km) < 1e-4)?.label ?? `${Number(km.toPrecision(6))} km`;
}

/** The name the server gives a goal when you leave the name blank. */
export function defaultGoalName(km: number): string {
  return `${goalDistanceLabel(km)} goal`;
}

function localToday(): string {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 10);
}

interface Props {
  /** Pass a goal to edit it; leave out to add a new one. */
  goal?: Goal;
  onSaved: (goal: Goal) => void;
  onCancel?: () => void;
}

export default function GoalForm({ goal, onSaved, onCancel }: Props) {
  const startKm = goal ? goal.distance_m / 1000 : 21.0975;
  const startPreset = PRESETS.find((p) => Math.abs(p.km - startKm) < 1e-3);
  const [h0, m0, s0] = goal ? splitDuration(goal.target_time_s) : ["", "", ""];

  const [preset, setPreset] = useState(startPreset ? String(startPreset.km) : "custom");
  const [custom, setCustom] = useState(startPreset ? "" : String(Number(startKm.toFixed(3))));
  const [hours, setHours] = useState(h0);
  const [minutes, setMinutes] = useState(m0);
  const [seconds, setSeconds] = useState(s0);
  const [raceDate, setRaceDate] = useState(goal?.race_date ?? "");
  // Keep a hand-picked name; clear an automatic one so it follows the distance.
  const [name, setName] = useState(goal && goal.name !== defaultGoalName(startKm) ? goal.name : "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const slow = useSlowNotice(busy);

  const distanceKm = preset === "custom" ? Number(custom) : Number(preset);
  const totalSeconds = toSeconds(hours, minutes, seconds);
  const pace = paceFrom(distanceKm, totalSeconds);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (pace === null) return;
    setBusy(true);
    setError(null);
    const input: GoalInput = {
      name: name.trim() || undefined,
      distance_km: distanceKm,
      target_time_s: totalSeconds,
      race_date: raceDate,
    };
    try {
      onSaved(goal ? await api.updateGoal(goal.id, input) : await api.createGoal(input));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save the goal.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="stack" onSubmit={submit}>
      <div className="row">
        <label>
          Race distance
          <select value={preset} onChange={(e) => setPreset(e.target.value)}>
            {PRESETS.map((p) => (
              <option key={p.label} value={String(p.km)}>{p.label}</option>
            ))}
            <option value="custom">Other distance</option>
          </select>
        </label>
        {preset === "custom" && (
          <label>
            Distance (km)
            <input type="number" inputMode="decimal" min="1" max="100" step="0.01" required value={custom} onChange={(e) => setCustom(e.target.value)} placeholder="15" />
          </label>
        )}
        <fieldset className="duration">
          <legend>Target time</legend>
          <input aria-label="Hours" type="number" inputMode="numeric" min="0" value={hours} onChange={(e) => setHours(e.target.value)} placeholder="h" />
          <span>:</span>
          <input aria-label="Minutes" type="number" inputMode="numeric" min="0" max="59" value={minutes} onChange={(e) => setMinutes(e.target.value)} placeholder="mm" />
          <span>:</span>
          <input aria-label="Seconds" type="number" inputMode="numeric" min="0" max="59" value={seconds} onChange={(e) => setSeconds(e.target.value)} placeholder="ss" />
        </fieldset>
      </div>
      <p className="pace-preview" aria-live="polite">
        Target pace: <strong>{pace === null ? "–" : formatPace(pace)}</strong>
      </p>
      <div className="row">
        <label>
          Race date
          <input type="date" required min={goal ? undefined : localToday()} value={raceDate} onChange={(e) => setRaceDate(e.target.value)} />
        </label>
        <label>
          Name (optional)
          <input value={name} maxLength={200} onChange={(e) => setName(e.target.value)} placeholder={distanceKm > 0 ? defaultGoalName(distanceKm) : "Spring half"} />
        </label>
      </div>
      {error && <p className="error" role="alert">{error}</p>}
      {slow && <p className="info">Waking up the server; the first request can take up to a minute.</p>}
      <div className="actions">
        <button type="submit" disabled={pace === null || !raceDate || busy}>
          {busy ? "Saving…" : goal ? "Save changes" : "Add goal"}
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
