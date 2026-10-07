import { useEffect, useState } from "react";

import { api } from "../api";
import { BarChart, LineChart } from "../components/charts";
import { describeExponent, formatDuration, formatShortDate } from "../format";
import type { Evaluation, LoadDay, RunnerPredictions, Week } from "../types";
import { useSlowNotice } from "../useSlowNotice";
import { useTitle } from "../useTitle";

interface Data {
  predictions: RunnerPredictions;
  evaluation: Evaluation;
  weeks: Week[];
  load: LoadDay[];
}

const time = (s: number | null) => (s === null ? "–" : formatDuration(s));

export default function Trends() {
  useTitle("Trends");
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState<string | null>(null);
  const slow = useSlowNotice(data === null && !error);

  useEffect(() => {
    Promise.all([api.predictions(), api.evaluation(), api.trends(26), api.trainingLoad(84)]).then(
      ([predictions, evaluation, weeks, load]) => setData({ predictions, evaluation, weeks, load }),
      (e: Error) => setError(e.message),
    );
  }, []);

  if (error) return <main><p className="error">{error}</p></main>;
  if (!data) return <main><p className="muted">{slow ? "Waking up the server; this can take up to a minute…" : "Loading…"}</p></main>;

  const { predictions: p, evaluation: ev, load } = data;
  // Start the charts at the first week with a run, not 26 weeks of empty space.
  const firstActive = data.weeks.findIndex((w) => w.runs > 0);
  const weeks = firstActive === -1 ? [] : data.weeks.slice(firstActive);
  const weekLabels = weeks.map((w) => formatShortDate(w.week_start));
  const loadWithRatio = load.filter((d) => d.acwr !== null);
  const anyExtrapolated = p.predictions.some((x) => x.extrapolated);
  const anchors = [...new Set(p.predictions.map((x) => x.anchor_name).filter(Boolean))];

  return (
    <main>
      <h1>Trends</h1>

      <section className="card">
        <h2>Race predictions</h2>
        {p.envelope_size === 0 ? (
          <p className="muted">
            No recent hard efforts yet. Upload GPX runs (or CSV races) from the last 180 days and tick "This was a race" for races.
          </p>
        ) : (
          <>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Distance</th>
                    <th className="num">Riegel (1.06)</th>
                    <th className="num">Your exponent</th>
                    <th className="num">Pooled model</th>
                  </tr>
                </thead>
                <tbody>
                  {p.predictions.map((x) => (
                    <tr key={x.name}>
                      <td>
                        {x.name}
                        {x.extrapolated && <span className="tag">extrapolated</span>}
                      </td>
                      <td className="num">{time(x.riegel_s)}</td>
                      <td className="num">{time(x.personal_s)}</td>
                      <td className="num">{time(x.pooled_s)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <ul className="facts">
              <li>{describeExponent(p.personal_exponent)}</li>
              {anchors.length > 0 && <li>Riegel predictions start from your nearest recent effort: {anchors.join("; ")}.</li>}
              {anyExtrapolated && <li>"Extrapolated" means more than twice your longest recent effort, so treat it as a rough guide.</li>}
              {p.pooled_exponent === null && <li>The pooled model needs more runners' data before it can be fitted.</li>}
            </ul>
          </>
        )}
        <h3>How accurate has each method been?</h3>
        {ev.enough_data ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr><th>Method</th><th className="num">Average error</th><th className="num">As %</th><th className="num">Tested on</th></tr>
              </thead>
              <tbody>
                {ev.scores.map((s) => (
                  <tr key={s.method}>
                    <td>{s.method}</td>
                    <td className="num">{s.mae_s === null ? "–" : `${Math.round(s.mae_s)} s`}</td>
                    <td className="num">{s.mape_pct === null ? "–" : `${s.mape_pct.toFixed(1)}%`}</td>
                    <td className="num">{s.n}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="muted">
            Not enough data yet ({ev.n_pairs} hard efforts with an earlier effort to predict from). Each method is scored on
            the most recent 30% of efforts, predicted only from runs before them.
          </p>
        )}
      </section>

      <section className="card">
        <h2>Weekly trends</h2>
        {weeks.length === 0 && <p className="muted">Upload a run to see your weekly trends.</p>}
        <div className="charts">
          <BarChart title="Weekly distance" labels={weekLabels} values={weeks.map((w) => w.distance_km)} format={(v) => `${Math.round(v)} km`} />
          <LineChart title="Average pace" labels={weekLabels} values={weeks.map((w) => w.avg_pace_s_per_km)} format={formatDuration} lowerIsBetter />
          <LineChart title="Predicted 5k" labels={weekLabels} values={weeks.map((w) => w.predicted_5k_s)} format={formatDuration} lowerIsBetter />
          {loadWithRatio.length > 0 ? (
            <LineChart
              title="Training load ratio (ACWR)"
              labels={loadWithRatio.map((d) => formatShortDate(d.date))}
              values={loadWithRatio.map((d) => d.acwr)}
              format={(v) => v.toFixed(2)}
              references={[
                { value: 1.5, label: "1.5 spike" },
                { value: 0.8, label: "0.8 drop" },
              ]}
            />
          ) : (
            <p className="muted">The training load ratio appears after 3 weeks of runs.</p>
          )}
        </div>
      </section>
    </main>
  );
}
