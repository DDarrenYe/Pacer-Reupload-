"""Training load over time and the acute:chronic workload ratio (ACWR).

Load for a run is its moving time in minutes. Acute load is the sum over the last 7 days;
chronic load is the weekly average over the last 28 days. ACWR = acute / chronic, so 1.0
means this week matches your recent normal.
"""

from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd

# Commonly used bands: above 1.5 is a spike, below 0.8 is a drop.
SPIKE_ACWR = 1.5
LOW_ACWR = 0.8
# With less history than this the chronic average isn't meaningful yet.
MIN_HISTORY_DAYS = 21


@dataclass(frozen=True)
class LoadDay:
    date: date
    load_min: float
    acute_7d: float
    chronic_28d: float
    acwr: float | None
    flag: str | None


def training_load(runs: list[tuple[date, float]], end: date, days: int) -> list[LoadDay]:
    """runs: (run date, moving minutes). Returns one row per day for the last `days` days."""
    start = end - timedelta(days=days - 1)
    index = pd.date_range(start - timedelta(days=27), end, freq="D")
    daily = pd.Series(0.0, index=index)
    for day, minutes in runs:
        ts = pd.Timestamp(day)
        if ts in daily.index:
            daily[ts] += minutes

    acute = daily.rolling(7, min_periods=1).sum()
    chronic = daily.rolling(28, min_periods=1).sum() / 4
    first_run = min((d for d, _ in runs), default=None)

    out = []
    for ts in pd.date_range(start, end, freq="D"):
        day = ts.date()
        enough_history = first_run is not None and (day - first_run).days >= MIN_HISTORY_DAYS
        ratio = acute[ts] / chronic[ts] if enough_history and chronic[ts] > 0 else None
        flag = None
        if ratio is not None:
            flag = "spike" if ratio > SPIKE_ACWR else "low" if ratio < LOW_ACWR else "normal"
        out.append(
            LoadDay(
                date=day,
                load_min=round(float(daily[ts]), 1),
                acute_7d=round(float(acute[ts]), 1),
                chronic_28d=round(float(chronic[ts]), 1),
                acwr=None if ratio is None else round(float(ratio), 2),
                flag=flag,
            )
        )
    return out
