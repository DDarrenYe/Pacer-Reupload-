"""Weekly totals for the trends page."""

from dataclasses import dataclass
from datetime import date, timedelta

from app.analytics.predict import Effort, riegel_5k_as_of


@dataclass(frozen=True)
class WeekRow:
    week_start: date
    runs: int
    distance_km: float
    avg_pace_s_per_km: float | None
    predicted_5k_s: float | None
    # Total climb from runs with elevation (GPX uploads and Strava imports); None when
    # none of the week's runs have any (treadmill, manual or CSV only).
    elevation_gain_m: float | None = None


def weekly_trends(
    runs: list[tuple[date, float, float, float | None]],
    efforts: list[Effort],
    user_id: str,
    today: date,
    weeks: int,
) -> list[WeekRow]:
    """runs: (day, distance_m, moving_time_s, elevation_gain_m or None). Weeks start on
    Monday; oldest first."""
    this_monday = today - timedelta(days=today.weekday())
    rows = []
    for i in range(weeks - 1, -1, -1):
        start = this_monday - timedelta(weeks=i)
        end = start + timedelta(days=7)
        in_week = [r for r in runs if start <= r[0] < end]
        dist = sum(r[1] for r in in_week)
        moving = sum(r[2] for r in in_week)
        gains = [r[3] for r in in_week if r[3] is not None]
        rows.append(
            WeekRow(
                week_start=start,
                runs=len(in_week),
                distance_km=round(dist / 1000, 2),
                # Moving-time weighted: total time over total distance, not a mean of paces.
                avg_pace_s_per_km=round(moving / (dist / 1000), 1) if dist else None,
                predicted_5k_s=riegel_5k_as_of(
                    efforts, user_id, min(end - timedelta(days=1), today)
                ),
                elevation_gain_m=round(sum(gains)) if gains else None,
            )
        )
    return rows
