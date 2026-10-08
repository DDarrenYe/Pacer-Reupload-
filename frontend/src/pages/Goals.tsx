import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api";
import { useAuth } from "../auth";
import { LineChart } from "../components/charts";
import GoalForm, { goalDistanceLabel } from "../components/GoalForm";
import { describeCountdown, describeGap, formatDate, formatDuration, formatPace, formatShortDate } from "../format";
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

const versusTarget = (gap: number) => (Math.abs(gap) < 1 ? "right on target" : `${describeGap(gap)} than target`);

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
  return (
    <section className="card stack" aria-labelledby={`goal-${goal.id}`}>
      <div className="goal-header">
        <div>
          <h2 id={`goal-${goal.id}`}>{goal.name}</h2>
          <p className="muted">
            {distance} on {formatDate(`${goal.race_date}T00:00:00`)}, {describeCountdown(a.days_left)}
          </p>
        </div>
        <span className={`status status-${a.status}`}>{STATUS_LABELS[a.status]}</span>
      </div>

      <div className="tiles goal-tiles">
        <div className="tile">
          <div className="tile-label">Target</div>
          <div className="tile-value">{formatDuration(target)}</div>
          <div className="tile-note">{formatPace(a.target_pace_s_per_km)}</div>
        </div>
        {a.status === "passed" ? (
          <div className="tile">
            <div className="tile-label">Result</div>
            <div className="tile-value">{a.result_s === null ? "–" : formatDuration(a.result_s)}</div>
            {a.result_s !== null && <div className="tile-note">{describeGap(a.result_s - target)}</div>}
          </div>
        ) : (
          <>
            <div className="tile">
              <div className="tile-label">Predicted now</div>
              <div className="tile-value">{a.now_s === null ? "–" : formatDuration(a.now_s)}</div>
              {a.now_s !== null && <div className="tile-note">{versusTarget(a.now_s - target)}</div>}
            </div>
            <div className="tile">
              <div className="tile-label">Projected on race day</div>
              <div className="tile-value">{a.projected_s === null ? "–" : formatDuration(a.projected_s)}</div>
              {a.projected_s !== null && (
                <div className="tile-note">
                  {versusTarget(a.projected_s - target)}
                  {a.projection_basis === "current" && ", if fitness holds"}
                </div>
              )}
            </div>
          </>
        )}
      </div>

      <p className="goal-verdict">
        <strong>{STATUS_LABELS[a.status]}.</strong> {statusSentence(a)}
      </p>

      {(a.anchor || a.projection_note) && (
        <ul className="facts">
          {a.anchor && <li>The prediction starts from {a.anchor}.</li>}
          {a.projection_note && <li>{a.projection_note}</li>}
        </ul>
      )}

      {chartPoints.length > 1 && (
        <LineChart
          title={`Predicted ${distance.toLowerCase()} time`}
          labels={chartPoints.map((w) => formatShortDate(w.week_end))}
          values={chartPoints.map((w) => w.predicted_s)}
          format={formatDuration}
          lowerIsBetter
          references={[{ value: target, label: `target ${formatDuration(target)}` }]}
        />
      )}

      {a.equivalents.length > 0 && a.status !== "passed" && (
        <p className="muted goal-verdict">
          Checkpoints at the same fitness:{" "}
          {a.equivalents.map((e) => `${e.name} in ${formatDuration(e.time_s)}`).join(", ")}.
        </p>
      )}

      {a.recommendations.length > 0 && (
        <>
          <h3 className="goal-subhead">What to do</h3>
          <ol className="steps">
            {a.recommendations.map((r) => <li key={r}>{r}</li>)}
          </ol>
        </>
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
          <button onClick={() => setAdding(true)}>Add a goal</button>
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
