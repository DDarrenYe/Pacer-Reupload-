/** Game-style ranks by age grade, lowest first. Matches backend/app/analytics/compare.py. */
export const RANKS = ["Bronze", "Silver", "Gold", "Platinum", "Diamond", "Emerald", "Pace Setter", "Apex"] as const;
export type RankName = (typeof RANKS)[number];

/** Age-grade floor of each rank, matching the API. */
export const RANK_FLOORS: Record<RankName, number> = {
  Bronze: 0,
  Silver: 35,
  Gold: 45,
  Platinum: 52,
  Diamond: 60,
  Emerald: 70,
  "Pace Setter": 80,
  Apex: 90,
};

/** Ranks below Pace Setter split into divisions 3, 2 and 1, one per third of the range. */
export const DIVISIONS = [3, 2, 1] as const;
export function isDivided(rank: RankName): boolean {
  return rank !== "Pace Setter" && rank !== "Apex";
}

/** "under 35%", "45–52%", "90%+". */
export function rankRange(rank: RankName): string {
  const i = RANKS.indexOf(rank);
  const lo = RANK_FLOORS[rank];
  const next = RANKS[i + 1];
  if (!next) return `${lo}%+`;
  return lo === 0 ? `under ${RANK_FLOORS[next]}%` : `${lo}–${RANK_FLOORS[next]}%`;
}
