import { describe, expect, it } from "vitest";

import { averagePace, monthDistanceM } from "./runnerStats";
import type { Run } from "./types";

const run = (started_at: string, distance_m: number, moving_time_s: number) =>
  ({ started_at, distance_m, moving_time_s }) as Run;

describe("runner stats", () => {
  const now = new Date(2026, 9, 13, 12); // 13 Oct 2026, local time
  const runs = [
    run(new Date(2026, 9, 2, 7).toISOString(), 5000, 1500),
    run(new Date(2026, 9, 12, 7).toISOString(), 10000, 3300),
    run(new Date(2026, 8, 30, 7).toISOString(), 8000, 2400), // last month
    run(new Date(2025, 9, 5, 7).toISOString(), 6000, 1800), // October, but last year
  ];
  it("adds up this month only", () => expect(monthDistanceM(runs, now)).toBe(15000));
  it("averages pace by total time over total distance", () =>
    expect(averagePace(runs)).toBeCloseTo((1500 + 3300 + 2400 + 1800) / 29, 6));
  it("has no pace without runs", () => expect(averagePace([])).toBeNull());
});
