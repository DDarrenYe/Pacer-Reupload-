import { describe, expect, it, vi } from "vitest";

vi.mock("./supabase", () => ({ supabase: {} }));

const { errorMessage } = await import("./api");

describe("errorMessage", () => {
  it("passes strings through", () => expect(errorMessage("Run not found.")).toBe("Run not found."));
  it("reads {message}", () => expect(errorMessage({ message: "Already uploaded", run_id: "x" })).toBe("Already uploaded"));
  it("reads validation lists without the prefix", () =>
    expect(errorMessage([{ msg: "Value error, That works out to an unrealistic pace." }])).toBe(
      "That works out to an unrealistic pace.",
    ));
  it("gives up on unknown shapes", () => expect(errorMessage(null)).toBeNull());
});
