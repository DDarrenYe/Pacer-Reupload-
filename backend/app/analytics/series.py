"""Turn a parsed run into one shape for analytics: moving time against distance."""

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class RunSeries:
    """Cumulative distance and moving time, sample by sample, both starting at 0.

    hr[i] is the heart rate over the segment ending at sample i (NaN if unknown);
    hr[0] is unused.
    """

    distance_m: np.ndarray
    time_s: np.ndarray
    hr: np.ndarray

    @property
    def total_distance_m(self) -> float:
        return float(self.distance_m[-1])

    def time_at(self, distance_m) -> np.ndarray:
        """Moving time when each distance was first reached (linear between samples)."""
        # Paused samples repeat the same distance; keep the first so the time is when
        # you got there, not when you set off again.
        d, first = np.unique(self.distance_m, return_index=True)
        return np.interp(distance_m, d, self.time_s[first])


def series_from_track(df: pd.DataFrame) -> RunSeries:
    """GPX: paused segments add no time (but keep their distance)."""
    dt = df["elapsed_s"].diff().fillna(0).to_numpy()
    moving_dt = np.where(df["moving"].to_numpy(), dt, 0.0)
    return RunSeries(
        distance_m=df["cum_dist_m"].to_numpy(dtype=float),
        time_s=np.cumsum(moving_dt),
        hr=df["hr"].to_numpy(dtype=float),
    )


def series_from_laps(df: pd.DataFrame) -> RunSeries:
    """CSV laps: one sample per lap end, assuming even pace within each lap."""
    zero = np.array([0.0])
    return RunSeries(
        distance_m=np.concatenate([zero, df["cum_dist_m"].to_numpy(dtype=float)]),
        time_s=np.concatenate([zero, df["elapsed_s"].to_numpy(dtype=float)]),
        hr=np.concatenate([[np.nan], df["avg_hr"].to_numpy(dtype=float)]),
    )
