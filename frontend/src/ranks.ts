/** Game-style ranks by age grade, lowest first. Matches backend/app/analytics/compare.py. */
export const RANKS = ["Bronze", "Silver", "Gold", "Platinum", "Diamond", "Pace Setter", "Apex"] as const;
export type RankName = (typeof RANKS)[number];

/** Age-grade floor of each rank, matching the API. */
export const RANK_FLOORS: Record<RankName, number> = {
  Bronze: 0,
  Silver: 40,
  Gold: 50,
  Platinum: 60,
  Diamond: 70,
  "Pace Setter": 80,
  Apex: 90,
};

/** "under 40%", "50–60%", "90%+". */
export function rankRange(rank: RankName): string {
  const i = RANKS.indexOf(rank);
  const lo = RANK_FLOORS[rank];
  const next = RANKS[i + 1];
  if (!next) return `${lo}%+`;
  return lo === 0 ? `under ${RANK_FLOORS[next]}%` : `${lo}–${RANK_FLOORS[next]}%`;
}
