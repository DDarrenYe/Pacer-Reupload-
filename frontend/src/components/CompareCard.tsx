import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api";
import { describePercentile, formatDuration } from "../format";
import { RANKS, rankRange } from "../ranks";
import type { Comparison, OverallRank } from "../types";
import RankMedal from "./RankMedal";

/** Trends page: age grade and percentile at 5k to marathon for your age and sex. The
 * age and sex themselves are set on My Profile. */
/** The big rank badge: medal, rank, what it's based on, and the way to the next one. */
export function RankHeader({ overall }: { overall: OverallRank }) {
  return (
    <div className="rank-header">
      <RankMedal rank={overall.rank} size={72} />
      <div className="rank-body">
        <div className="rank-name">{overall.rank}</div>
        <p className="muted">
          From your {overall.source === "best time" ? "best" : "predicted"} {overall.distance}:{" "}
          {overall.age_grade.toFixed(1)}% age grade
        </p>
        {overall.next_rank && overall.progress_pct !== null && overall.next_rank_age_grade !== null ? (
          <>
            <div
              className="rank-progress"
              role="progressbar"
              aria-label={`Progress to ${overall.next_rank}`}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={Math.round(overall.progress_pct)}
            >
              <div style={{ width: `${Math.min(100, Math.max(2, overall.progress_pct))}%` }} />
            </div>
            <p className="small">
              {(overall.next_rank_age_grade - overall.age_grade).toFixed(1)} points to <strong>{overall.next_rank}</strong>
              {overall.next_rank_time_s !== null && (
                <>: run a {overall.distance} in {formatDuration(overall.next_rank_time_s)} to get there.</>
              )}
            </p>
          </>
        ) : (
          <p className="small">The top rank. World-class for your age.</p>
        )}
      </div>
    </div>
  );
}

function AllRanks() {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button className="link" aria-expanded={open} aria-controls="all-ranks" onClick={() => setOpen(!open)}>
        {open ? "Hide ranks ▴" : "See all ranks ▾"}
      </button>
      {open && (
        <ol id="all-ranks" className="rank-list">
          {RANKS.map((r) => (
            <li key={r}>
              <RankMedal rank={r} size={40} />
              <span className="rank-list-text">
                <strong>{r}</strong>
                <span className="muted small">{rankRange(r)} age grade</span>
              </span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

export default function CompareCard() {
  const [data, setData] = useState<Comparison | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.comparison().then(setData, (e: Error) => setError(e.message));
  }, []);

  if (!data) return error ? <section className="card"><p className="error">{error}</p></section> : null;
  const { profile, rows, overall, sources } = data;
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
          {overall && <RankHeader overall={overall} />}
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
                  <th>Rank</th>
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
                    </td>
                    <td>
                      {r.rank ? (
                        <span className="rank-cell">
                          <RankMedal rank={r.rank} size={22} />
                          {r.rank}
                        </span>
                      ) : (
                        <span className="muted">–</span>
                      )}
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
          <AllRanks />
          <ul className="facts small">
            <li>
              <strong>Ranks</strong> come from age grade, so they're fair across ages, sexes and distances. Your rank
              is your best age grade from a time you've actually run at 5k, 10k, half or marathon, or a prediction
              at a distance you've run near (long predictions don't count).
            </li>
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
