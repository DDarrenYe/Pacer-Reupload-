import { describe, expect, it } from "vitest";

import { goalProgress } from "./goalProgress";

describe("goalProgress", () => {
  it("measures how much of today's gap race day closes", () => {
    // 2:01:59 now, 2:00:35 projected, 1:59:00 target: 84 of 179 seconds closed
    const p = goalProgress(7319, 7235, 7140);
    expect(p.pct).toBe(47);
    expect(p.headline).toBe("About halfway there by race day");
    expect(p.left).toBe("1:35 still to find");
  });

  it("is full when you're on track or already there", () => {
    expect(goalProgress(7300, 7100, 7140)).toMatchObject({ pct: 100, headline: "On track to hit it by race day" });
    expect(goalProgress(7000, 7000, 7140)).toMatchObject({ pct: 100, headline: "You're already there" });
  });

  it("never goes below zero when the trend is getting slower", () => {
    expect(goalProgress(7300, 7400, 7140)).toMatchObject({ pct: 0, headline: "Not much closer by race day at this rate" });
    expect(goalProgress(7300, null, 7140).pct).toBe(0);
  });
});
