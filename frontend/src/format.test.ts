import { describe, expect, it } from "vitest";

import {
  describeCountdown,
  describeDrift,
  describeGap,
  describeExponent,
  formatDistance,
  formatDuration,
  formatPace,
  defaultManualName,
  paceFrom,
  splitDuration,
  toSeconds,
} from "./format";

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

describe("describeExponent", () => {
  it("handles missing", () => expect(describeExponent(null)).toMatch(/two quite different distances/));
  it("calls 1.06 average", () => expect(describeExponent(1.065)).toMatch(/about as much/));
  it("explains a high exponent", () => expect(describeExponent(1.1)).toMatch(/speed is your relative strength/));
  it("explains a low exponent", () => expect(describeExponent(1.02)).toMatch(/endurance/));
});

describe("manual entry helpers", () => {
  it("adds up h:m:s", () => expect(toSeconds("1", "02", "05")).toBe(3725));
  it("treats blanks as zero", () => expect(toSeconds("", "27", "")).toBe(1620));
  it("works out pace", () => expect(paceFrom(5, 1650)).toBe(330));
  it("waits for both values", () => {
    expect(paceFrom(0, 1650)).toBeNull();
    expect(paceFrom(5, 0)).toBeNull();
    expect(paceFrom(Number.NaN, 100)).toBeNull();
  });
});

describe("editing helpers", () => {
  it("splits a duration for the form", () => {
    expect(splitDuration(3725)).toEqual(["1", "2", "05"]);
    expect(splitDuration(1650)).toEqual(["", "27", "30"]);
  });
  it("matches the server's default name", () => {
    expect(defaultManualName(5, "treadmill")).toBe("5 km treadmill run");
    expect(defaultManualName(6.4, "road")).toBe("6.4 km road run");
    expect(defaultManualName(21.0975, "road")).toBe("21.0975 km road run");
  });
});

describe("describeCountdown", () => {
  it("names near days", () => {
    expect(describeCountdown(0)).toBe("today");
    expect(describeCountdown(1)).toBe("tomorrow");
    expect(describeCountdown(9)).toBe("in 9 days");
  });
  it("uses weeks further out", () => expect(describeCountdown(49)).toBe("in 7 weeks"));
  it("handles the past", () => {
    expect(describeCountdown(-1)).toBe("yesterday");
    expect(describeCountdown(-4)).toBe("4 days ago");
  });
});

describe("describeGap", () => {
  it("says faster or slower", () => {
    expect(describeGap(-83)).toBe("1:23 faster");
    expect(describeGap(179)).toBe("2:59 slower");
  });
  it("calls a tiny gap spot on", () => expect(describeGap(0.4)).toBe("spot on"));
});
