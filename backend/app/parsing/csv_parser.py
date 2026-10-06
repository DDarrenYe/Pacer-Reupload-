"""Parse CSV lap files (treadmill sessions, watch lap exports, manual logs).

Each row is one lap or interval of a single run. Recognised columns
(case-insensitive):

    distance   distance_m / meters / m, distance_km / km, distance_mi / miles,
               or plain "distance" (read as km if every value is <= 50, else metres)
    time       time / duration / duration_s / seconds / elapsed / moving_time,
               as seconds or "mm:ss" / "hh:mm:ss"
    heart rate (optional) hr / heart_rate / avg_hr

Output columns: lap_no, distance_m, duration_s, avg_hr, cum_dist_m, elapsed_s.
"""

from __future__ import annotations

import io

import numpy as np
import pandas as pd

from app.parsing.errors import ParseError
from app.schemas.run import RunSummary

METRES_PER_MILE = 1609.344
# A "distance" column with every value at or below this is assumed to be in km.
KM_HEURISTIC_MAX = 50

DISTANCE_COLUMNS = {
    "distance_m": 1.0,
    "meters": 1.0,
    "metres": 1.0,
    "m": 1.0,
    "distance_km": 1000.0,
    "km": 1000.0,
    "distance_mi": METRES_PER_MILE,
    "miles": METRES_PER_MILE,
    "mi": METRES_PER_MILE,
    "distance": None,  # unit inferred
    "dist": None,
}
TIME_COLUMNS = ["time", "duration", "duration_s", "seconds", "elapsed", "moving_time"]
HR_COLUMNS = ["hr", "heart_rate", "avg_hr"]


def parse_csv(content: str | bytes) -> pd.DataFrame:
    text = content.decode("utf-8-sig") if isinstance(content, bytes) else content
    try:
        raw = pd.read_csv(io.StringIO(text), dtype=str, skipinitialspace=True)
    except (pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise ParseError("This doesn't look like a valid CSV file.") from exc

    raw.columns = [str(c).strip().lower().replace(" ", "_") for c in raw.columns]
    raw = raw.dropna(how="all")
    if raw.empty:
        raise ParseError("The CSV file has no rows.")

    dist_col = next((c for c in DISTANCE_COLUMNS if c in raw.columns), None)
    time_col = next((c for c in TIME_COLUMNS if c in raw.columns), None)
    missing = [name for name, col in (("distance", dist_col), ("time", time_col)) if col is None]
    if missing:
        raise ParseError(
            f"The CSV is missing a {' and '.join(missing)} column. "
            f"Found columns: {', '.join(raw.columns)}."
        )

    distance = _to_number(raw[dist_col], dist_col)
    factor = DISTANCE_COLUMNS[dist_col]
    if factor is None:
        factor = 1000.0 if distance.max() <= KM_HEURISTIC_MAX else 1.0
    distance_m = distance * factor

    duration_s = raw[time_col].map(lambda v: _parse_duration(v, time_col))

    hr_col = next((c for c in HR_COLUMNS if c in raw.columns), None)
    avg_hr = _to_number(raw[hr_col], hr_col, allow_blank=True) if hr_col else np.nan

    df = pd.DataFrame(
        {
            "lap_no": range(1, len(raw) + 1),
            "distance_m": distance_m.to_numpy(),
            "duration_s": duration_s.to_numpy(dtype=float),
            "avg_hr": avg_hr if np.isscalar(avg_hr) else avg_hr.to_numpy(),
        }
    )
    bad = df.index[(df["distance_m"] <= 0) | (df["duration_s"] <= 0)]
    if len(bad):
        raise ParseError(
            f"Distance and time must be greater than zero (row {_row_number(bad[0])})."
        )

    df["cum_dist_m"] = df["distance_m"].cumsum()
    df["elapsed_s"] = df["duration_s"].cumsum()
    return df


def summarize_laps(df: pd.DataFrame) -> RunSummary:
    distance = float(df["cum_dist_m"].iloc[-1])
    duration = float(df["elapsed_s"].iloc[-1])
    hr = df.dropna(subset=["avg_hr"])
    avg_hr = None
    if not hr.empty:  # weight each lap's heart rate by how long it lasted
        avg_hr = round(float((hr["avg_hr"] * hr["duration_s"]).sum() / hr["duration_s"].sum()), 1)
    return RunSummary(
        source="csv",
        start_time=None,
        distance_m=round(distance, 1),
        elapsed_s=duration,
        moving_time_s=duration,
        avg_pace_s_per_km=round(duration / (distance / 1000), 1),
        elevation_gain_m=None,
        avg_hr=avg_hr,
        point_count=len(df),
    )


def _row_number(index: int) -> int:
    # +2: header line, and 1-based numbering as shown in a spreadsheet.
    return int(index) + 2


def _to_number(col: pd.Series, name: str, allow_blank: bool = False) -> pd.Series:
    values = pd.to_numeric(col.str.strip(), errors="coerce")
    invalid = values.isna() & (col.notna() if allow_blank else True)
    if invalid.any():
        idx = invalid.idxmax()
        raise ParseError(f"Couldn't read '{col[idx]}' in column '{name}' (row {_row_number(idx)}).")
    return values.astype(float)


def _parse_duration(value, column: str) -> float:
    text = "" if pd.isna(value) else str(value).strip()
    try:
        if ":" not in text:
            return float(text)
        parts = [float(p) for p in text.split(":")]
        if len(parts) > 3:
            raise ValueError
        seconds = 0.0
        for part in parts:
            seconds = seconds * 60 + part
        return seconds
    except ValueError:
        raise ParseError(
            f"Couldn't read time '{text}' in column '{column}'. Use seconds or mm:ss / hh:mm:ss."
        ) from None
