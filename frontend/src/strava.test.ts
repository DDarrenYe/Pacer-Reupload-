import { beforeEach, describe, expect, it } from "vitest";

import { checkStravaState, describeSync, stravaActivityUrl } from "./strava";

describe("describeSync", () => {
  it("counts imports", () => expect(describeSync({ imported: 3, skipped: 0, more: false })).toBe("Imported 3 runs."));
  it("handles nothing new", () => expect(describeSync({ imported: 0, skipped: 0, more: false })).toBe("No new runs."));
  it("mentions skips and more", () =>
    expect(describeSync({ imported: 1, skipped: 2, more: true })).toBe(
      "Imported 1 run, skipped 2 (not runs, or already here). There are more to fetch: sync again.",
    ));
});

describe("checkStravaState", () => {
  beforeEach(() => {
    const data = new Map<string, string>();
    const storage = {
      getItem: (k: string) => data.get(k) ?? null,
      setItem: (k: string, v: string) => void data.set(k, v),
      removeItem: (k: string) => void data.delete(k),
    };
    Object.assign(globalThis, { sessionStorage: storage });
  });
  it("accepts the state this tab sent, once", () => {
    sessionStorage.setItem("pacer-strava-state", "abc");
    expect(checkStravaState("abc")).toBe(true);
    expect(checkStravaState("abc")).toBe(false);
  });
  it("rejects a different or missing state", () => {
    sessionStorage.setItem("pacer-strava-state", "abc");
    expect(checkStravaState("xyz")).toBe(false);
    expect(checkStravaState(null)).toBe(false);
  });
});

it("links to the activity on Strava", () =>
  expect(stravaActivityUrl(42)).toBe("https://www.strava.com/activities/42"));
