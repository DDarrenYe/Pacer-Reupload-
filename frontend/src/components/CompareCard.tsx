import { useEffect, useState, type FormEvent } from "react";

import { api } from "../api";
import { useAuth } from "../auth";
import { describePercentile, formatDuration } from "../format";
import type { Comparison, Sex } from "../types";

const THIS_YEAR = new Date().getFullYear();

/** Trends page: age grade and percentile at 5k to marathon for your age and sex. */
export default function CompareCard() {
  const { demo } = useAuth();
  const [data, setData] = useState<Comparison | null>(null);
  const [editing, setEditing] = useState(false);
  const [year, setYear] = useState("");
  const [sex, setSex] = useState<Sex | "">("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = () =>
    api.comparison().then((c) => {
      setData(c);
      setYear(c.profile.birth_year ? String(c.profile.birth_year) : "");
      setSex(c.profile.sex ?? "");
    }, (e: Error) => setError(e.message));
  useEffect(() => {
    load();
  }, []);

  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.saveProfile({ birth_year: year ? Number(year) : null, sex: sex || null });
      await load();
      setEditing(false);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (!data) return error ? <section className="card"><p className="error">{error}</p></section> : null;
  const { profile, rows, sources } = data;
  const complete = profile.age !== null && profile.sex !== null;
  const showForm = !demo && (editing || !complete);
  const who = profile.sex === "female" ? "women" : "men";
  const anchors = [...new Set(rows.map((r) => r.anchor).filter(Boolean))];

  return (
    <section className="card stack">
      <div className="page-header">
        <h2>How you compare</h2>
        {complete && !showForm && !demo && (
          <button className="link" onClick={() => setEditing(true)}>Edit age and sex</button>
        )}
      </div>

      {showForm ? (
        <form className="stack" onSubmit={save}>
          <p className="muted">
            Add your year of birth and sex to see an age grade and a percentile for each distance. They're only used
            for this comparison, and you can remove them any time.
          </p>
          <div className="row">
            <label>
              Year of birth
              <input
                type="number"
                inputMode="numeric"
                min="1920"
                max={THIS_YEAR - 5}
                required
                value={year}
                onChange={(e) => setYear(e.target.value)}
                placeholder="1995"
              />
            </label>
            <label>
              Sex
              <select required value={sex} onChange={(e) => setSex(e.target.value as Sex | "")}>
                <option value="">Choose…</option>
                <option value="female">Female</option>
                <option value="male">Male</option>
              </select>
            </label>
          </div>
          <p className="muted small">
            The published age-grading standards only exist for women and men, so those are the two options.
          </p>
          {error && <p className="error" role="alert">{error}</p>}
          <div className="actions">
            <button type="submit" disabled={busy}>{busy ? "Saving…" : "Save"}</button>
            {complete && (
              <button type="button" className="secondary" onClick={() => setEditing(false)} disabled={busy}>
                Cancel
              </button>
            )}
          </div>
        </form>
      ) : rows.every((r) => r.time_s === null) ? (
        <p className="muted">Upload a race or a hard GPX run and your comparison appears here.</p>
      ) : (
        <>
          <p className="muted">
            Based on your predicted times, for {who} aged {profile.age}
            {anchors.length > 0 && <>, starting from {anchors.join("; ")}</>}.
          </p>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Distance</th>
                  <th className="num">Predicted</th>
                  <th className="num">Age grade</th>
                  <th>Faster than</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.name}>
                    <td>
                      {r.name}
                      {r.extrapolated && <span className="tag">extrapolated</span>}
                    </td>
                    <td className="num">{r.time_s === null ? "–" : formatDuration(r.time_s)}</td>
                    <td className="num">
                      {r.age_grade === null ? "–" : `${r.age_grade.toFixed(1)}%`}
                      {r.band && <div className="tile-note">{r.band}</div>}
                    </td>
                    <td>
                      {r.faster_than_pct === null ? (
                        <span className="muted">–</span>
                      ) : (
                        <>
                          <strong>{describePercentile(r.faster_than_pct)}</strong>
                          <div className="tile-note">of {r.group}</div>
                        </>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ul className="facts small">
            <li>
              <strong>Age grade</strong> compares your time with the best expected for your age and sex (100% is
              world-record level), so it's fair across ages and distances. Standards: {sources.age_grade}.
            </li>
            {sources.percentiles ? (
              <li>
                <strong>Faster than</strong> compares your age grade with finishers of your sex and age group in 2023 US
                marathons ({sources.finishers?.toLocaleString()} finishers in all; {sources.percentiles}). People who
                race are faster than runners in general, and shorter races draw more casual runners, so treat the 5k
                to half marathon percentiles as a rough guide.
              </li>
            ) : (
              <li>Percentiles against other runners are coming soon.</li>
            )}
          </ul>
        </>
      )}
    </section>
  );
}
