import type { StravaSyncResult } from "./types";

const STATE_KEY = "pacer-strava-state";
export const STRAVA_ORANGE = "#FC5200";

/** Send the browser to Strava to approve read access to activities. */
export function startStravaConnect(clientId: string): void {
  const state = crypto.randomUUID();
  try {
    sessionStorage.setItem(STATE_KEY, state);
  } catch {
    // Storage blocked: the callback will refuse the mismatched state and say so.
  }
  const params = new URLSearchParams({
    client_id: clientId,
    redirect_uri: `${window.location.origin}/strava/callback`,
    response_type: "code",
    approval_prompt: "auto",
    scope: "read,activity:read_all",
    state,
  });
  window.location.assign(`https://www.strava.com/oauth/authorize?${params}`);
}

/** True if `state` is the one this tab sent to Strava (guards against forged callbacks). */
export function checkStravaState(state: string | null): boolean {
  let expected: string | null = null;
  try {
    expected = sessionStorage.getItem(STATE_KEY);
    sessionStorage.removeItem(STATE_KEY);
  } catch {
    return false;
  }
  return !!state && state === expected;
}

export function stravaActivityUrl(id: number): string {
  return `https://www.strava.com/activities/${id}`;
}

export function describeSync({ imported, skipped, more }: StravaSyncResult): string {
  const parts = [imported === 0 ? "No new runs" : `Imported ${imported} run${imported === 1 ? "" : "s"}`];
  if (skipped) parts.push(`skipped ${skipped} (not runs, or already here)`);
  let text = parts.join(", ") + ".";
  if (more) text += " There are more to fetch: sync again.";
  return text;
}
