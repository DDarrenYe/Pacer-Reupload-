"""Pace splits, fastest/slowest split and the overall split type."""

from dataclasses import dataclass
from typing import Literal

import numpy as np

from app.analytics.series import RunSeries

# A partial last split shorter than this isn't worth showing.
MIN_PARTIAL_M = 50.0
# Halves within this fraction of each other count as an even split.
EVEN_SPLIT_TOLERANCE = 0.01


@dataclass(frozen=True)
class Split:
    split_no: int
    distance_m: float
    duration_s: float
    pace_s_per_km: float
    avg_hr: float | None
    is_partial: bool


def compute_splits(series: RunSeries, split_length_m: float = 1000.0) -> list[Split]:
    total = series.total_distance_m
    edges = np.arange(0.0, total, split_length_m)
    edges = np.append(edges, total)
    if total - edges[-2] < MIN_PARTIAL_M and len(edges) > 2:
        edges = np.delete(edges, -2)  # fold a tiny leftover into the last split
    times = series.time_at(edges)

    splits = []
    for i in range(len(edges) - 1):
        dist = float(edges[i + 1] - edges[i])
        dur = float(times[i + 1] - times[i])
        splits.append(
            Split(
                split_no=i + 1,
                distance_m=round(dist, 1),
                duration_s=round(dur, 1),
                pace_s_per_km=round(dur / dist * 1000, 1) if dist else 0.0,
                avg_hr=_avg_hr(series, edges[i], edges[i + 1]),
                is_partial=dist < split_length_m - 0.5,
            )
        )
    return splits


def fastest_and_slowest(splits: list[Split]) -> tuple[int | None, int | None]:
    full = [s for s in splits if not s.is_partial]
    if not full:
        return None, None
    fastest = min(full, key=lambda s: s.pace_s_per_km)
    slowest = max(full, key=lambda s: s.pace_s_per_km)
    return fastest.split_no, slowest.split_no


def split_type(series: RunSeries) -> Literal["negative", "even", "positive"]:
    """Compare the time for the second half of the distance with the first half."""
    half = series.total_distance_m / 2
    first, end = series.time_at([half, series.total_distance_m])
    second = end - first
    change = (second - first) / first
    if change < -EVEN_SPLIT_TOLERANCE:
        return "negative"
    if change > EVEN_SPLIT_TOLERANCE:
        return "positive"
    return "even"


def _avg_hr(series: RunSeries, start_m: float, end_m: float) -> float | None:
    """Time-weighted heart rate between two distances, on a 10 m grid."""
    grid = np.linspace(start_m, end_m, max(2, int((end_m - start_m) / 10) + 1))
    dt = np.diff(series.time_at(grid))
    mids = (grid[:-1] + grid[1:]) / 2
    # The segment containing each midpoint supplies its heart rate.
    idx = np.clip(np.searchsorted(series.distance_m, mids), 1, len(series.hr) - 1)
    hr = series.hr[idx]
    known = ~np.isnan(hr) & (dt > 0)
    if not known.any():
        return None
    return round(float(np.average(hr[known], weights=dt[known])), 1)
