import { formatDuration } from "./format";

export interface GoalProgress {
  /** Share of today's gap to the target that race day closes, 0–100. */
  pct: number;
  headline: string;
  /** What's left at race day, e.g. "1:35 still to find". */
  left: string;
}

/** How much of the gap between your predicted time now and your target your current trend
 * closes by race day. Times are in seconds; lower is faster. */
export function goalProgress(now: number, projected: number | null, target: number): GoalProgress {
  if (now <= target) return { pct: 100, headline: "You're already there", left: "On target today" };
  const race = projected ?? now;
  if (race <= target) return { pct: 100, headline: "On track to hit it by race day", left: "On target by race day" };
  const share = Math.min(1, Math.max(0, (now - race) / (now - target)));
  const headline =
    share >= 0.6
      ? "Most of the way there by race day"
      : share >= 0.4
        ? "About halfway there by race day"
        : share >= 0.15
          ? "Part of the way there by race day"
          : "Not much closer by race day at this rate";
  return { pct: Math.round(share * 100), headline, left: `${formatDuration(race - target)} still to find` };
}
