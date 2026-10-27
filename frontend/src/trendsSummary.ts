import type { Week } from "./types";

export interface TrendsSummary {
  /** Average weekly distance over the last 4 full weeks, and the 4 before. */
  weeklyKm: number | null;
  prevWeeklyKm: number | null;
  /** Total climb over the last 4 full weeks (null if none of those runs had elevation). */
  climbM: number | null;
  prevClimbM: number | null;
  /** Distance-weighted average pace over the last 4 full weeks, s/km. */
  paceS: number | null;
  prevPaceS: number | null;
  /** The latest predicted 5k, and the one 6 weeks before it. */
  fiveK: number | null;
  prevFiveK: number | null;
}

const WINDOW = 4;
const FIVE_K_LOOKBACK = 6;

function sumOrNull(values: (number | null)[]): number | null {
  const real = values.filter((v): v is number => v !== null);
  return real.length ? real.reduce((a, b) => a + b, 0) : null;
}

function weightedPace(weeks: Week[]): number | null {
  const run = weeks.filter((w) => w.avg_pace_s_per_km !== null && w.distance_km > 0);
  const km = run.reduce((a, w) => a + w.distance_km, 0);
  return km ? run.reduce((a, w) => a + (w.avg_pace_s_per_km as number) * w.distance_km, 0) / km : null;
}

/** The value at `i`, or the nearest one before it (weeks with no prediction are null). */
function earlier(values: (number | null)[], i: number): number | null {
  for (let j = i; j >= 0; j--) if (values[j] !== null) return values[j];
  return null;
}

/** Headline numbers for the Trends page. `weeks` is oldest first, ending with the current
 * (unfinished) week, which is left out so a Monday doesn't look like a collapse. */
export function summarise(weeks: Week[]): TrendsSummary {
  const full = weeks.slice(0, -1);
  const recent = full.slice(-WINDOW);
  const prev = full.slice(-2 * WINDOW, -WINDOW);
  const avgKm = (ws: Week[]) => (ws.length === WINDOW ? ws.reduce((a, w) => a + w.distance_km, 0) / WINDOW : null);
  const fives = weeks.map((w) => w.predicted_5k_s);
  const lastIdx = fives.map((v, i) => (v === null ? -1 : i)).reduce((a, b) => Math.max(a, b), -1);
  return {
    weeklyKm: avgKm(recent),
    prevWeeklyKm: avgKm(prev),
    climbM: sumOrNull(recent.map((w) => w.elevation_gain_m)),
    prevClimbM: prev.length === WINDOW ? sumOrNull(prev.map((w) => w.elevation_gain_m)) : null,
    paceS: weightedPace(recent),
    prevPaceS: prev.length === WINDOW ? weightedPace(prev) : null,
    fiveK: lastIdx >= 0 ? fives[lastIdx] : null,
    prevFiveK: earlier(fives, lastIdx - FIVE_K_LOOKBACK),
  };
}

/** "+8%" / "−12%", or null when there's nothing to compare with. */
export function percentChange(now: number | null, before: number | null): number | null {
  if (now === null || before === null || before === 0) return null;
  return Math.round(((now - before) / before) * 100);
}

export type LoadStatus = "easing" | "balanced" | "spike";

/** Where an acute:chronic workload ratio sits against the usual 0.8–1.5 range. */
export function loadStatus(acwr: number): LoadStatus {
  if (acwr < 0.8) return "easing";
  if (acwr > 1.5) return "spike";
  return "balanced";
}
