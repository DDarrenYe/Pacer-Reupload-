"""Fastest time for standard distances anywhere inside a run."""

from dataclasses import dataclass

import numpy as np

from app.analytics.series import RunSeries

STANDARD_DISTANCES_M = {
    "400m": 400.0,
    "1k": 1000.0,
    "1 mile": 1609.344,
    "5k": 5000.0,
    "10k": 10000.0,
    "Half marathon": 21097.5,
    "Marathon": 42195.0,
}


@dataclass(frozen=True)
class BestEffort:
    name: str
    distance_m: float
    duration_s: float
    start_offset_m: float


def compute_best_efforts(series: RunSeries) -> list[BestEffort]:
    """Slide a window of each length along the run, starting at every sample."""
    starts = np.unique(series.distance_m)
    start_times = series.time_at(starts)
    efforts = []
    for name, length in STANDARD_DISTANCES_M.items():
        valid = starts + length <= series.total_distance_m + 1e-6
        if not valid.any():
            continue
        durations = series.time_at(starts[valid] + length) - start_times[valid]
        # Round first so float noise doesn't break ties; argmin then picks the earliest.
        durations = np.round(durations, 1)
        best = int(np.argmin(durations))
        efforts.append(
            BestEffort(
                name=name,
                distance_m=length,
                duration_s=round(float(durations[best]), 1),
                start_offset_m=round(float(starts[valid][best]), 1),
            )
        )
    return efforts
