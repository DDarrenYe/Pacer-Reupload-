import { expect, it } from "vitest";

import { TITLE_DESCRIPTIONS } from "./titles";

it("describes all eight titles the API can give", () => {
  expect(Object.keys(TITLE_DESCRIPTIONS).sort()).toEqual(
    [
      "The Diesel",
      "The Kicker",
      "The Metronome",
      "The Mountain Goat",
      "The Negative Splitter",
      "The Power Sprinter",
      "The Rabbit",
      "The Surge Runner",
    ].sort(),
  );
});
