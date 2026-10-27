import { describe, expect, it } from "vitest";

import { runMeta } from "./runMeta";

const base = { surface: "road", split_type: null, source: "gpx", is_race: false, strava_activity_id: null } as const;

describe("runMeta", () => {
  it("names the surface and split", () =>
    expect(runMeta({ ...base, split_type: "even" })).toBe("Road · even split"));
  it("marks races and Strava imports", () =>
    expect(runMeta({ ...base, is_race: true, strava_activity_id: 42 })).toBe("Road · race · Strava"));
  it("says when a run was typed in", () =>
    expect(runMeta({ ...base, surface: "treadmill", source: "manual" })).toBe("Treadmill · entered manually"));
});
