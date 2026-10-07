"""Parse GPX tracks into a per-point DataFrame.

Output columns:
    time        UTC timestamp of the point
    lat, lon    degrees
    ele         metres (NaN if the file has no elevation)
    hr          heart rate in bpm (NaN if the file has none)
    dist_m      distance from the previous point
    cum_dist_m  running total distance
    elapsed_s   seconds since the first point
    moving      False for points recorded while stopped or after a long gap
"""

from __future__ import annotations

import gpxpy
import gpxpy.gpx
import numpy as np
import pandas as pd

from app.parsing.errors import ParseError
from app.parsing.geo import haversine_m
from app.schemas.run import RunSummary

# Below this speed you're standing at a crossing, not running.
MIN_MOVING_SPEED_MS = 0.5
# A gap this long between points means the watch was paused.
MAX_GAP_S = 60.0
# Faster than this is a GPS glitch (Usain Bolt tops out around 12.4 m/s).
MAX_PLAUSIBLE_SPEED_MS = 12.0

NO_GPS_HINT = (
    " Treadmill and other indoor runs have no GPS track; upload those as a CSV of laps instead."
)


def parse_gpx(content: str | bytes) -> pd.DataFrame:
    try:
        gpx = gpxpy.parse(content.decode("utf-8-sig") if isinstance(content, bytes) else content)
    except (gpxpy.gpx.GPXException, UnicodeDecodeError, ValueError) as exc:
        raise ParseError("This doesn't look like a valid GPX file.") from exc

    points = [
        (p.time, p.latitude, p.longitude, p.elevation, _heart_rate(p))
        for track in gpx.tracks
        for segment in track.segments
        for p in segment.points
    ]
    if len(points) < 2:
        raise ParseError(
            "The GPX file has no track (it needs at least two recorded points)." + NO_GPS_HINT
        )
    if any(t is None for t, *_ in points):
        raise ParseError(
            "The GPX file has points without timestamps, so pace can't be calculated. "
            "Export the activity (not the route) from your watch or app."
        )

    df = pd.DataFrame(points, columns=["time", "lat", "lon", "ele", "hr"])
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df["ele"] = df["ele"].astype(float)
    df["hr"] = df["hr"].astype(float)

    # Many devices write the same timestamp twice; keep the first.
    df = df.drop_duplicates(subset="time", keep="first").reset_index(drop=True)
    if (df["time"].diff().dt.total_seconds() < 0).any():
        raise ParseError("The GPX timestamps go backwards, so the file looks corrupted.")
    if len(df) < 2:
        raise ParseError("The GPX file has no track (it needs at least two recorded points).")

    df = _drop_gps_spikes(df)
    return _add_derived_columns(df)


def _heart_rate(point: gpxpy.gpx.GPXTrackPoint) -> float | None:
    """Heart rate from Garmin-style extensions (<gpxtpx:hr>), as Strava and Garmin export."""
    for ext in point.extensions:
        for el in ext.iter():
            if str(el.tag).rsplit("}", 1)[-1] == "hr" and el.text:
                try:
                    return float(el.text)
                except ValueError:
                    return None
    return None


def _drop_gps_spikes(df: pd.DataFrame) -> pd.DataFrame:
    """Drop points that imply an impossible speed from the last good point."""
    lats, lons = df["lat"].to_numpy(), df["lon"].to_numpy()
    secs = (df["time"] - df["time"].iloc[0]).dt.total_seconds().to_numpy()
    keep = [0]
    for i in range(1, len(df)):
        j = keep[-1]
        dt = secs[i] - secs[j]
        if haversine_m(lats[j], lons[j], lats[i], lons[i]) <= MAX_PLAUSIBLE_SPEED_MS * dt:
            keep.append(i)
    return df.iloc[keep].reset_index(drop=True)


def _add_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    lat, lon = df["lat"].to_numpy(), df["lon"].to_numpy()
    step = np.zeros(len(df))
    step[1:] = haversine_m(lat[:-1], lon[:-1], lat[1:], lon[1:])

    elapsed = (df["time"] - df["time"].iloc[0]).dt.total_seconds()
    dt = elapsed.diff().to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        speed = step / dt

    moving = (speed >= MIN_MOVING_SPEED_MS) & (dt <= MAX_GAP_S)
    moving[0] = False

    return df.assign(dist_m=step, cum_dist_m=step.cumsum(), elapsed_s=elapsed, moving=moving)


def summarize_track(df: pd.DataFrame) -> RunSummary:
    dt = df["elapsed_s"].diff().fillna(0)
    moving_time = float(dt[df["moving"]].sum())
    distance = float(df["cum_dist_m"].iloc[-1])
    if distance <= 0 or moving_time <= 0:
        raise ParseError("The GPX track has no movement in it." + NO_GPS_HINT)

    ele = df["ele"]
    gain = None if ele.isna().all() else float(ele.diff().clip(lower=0).sum())

    # Time-weighted: each point's heart rate covers the moving time since the previous point.
    hr_dt = dt.where(df["moving"] & df["hr"].notna(), 0)
    avg_hr = (
        round(float((df["hr"].fillna(0) * hr_dt).sum() / hr_dt.sum()), 1) if hr_dt.sum() else None
    )

    return RunSummary(
        source="gpx",
        start_time=df["time"].iloc[0].to_pydatetime(),
        distance_m=round(distance, 1),
        elapsed_s=float(df["elapsed_s"].iloc[-1]),
        moving_time_s=moving_time,
        avg_pace_s_per_km=round(moving_time / (distance / 1000), 1),
        elevation_gain_m=None if gain is None else round(gain, 1),
        avg_hr=avg_hr,
        point_count=len(df),
    )
