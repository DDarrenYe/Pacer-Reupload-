import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api";
import { BarChart, LineChart } from "../components/charts";
import { describeExponent, formatDuration, formatPace, formatShortDate } from "../format";
import { loadStatus, percentChange, summarise } from "../trendsSummary";
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

const RANGES = [
  { weeks: 12, label: "12 weeks" },
  { weeks: 26, label: "26 weeks" },
  { weeks: 52, label: "1 year" },
];
type Measure = "distance" | "elevation" | "pace" | "fiveK";
const MEASURES: { id: Measure; label: string; title: string }[] = [
  { id: "distance", label: "Distance", title: "Weekly distance" },
  { id: "elevation", label: "Elevation", title: "Weekly elevation gain" },
  { id: "pace", label: "Pace", title: "Average pace" },
  { id: "fiveK", label: "Predicted 5k", title: "Predicted 5k" },
];

const LOAD_TEXT = {
  easing: { label: "Easing off", tone: "", text: "You're doing less than your usual: fine for a recovery or taper week." },
  balanced: { label: "Balanced", tone: "good", text: "This week's load is in line with your last four weeks. Safe to build by about 10%." },
  spike: { label: "Spike", tone: "warn", text: "A big jump on your recent weeks. Injury risk rises above 1.5, so ease back for a few days." },
};

export default function Trends() {
  useTitle("Trends");
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [range, setRange] = useState(26);
  const [measure, setMeasure] = useState<Measure>("distance");
  const [showLoadHistory, setShowLoadHistory] = useState(false);
  const slow = useSlowNotice(data === null && !error);

  useEffect(() => {
    Promise.all([api.predictions(), api.evaluation(), api.trends(26), api.trainingLoad(84)]).then(
      ([predictions, evaluation, weeks, load]) => setData({ predictions, evaluation, weeks, load }),
      (e: Error) => setError(e.message),
    );
  }, []);

  function pickRange(weeks: number) {
    setRange(weeks);
    api.trends(weeks).then(
      (w) => setData((d) => (d ? { ...d, weeks: w } : d)),
      (e: Error) => setError(e.message),
    );
  }

  if (error) return <main><p className="error">{error}</p></main>;
  if (!data) return <main><p className="muted">{slow ? "Waking up the server; this can take up to a minute…" : "Loading…"}</p></main>;

  const { predictions: p, evaluation: ev, load } = data;
  // Start the chart at the first week with a run, not months of empty space.
  const firstActive = data.weeks.findIndex((w) => w.runs > 0);
  const weeks = firstActive === -1 ? [] : data.weeks.slice(firstActive);
  const weekLabels = weeks.map((w) => formatShortDate(w.week_start));
  const sum = summarise(data.weeks);
  const loadWithRatio = load.filter((d) => d.acwr !== null);
  const acwr = loadWithRatio.length ? (loadWithRatio[loadWithRatio.length - 1].acwr as number) : null;
  const status = acwr === null ? null : LOAD_TEXT[loadStatus(acwr)];
  const anyExtrapolated = p.predictions.some((x) => x.extrapolated);
  const anchors = [...new Set(p.predictions.map((x) => x.anchor_name).filter(Boolean))];
  const current = MEASURES.find((m) => m.id === measure)!;

  const kmChange = percentChange(sum.weeklyKm, sum.prevWeeklyKm);
  const climbChange = percentChange(sum.climbM, sum.prevClimbM);
  const paceFaster = sum.paceS !== null && sum.prevPaceS !== null ? Math.round(sum.prevPaceS - sum.paceS) : null;
  const fiveKFaster = sum.fiveK !== null && sum.prevFiveK !== null ? Math.round(sum.prevFiveK - sum.fiveK) : null;

  return (
    <main>
      <div className="page-header">
        <h1>Trends</h1>
        <div className="segmented" role="group" aria-label="Time range">
          {RANGES.map((r) => (
            <button key={r.weeks} aria-pressed={range === r.weeks} onClick={() => pickRange(r.weeks)}>{r.label}</button>
          ))}
        </div>
      </div>

      <section className="kpis" aria-label="The last 4 weeks">
        <Kpi
          label="Weekly average"
          value={sum.weeklyKm === null ? "–" : `${sum.weeklyKm.toFixed(1)} km`}
          delta={kmChange === null ? "Last 4 full weeks" : `${signed(kmChange)}% vs the 4 before`}
          up={kmChange !== null && kmChange > 0}
        />
        <Kpi
          label="Climb, last 4 weeks"
          value={sum.climbM === null ? "–" : `${Math.round(sum.climbM)} m`}
          delta={sum.climbM === null ? "GPS runs only" : climbChange === null ? "GPS runs only" : `${signed(climbChange)}% vs the 4 before`}
          up={climbChange !== null && climbChange > 0}
        />
        <Kpi
          label="Average pace"
          value={sum.paceS === null ? "–" : formatPace(sum.paceS)}
          delta={paceFaster === null ? "Last 4 full weeks" : paceFaster === 0 ? "Same as the 4 before" : `${Math.abs(paceFaster)} s/km ${paceFaster > 0 ? "faster" : "slower"}`}
          up={paceFaster !== null && paceFaster > 0}
        />
        <Kpi
          label="Predicted 5k"
          value={sum.fiveK === null ? "–" : formatDuration(sum.fiveK)}
          delta={fiveKFaster === null ? "From your hard efforts" : fiveKFaster === 0 ? "No change in 6 weeks" : `${formatDuration(Math.abs(fiveKFaster))} ${fiveKFaster > 0 ? "faster" : "slower"} than 6 weeks ago`}
          up={fiveKFaster !== null && fiveKFaster > 0}
        />
      </section>

      <section className="card">
        <div className="section-head">
          <h2>{current.title}</h2>
          <div className="pills" role="group" aria-label="Measure">
            {MEASURES.map((m) => (
              <button key={m.id} aria-pressed={measure === m.id} onClick={() => setMeasure(m.id)}>{m.label}</button>
            ))}
          </div>
        </div>
        {weeks.length === 0 ? (
          <p className="muted">Upload a run to see your weekly trends.</p>
        ) : measure === "distance" ? (
          <BarChart bare title={current.title} labels={weekLabels} values={weeks.map((w) => w.distance_km)} format={(v) => `${Math.round(v)} km`} />
        ) : measure === "elevation" ? (
          <BarChart bare title={current.title} note="GPS runs only" labels={weekLabels} values={weeks.map((w) => w.elevation_gain_m)} format={(v) => `${Math.round(v)} m`} />
        ) : measure === "pace" ? (
          <LineChart bare title={current.title} labels={weekLabels} values={weeks.map((w) => w.avg_pace_s_per_km)} format={formatDuration} lowerIsBetter />
        ) : (
          <LineChart bare title={current.title} labels={weekLabels} values={weeks.map((w) => w.predicted_5k_s)} format={formatDuration} lowerIsBetter />
        )}
      </section>

      <div className="two-col">
        <section className="card stack">
          <div className="section-head">
            <h2>Training load</h2>
            {status && acwr !== null && <span className={`badge ${status.tone}`}>{status.label} · {acwr.toFixed(2)}</span>}
          </div>
          {acwr === null || !status ? (
            <p className="muted" style={{ margin: 0 }}>Your training load appears after 3 weeks of runs.</p>
          ) : (
            <>
              <div>
                <div className="gauge" role="img" aria-label={`Load ratio ${acwr.toFixed(2)}: ${status.label}`}>
                  <span className="gauge-mark" style={{ left: `${(Math.min(acwr, 2) / 2) * 100}%` }} />
                </div>
                <div className="gauge-scale" aria-hidden="true"><span>Easing off</span><span>Sweet spot 0.8–1.5</span><span>Spike</span></div>
              </div>
              <p style={{ margin: 0 }}>{status.text}</p>
              <button className="link" style={{ justifySelf: "start" }} aria-expanded={showLoadHistory} onClick={() => setShowLoadHistory((v) => !v)}>
                {showLoadHistory ? "Hide the last 12 weeks ▴" : "See the last 12 weeks ▾"}
              </button>
              {showLoadHistory && (
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
              )}
            </>
          )}
        </section>

        <section className={p.envelope_size === 0 ? "card stack" : "card stack wide"}>
          <h2 style={{ margin: 0 }}>Race predictions</h2>
          {p.envelope_size === 0 ? (
            <>
              <p className="muted" style={{ margin: 0 }}>
                No hard efforts in the last 180 days. Mark a run as a race, or upload a GPX of a hard effort, to unlock
                predictions and how accurate they've been.
              </p>
              <Link to="/" className="button secondary" style={{ justifySelf: "start" }}>Add a race</Link>
            </>
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
              <ul className="facts small">
                <li>{describeExponent(p.personal_exponent)}</li>
                {anchors.length > 0 && <li>Riegel predictions start from your nearest recent effort: {anchors.join("; ")}.</li>}
                {anyExtrapolated && <li>"Extrapolated" means more than twice your longest recent effort, so treat it as a rough guide.</li>}
                {p.pooled_exponent === null && <li>The pooled model needs more runners' data before it can be fitted.</li>}
              </ul>
              <h3 style={{ margin: 0 }}>How accurate has each method been?</h3>
              {ev.enough_data ? (
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr><th>Method</th><th className="num">Average error</th><th className="num">As %</th><th className="num">Tested on</th></tr>
                    </thead>
                    <tbody>
                      {ev.scores.map((sc) => (
                        <tr key={sc.method}>
                          <td>{sc.method}</td>
                          <td className="num">{sc.mae_s === null ? "–" : `${Math.round(sc.mae_s)} s`}</td>
                          <td className="num">{sc.mape_pct === null ? "–" : `${sc.mape_pct.toFixed(1)}%`}</td>
                          <td className="num">{sc.n}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="muted small">
                  Not enough data yet ({ev.n_pairs} hard efforts with an earlier effort to predict from). Each method is
                  scored on the most recent 30% of efforts, predicted only from runs before them.
                </p>
              )}
            </>
          )}
        </section>
      </div>
    </main>
  );
}

const signed = (n: number) => (n > 0 ? `+${n}` : `${n}`);

function Kpi({ label, value, delta, up }: { label: string; value: string; delta: string; up: boolean }) {
  return (
    <div className="kpi">
      <span className="kpi-label">{label}</span>
      <span className="kpi-value">{value}</span>
      <span className={up ? "kpi-delta up" : "kpi-delta"}>{delta}</span>
    </div>
  );
}
