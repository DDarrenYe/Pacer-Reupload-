import { beforeEach, describe, expect, it } from "vitest";

import { demoToken, endDemo, saveDemo } from "./demo";

class MemoryStorage {
  private data = new Map<string, string>();
  getItem(k: string) {
    return this.data.get(k) ?? null;
  }
  setItem(k: string, v: string) {
    this.data.set(k, v);
  }
  removeItem(k: string) {
    this.data.delete(k);
  }
}

beforeEach(() => {
  Object.assign(globalThis, { sessionStorage: new MemoryStorage(), window: new EventTarget() });
});

describe("demo token", () => {
  it("is stored and returned until it expires", () => {
    saveDemo("abc", 60, 1_000);
    expect(demoToken(1_000)).toBe("abc");
    expect(demoToken(60_999)).toBe("abc");
    expect(demoToken(61_000)).toBeNull();
    expect(demoToken(1_000)).toBeNull(); // expired tokens are cleared
  });

  it("ends", () => {
    saveDemo("abc", 60);
    endDemo();
    expect(demoToken()).toBeNull();
  });

  it("copes with no stored demo", () => expect(demoToken()).toBeNull());
});
