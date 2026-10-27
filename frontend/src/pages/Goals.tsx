import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api";
import { useAuth } from "../auth";
import { LineChart } from "../components/charts";
import GoalForm, { goalDistanceLabel } from "../components/GoalForm";
import { describeCountdown, describeGap, formatDuration, formatPace, formatShortDate } from "../format";
import { goalProgress } from "../goalProgress";
import type { Goal, GoalAnalysis } from "../types";
import { useSlowNotice } from "../useSlowNotice";
import { useTitle } from "../useTitle";

const STATUS_LABELS: Record<GoalAnalysis["status"], string> = {
  no_data: "Not enough data",
  already_there: "Already there",
  on_track: "On track",
  within_reach: "Within reach",
  stretch: "Stretch",
  passed: "Race day passed",
};

function statusSentence(a: GoalAnalysis): string {
  switch (a.status) {
    case "no_data":
      return "Pacer needs a recent hard effort before it can predict this race.";
    case "already_there":
      return "Your current fitness already predicts this time or faster. Stay healthy and consistent.";
    case "on_track":
      return "If your recent improvement carries on, you'll reach this time by race day.";
    case "within_reach":
      return `You'd need to improve by about ${a.needed_pct_per_week}% a week. That's realistic for most runners with steady training.`;
    case "stretch":
      return `You'd need to improve by about ${a.needed_pct_per_week}% a week. Most runners manage up to 0.5%, so this is ambitious; consider a later race or a softer target.`;
    case "passed":
      if (a.result_s === null) return "No run of this distance was found within a day of the race. Upload it to see how you did.";
      return a.result_hit ? "You hit your goal. Well done!" : "You didn't quite make it this time.";
  }
}

function GoalCard({ goal, demo, onChanged }: { goal: Goal; demo: boolean; onChanged: () => void }) {
  const [editing, setEditing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showTrend, setShowTrend] = useState(false);
  const a = goal.analysis;
  const target = goal.target_time_s;

  async function remove() {
    if (!confirm(`Delete the goal "${goal.name}"?`)) return;
    setDeleting(true);
    try {
      await api.deleteGoal(goal.id);
      onChanged();
    } catch (e) {
      setError((e as Error).message);
      setDeleting(false);
    }
  }

  if (editing) {
    return (
      <section className="card stack">
        <h2>Edit goal</h2>
        <GoalForm goal={goal} onSaved={() => { setEditing(false); onChanged(); }} onCancel={() => setEditing(false)} />
      </section>
    );
  }

  const distance = goalDistanceLabel(goal.distance_m / 1000);
  const chartPoints = a.weekly.filter((w) => w.predicted_s !== null);
  const raceDay = new Date(`${goal.race_date}T00:00:00`).toLocaleDateString(undefined, {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
  });
  const progress = a.now_s !== null ? goalProgress(a.now_s, a.projected_s, target) : null;

  return (
    <section className="card stack goal-card" aria-labelledby={`goal-${goal.id}`}>
      <div className="goal-header">
        <div>
          <h2 id={`goal-${goal.id}`}>{goal.name}</h2>
          <p className="muted">{distance} · {raceDay} · {describeCountdown(a.days_left)}</p>
        </div>
        <span className={`badge ${STATUS_TONE[a.status === "passed" && a.result_hit ? "on_track" : a.status]}`}>
          {STATUS_LABELS[a.status]}
        </span>
      </div>

      {a.status === "passed" ? (
        <div className="goal-flow">
          <FlowValue label="Target" value={formatDuration(target)} />
          <Arrow />
          <FlowValue
            label="Result"
            value={a.result_s === null ? "–" : formatDuration(a.result_s)}
            note={a.result_s === null ? undefined : describeGap(a.result_s - target)}
            accent
          />
        </div>
      ) : a.now_s !== null && progress ? (
        <>
          <div className="goal-flow">
            <FlowValue label="Now" value={formatDuration(a.now_s)} />
            <Arrow />
            <FlowValue
              label={a.projection_basis === "current" ? "Race day (if fitness holds)" : "Race day (at your current rate)"}
              value={a.projected_s === null ? "–" : formatDuration(a.projected_s)}
              accent
            />
            <Arrow />
            <FlowValue label="Target" value={formatDuration(target)} note={formatPace(a.target_pace_s_per_km)} />
          </div>
          <div className="goal-progress">
            <div className="goal-progress-head">
              <strong>{progress.headline}</strong>
              <span className="muted">{progress.left}</span>
            </div>
            <div
              className="progress"
              role="progressbar"
              aria-label="Share of the gap to your target closed by race day"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={progress.pct}
            >
              <div style={{ width: `${Math.max(progress.pct, 2)}%` }} />
            </div>
            <p className="muted small">
              {a.now_s > target ? `You're ${formatDuration(a.now_s - target)} off your target today. ` : ""}
              {statusSentence(a)}
            </p>
          </div>
        </>
      ) : (
        <p style={{ margin: 0 }}>{statusSentence(a)}</p>
      )}
      {a.status === "passed" && <p style={{ margin: 0 }}>{statusSentence(a)}</p>}

      {a.status !== "passed" && (a.recommendations.length > 0 || a.equivalents.length > 0) && (
        <div className="two-col goal-extras">
          {a.recommendations.length > 0 && (
            <div className="inset stack">
              <h3>This week's focus</h3>
              <ul className="focus-list">
                {a.recommendations.map((r) => <li key={r}>{r}</li>)}
              </ul>
            </div>
          )}
          {a.equivalents.length > 0 && (
            <div className="inset stack">
              <h3>Same fitness at other distances</h3>
              <div className="actions">
                {a.equivalents.map((e) => (
                  <div key={e.name} className="equiv">
                    <span className="tile-label">{e.name}</span>
                    <span className="effort-time">{formatDuration(e.time_s)}</span>
                  </div>
                ))}
              </div>
              {chartPoints.length > 1 && (
                <button className="link" style={{ justifySelf: "start" }} aria-expanded={showTrend} onClick={() => setShowTrend((v) => !v)}>
                  {showTrend ? "Hide the trend ▴" : `See the ${chartPoints.length}-week trend ▾`}
                </button>
              )}
            </div>
          )}
        </div>
      )}

      {showTrend && chartPoints.length > 1 && (
        <LineChart
          title={`Predicted ${distance.toLowerCase()} time`}
          labels={chartPoints.map((w) => formatShortDate(w.week_end))}
          values={chartPoints.map((w) => w.predicted_s)}
          format={formatDuration}
          lowerIsBetter
          references={[{ value: target, label: `target ${formatDuration(target)}` }]}
        />
      )}

      {(a.anchor || a.projection_note) && a.status !== "passed" && (
        <p className="muted small">
          {a.anchor && <>Predictions start from {a.anchor}. </>}
          {a.projection_note}
        </p>
      )}

      {error && <p className="error" role="alert">{error}</p>}
      {!demo && (
        <div className="actions">
          <button className="secondary" onClick={() => setEditing(true)}>Edit</button>
          <button className="danger" onClick={remove} disabled={deleting}>{deleting ? "Deleting…" : "Delete"}</button>
        </div>
      )}
    </section>
  );
}

const STATUS_TONE: Record<GoalAnalysis["status"], string> = {
  no_data: "",
  already_there: "good",
  on_track: "good",
  within_reach: "",
  stretch: "warn",
  passed: "warn",
};

function FlowValue({ label, value, note, accent }: { label: string; value: string; note?: string; accent?: boolean }) {
  return (
    <div className="flow-value">
      <span className="tile-label">{label}</span>
      <span className={accent ? "flow-number accent" : "flow-number"}>{value}</span>
      {note && <span className="muted small">{note}</span>}
    </div>
  );
}

function Arrow() {
  return (
    <svg className="flow-arrow" width="24" height="24" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 12h14M13 6l6 6-6 6" />
    </svg>
  );
}

export default function Goals() {
  useTitle("Goals");
  const { demo } = useAuth();
  const [goals, setGoals] = useState<Goal[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const slow = useSlowNotice(goals === null && !error);

  const load = useCallback(() => {
    api.listGoals().then(setGoals, (e: Error) => setError(e.message));
  }, []);
  useEffect(load, [load]);

  const showForm = !demo && (adding || goals?.length === 0);

  return (
    <main>
      <div className="page-header">
        <h1>Goals</h1>
        {!demo && goals && goals.length > 0 && !adding && (
          <button onClick={() => setAdding(true)}>+ New goal</button>
        )}
      </div>
      {error && <p className="error">{error}</p>}
      {goals === null && !error && (
        <p className="muted">{slow ? "Waking up the server; this can take up to a minute…" : "Loading…"}</p>
      )}
      {showForm && (
        <section className="card stack">
          <h2>New goal</h2>
          {goals?.length === 0 && (
            <p className="muted">
              Pick a race and a target time. Pacer compares it with what your recent runs predict, shows where your
              trend is heading by race day, and suggests what to work on.
            </p>
          )}
          <GoalForm
            onSaved={() => { setAdding(false); load(); }}
            onCancel={goals && goals.length > 0 ? () => setAdding(false) : undefined}
          />
        </section>
      )}
      {demo && goals?.length === 0 && <p className="muted">The demo has no goals. <Link to="/">See its runs</Link></p>}
      {goals?.map((g) => <GoalCard key={g.id} goal={g} demo={demo} onChanged={load} />)}
      {goals && goals.length > 0 && (
        <p className="muted small">
          Predictions use Riegel's formula from your nearest recent hard effort, the same as the Trends page. Advice is
          a rule-of-thumb starting point, not a coaching plan.
        </p>
      )}
    </main>
  );
}
