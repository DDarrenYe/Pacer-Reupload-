import type { Run } from "./types";

const SPLIT_WORDS = { negative: "negative split", even: "even split", positive: "positive split" };

/** "Road · even split · race · Strava": what kind of run, in one line. */
export function runMeta(r: Pick<Run, "surface" | "split_type" | "source" | "is_race" | "strava_activity_id">): string {
  const parts: string[] = [r.surface.charAt(0).toUpperCase() + r.surface.slice(1)];
  if (r.split_type) parts.push(SPLIT_WORDS[r.split_type]);
  if (r.source === "manual" && r.strava_activity_id === null) parts.push("entered manually");
  if (r.is_race) parts.push("race");
  if (r.strava_activity_id !== null) parts.push("Strava");
  return parts.join(" · ");
}
