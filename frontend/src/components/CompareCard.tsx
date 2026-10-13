import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api";
import { describePercentile, formatDuration } from "../format";
import type { Comparison } from "../types";

/** Trends page: age grade and percentile at 5k to marathon for your age and sex. The
 * age and sex themselves are set on My Profile. */
export default function CompareCard() {
  const [data, setData] = useState<Comparison | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.comparison().then(setData, (e: Error) => setError(e.message));
  }, []);

  if (!data) return error ? <section className="card"><p className="error">{error}</p></section> : null;
  const { profile, rows, sources } = data;
  const complete = profile.age !== null && profile.sex !== null;
  const who = profile.sex === "female" ? "women" : "men";
  const anchors = [...new Set(rows.map((r) => r.anchor).filter(Boolean))];

  return (
    <section className="card stack">
      <div className="page-header">
        <h2>How you compare</h2>
        {complete && <Link to="/account">Change age or sex</Link>}
      </div>

      {!complete ? (
        <p className="info">
          <Link to="/account">Go to My Profile</Link> to add your age and sex, and you'll see how your times compare
          with other runners of your age.
        </p>
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
