import { describe, expect, it } from "vitest";

import { RANKS, rankRange } from "./ranks";

describe("ranks", () => {
  it("has eight, lowest first", () =>
    expect(RANKS).toEqual(["Bronze", "Silver", "Gold", "Platinum", "Diamond", "Emerald", "Pace Setter", "Apex"]));
  it("describes each range", () => {
    expect(rankRange("Bronze")).toBe("under 35%");
    expect(rankRange("Gold")).toBe("45–52%");
    expect(rankRange("Emerald")).toBe("70–80%");
    expect(rankRange("Apex")).toBe("90%+");
  });
});
