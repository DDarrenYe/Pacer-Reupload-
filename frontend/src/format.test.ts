import { describe, expect, it } from "vitest";

import { describeDrift, formatDistance, formatDuration, formatPace } from "./format";

describe("formatDuration", () => {
  it.each([
    [0, "0:00"],
    [59.6, "1:00"],
    [300, "5:00"],
    [3725, "1:02:05"],
  ])("%s s -> %s", (input, expected) => {
    expect(formatDuration(input)).toBe(expected);
  });
});

describe("formatPace", () => {
  it("adds the unit", () => expect(formatPace(287.4)).toBe("4:47 /km"));
});

describe("formatDistance", () => {
  it("uses metres under 1 km", () => expect(formatDistance(400)).toBe("400 m"));
  it("uses km above", () => expect(formatDistance(5012)).toBe("5.01 km"));
});

describe("describeDrift", () => {
  it("handles missing", () => expect(describeDrift(null)).toMatch(/Not enough/));
  it("calls small drift steady", () => expect(describeDrift(0.4)).toMatch(/Steady/));
  it("explains fading", () => expect(describeDrift(4.25)).toBe("Faded: about 4.3 s/km slower each km."));
  it("explains building", () => expect(describeDrift(-3)).toMatch(/faster/));
});
