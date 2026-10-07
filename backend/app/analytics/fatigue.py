"""Pace drift within a run: how much slower each km gets as the run goes on."""

import numpy as np

from app.analytics.splits import Split

MIN_SPLITS = 3


def pace_drift(splits: list[Split]) -> float | None:
    """Least-squares slope of pace (s/km) against distance (km), using full splits only.

    Positive means slowing down: +5 means each km is about 5 s slower than the one before.
    Needs at least three full splits to say anything.
    """
    full = [s for s in splits if not s.is_partial]
    if len(full) < MIN_SPLITS:
        return None
    # Midpoint of each split in km, so the slope is per km of running.
    ends = np.cumsum([s.distance_m for s in full]) / 1000
    mids = ends - np.array([s.distance_m for s in full]) / 2000
    pace = np.array([s.pace_s_per_km for s in full])
    slope = np.polyfit(mids, pace, 1)[0]
    return round(float(slope), 2) + 0.0  # + 0.0 turns -0.0 into 0.0
