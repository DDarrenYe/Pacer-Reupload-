import type { Run } from "./types";

/** Total distance of runs started this calendar month, in your local time. */
export function monthDistanceM(runs: Run[], now = new Date()): number {
  return runs
    .filter((r) => {
      const d = new Date(r.started_at);
      return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth();
    })
    .reduce((sum, r) => sum + r.distance_m, 0);
}

/** Average pace over all your runs (total time / total distance), or null with none. */
export function averagePace(runs: Run[]): number | null {
  const distance = runs.reduce((sum, r) => sum + r.distance_m, 0);
  const time = runs.reduce((sum, r) => sum + r.moving_time_s, 0);
  return distance > 0 ? time / (distance / 1000) : null;
}
