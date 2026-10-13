import { describe, expect, it } from "vitest";

import { RANKS, rankRange } from "./ranks";

describe("ranks", () => {
  it("has seven, lowest first", () =>
    expect(RANKS).toEqual(["Bronze", "Silver", "Gold", "Platinum", "Diamond", "Pace Setter", "Apex"]));
  it("describes each range", () => {
    expect(rankRange("Bronze")).toBe("under 40%");
    expect(rankRange("Gold")).toBe("50–60%");
    expect(rankRange("Apex")).toBe("90%+");
  });
});
