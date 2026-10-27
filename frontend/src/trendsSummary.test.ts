import { describe, expect, it } from "vitest";

import { loadStatus, percentChange, summarise } from "./trendsSummary";
import type { Week } from "./types";

const week = (km: number, extra: Partial<Week> = {}): Week => ({
  week_start: "2026-01-05",
  runs: km ? 1 : 0,
  distance_km: km,
  avg_pace_s_per_km: km ? 300 : null,
  predicted_5k_s: null,
  elevation_gain_m: null,
  ...extra,
});

describe("summarise", () => {
  it("compares the last 4 full weeks with the 4 before, ignoring this week", () => {
    const weeks = [20, 20, 20, 20, 30, 30, 30, 30, 2].map((km) => week(km));
    const s = summarise(weeks);
    expect(s.weeklyKm).toBe(30);
    expect(s.prevWeeklyKm).toBe(20);
    expect(percentChange(s.weeklyKm, s.prevWeeklyKm)).toBe(50);
  });

  it("weights pace by distance and sums climb only where it exists", () => {
    const weeks = [
      week(10, { avg_pace_s_per_km: 300, elevation_gain_m: 100 }),
      week(30, { avg_pace_s_per_km: 340 }),
      week(0),
      week(0),
      week(5),
    ];
    const s = summarise(weeks);
    expect(s.paceS).toBe(330);
    expect(s.climbM).toBe(100);
    expect(s.prevWeeklyKm).toBeNull();
  });

  it("takes the latest predicted 5k and the one 6 weeks earlier", () => {
    const fives = [1300, 1295, 1290, 1280, 1280, 1270, 1260, 1250, null];
    const s = summarise(fives.map((v) => week(10, { predicted_5k_s: v })));
    expect(s.fiveK).toBe(1250);
    expect(s.prevFiveK).toBe(1295);
    // A gap 6 weeks back falls back to the prediction before it
    const gappy = summarise([1300, null, ...fives.slice(2)].map((v) => week(10, { predicted_5k_s: v })));
    expect(gappy.prevFiveK).toBe(1300);
  });
});

describe("loadStatus", () => {
  it("bands the ratio", () => {
    expect(loadStatus(0.7)).toBe("easing");
    expect(loadStatus(1.04)).toBe("balanced");
    expect(loadStatus(1.6)).toBe("spike");
  });
});
