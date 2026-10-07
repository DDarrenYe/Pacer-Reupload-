/** Demo mode: a short-lived, read-only token from our API, kept for this browser tab only. */

const KEY = "pacer-demo";
export const DEMO_EVENT = "pacer-demo-change";

interface Stored {
  token: string;
  expiresAt: number; // ms since epoch
}

function read(): Stored | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Stored) : null;
  } catch {
    return null;
  }
}

/** The demo token, or null if there isn't one or it has expired. */
export function demoToken(now = Date.now()): string | null {
  const stored = read();
  if (!stored) return null;
  if (stored.expiresAt <= now) {
    endDemo();
    return null;
  }
  return stored.token;
}

export function saveDemo(token: string, expiresInSeconds: number, now = Date.now()): void {
  try {
    sessionStorage.setItem(KEY, JSON.stringify({ token, expiresAt: now + expiresInSeconds * 1000 }));
  } catch {
    /* storage blocked: the demo just won't survive a reload */
  }
  window.dispatchEvent(new Event(DEMO_EVENT));
}

export function endDemo(): void {
  try {
    sessionStorage.removeItem(KEY);
  } catch {
    /* nothing to clear */
  }
  window.dispatchEvent(new Event(DEMO_EVENT));
}
