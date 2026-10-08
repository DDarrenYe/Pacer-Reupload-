"""Race goals: where you are, where your trend points, and what to do about the gap.

Everything here is rule-based and explainable: each suggestion carries the number that
triggered it. Predictions reuse predict.py (Riegel from your nearest recent hard effort).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np

from app.analytics.load import SPIKE_ACWR, training_load
from app.analytics.predict import (
    RIEGEL_EXPONENT,
    TARGET_DISTANCES_M,
    Effort,
    closest_anchor,
    envelope,
    personal_fit,
    riegel,
)

TRAJECTORY_WEEKS = 12
MIN_TRAJECTORY_POINTS = 3
# The trend is projected forward, but no faster than 1% a week and no slower than
# 0.5% a week: straight-line extrapolation of a few noisy points can promise anything.
MAX_IMPROVEMENT_PER_WEEK = 0.01
MAX_DECLINE_PER_WEEK = 0.005
# Improving by up to this much a week is realistic for most recreational runners.
REACHABLE_PER_WEEK = 0.005
RECENT_DAYS = 28
TAPER_DAYS = 14
MIN_PACE_KM = 3.0
# A split counts as "at goal pace" within this many seconds per km.
PACE_TOLERANCE_S = 2.0
# Within 5% of a guide counts as meeting it, so 29.6 km doesn't trigger "build to 30".
GUIDE_TOLERANCE = 0.95


@dataclass(frozen=True)
class Guide:
    """Typical minimums for a distance band: a starting point, not a training plan."""

    max_distance_m: float
    weekly_km: float
    long_run_km: float


GUIDES = [
    Guide(7_000, weekly_km=15, long_run_km=8),
    Guide(15_000, weekly_km=20, long_run_km=12),
    Guide(30_000, weekly_km=30, long_run_km=16),
    Guide(math.inf, weekly_km=45, long_run_km=28),
]


@dataclass(frozen=True)
class RunInfo:
    day: date
    distance_m: float
    moving_s: float
    is_race: bool = False
    # (distance_m, pace_s_per_km) of each full split; empty for manual runs
    splits: tuple[tuple[float, float], ...] = ()


@dataclass(frozen=True)
class WeekPoint:
    week_end: date
    predicted_s: float | None


@dataclass
class GoalAnalysis:
    status: str  # no_data | already_there | on_track | within_reach | stretch | passed
    days_left: int
    target_pace_s_per_km: float
    now_s: float | None = None
    personal_now_s: float | None = None
    anchor: str | None = None
    projected_s: float | None = None
    projection_note: str | None = None
    needed_pct_per_week: float | None = None
    weekly: list[WeekPoint] = field(default_factory=list)
    equivalents: list[tuple[str, float, float]] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    result_s: float | None = None
    result_hit: bool | None = None


def fmt(seconds: float) -> str:
    s = int(round(seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def guide_for(distance_m: float) -> Guide:
    return next(g for g in GUIDES if distance_m <= g.max_distance_m)


def predict_at(
    efforts: list[Effort], distance_m: float, as_of: date
) -> tuple[float, Effort] | None:
    env = envelope(efforts, before=as_of + timedelta(days=1))
    anchor = closest_anchor(env, distance_m)
    return (riegel(anchor, distance_m), anchor) if anchor else None


def weekly_predictions(efforts: list[Effort], distance_m: float, today: date) -> list[WeekPoint]:
    points = []
    for i in range(TRAJECTORY_WEEKS - 1, -1, -1):
        end = today - timedelta(weeks=i)
        p = predict_at(efforts, distance_m, end)
        points.append(WeekPoint(end, round(p[0], 1) if p else None))
    return points


def project(points: list[WeekPoint], now_s: float, weeks_ahead: float) -> tuple[float | None, str]:
    """Least-squares trend of the weekly predictions, clamped, carried to race day."""
    known = [(i, p.predicted_s) for i, p in enumerate(points) if p.predicted_s is not None]
    if len({round(v) for _, v in known}) < MIN_TRAJECTORY_POINTS:
        return None, "Not enough history yet to see a trend: keep uploading runs."
    x = np.array([i for i, _ in known], dtype=float)
    y = np.array([v for _, v in known], dtype=float)
    slope = float(np.polyfit(x, y, 1)[0])  # seconds per week; negative = getting faster
    clamped = min(max(slope, -MAX_IMPROVEMENT_PER_WEEK * now_s), MAX_DECLINE_PER_WEEK * now_s)
    note = (
        f"Your predicted time has been changing by {slope:+.0f} s a week over the last "
        f"{TRAJECTORY_WEEKS} weeks."
    )
    if clamped != slope:
        note += " The projection caps that rate, since trends this steep rarely last."
    return now_s + clamped * max(weeks_ahead, 0), note


def equivalents(
    distance_m: float, target_s: float, exponent: float
) -> list[tuple[str, float, float]]:
    """Times at standard shorter distances that match the goal, as checkpoints."""
    return [
        (name, d, round(target_s * (d / distance_m) ** exponent, 1))
        for name, d in TARGET_DISTANCES_M.items()
        if d < distance_m * 0.9
    ]


def analyse(
    *,
    distance_m: float,
    target_s: float,
    race_date: date,
    today: date,
    efforts: list[Effort],
    runs: list[RunInfo],
) -> GoalAnalysis:
    days_left = (race_date - today).days
    target_pace = target_s / (distance_m / 1000)
    a = GoalAnalysis(
        status="no_data", days_left=days_left, target_pace_s_per_km=round(target_pace, 1)
    )

    env = envelope(efforts, before=today + timedelta(days=1))
    fit = personal_fit(env)
    exponent = fit.b if fit and 1.0 <= fit.b <= 1.2 else RIEGEL_EXPONENT
    a.equivalents = equivalents(distance_m, target_s, exponent)

    if days_left < 0:
        return _race_day_passed(a, distance_m, target_s, race_date, runs)

    now = predict_at(efforts, distance_m, today)
    if now:
        a.now_s = round(now[0], 1)
        a.anchor = _label(now[1])
        a.personal_now_s = round(fit.predict(distance_m), 1) if fit else None
        a.weekly = weekly_predictions(efforts, distance_m, today)
        projected, a.projection_note = project(a.weekly, a.now_s, days_left / 7)
        a.projected_s = round(projected, 1) if projected is not None else None
        a.status = _status(a, target_s, days_left)

    a.recommendations = _recommendations(a, distance_m, target_pace, today, runs)
    return a


def _status(a: GoalAnalysis, target_s: float, days_left: int) -> str:
    assert a.now_s is not None
    if a.now_s <= target_s:
        return "already_there"
    if a.projected_s is not None and a.projected_s <= target_s:
        return "on_track"
    weeks = max(days_left / 7, 1)
    a.needed_pct_per_week = round((a.now_s - target_s) / a.now_s / weeks * 100, 2)
    return "within_reach" if a.needed_pct_per_week <= REACHABLE_PER_WEEK * 100 else "stretch"


def _race_day_passed(
    a: GoalAnalysis, distance_m: float, target_s: float, race_date: date, runs: list[RunInfo]
) -> GoalAnalysis:
    a.status = "passed"
    candidates = [
        r
        for r in runs
        if abs((r.day - race_date).days) <= 1
        and abs(r.distance_m - distance_m) <= 0.03 * distance_m
    ]
    if candidates:
        best = min(candidates, key=lambda r: (not r.is_race, r.moving_s))
        a.result_s = best.moving_s
        a.result_hit = best.moving_s <= target_s
    return a


def _recommendations(
    a: GoalAnalysis, distance_m: float, target_pace: float, today: date, runs: list[RunInfo]
) -> list[str]:
    if a.status == "no_data":
        return [
            "Upload a few recent runs, ideally a race or a hard effort of 5 km or more, so "
            "Pacer can predict your time and track your progress."
        ]
    if a.status == "passed":
        return []

    out: list[str] = []
    recent = [r for r in runs if today - timedelta(days=RECENT_DAYS) < r.day <= today]
    guide = guide_for(distance_m)
    weekly = sum(r.distance_m for r in recent) / 1000 / (RECENT_DAYS / 7)
    longest = max((r.distance_m for r in recent), default=0) / 1000

    load = training_load([(r.day, r.moving_s / 60) for r in runs], end=today, days=1)
    acwr = load[-1].acwr if load else None
    if acwr is not None and acwr > SPIKE_ACWR:
        out.append(
            f"Your training load has jumped (this week is {acwr:.1f}× your 4-week average). "
            "Hold steady for a week before adding more, to keep injury risk down."
        )

    if a.days_left <= TAPER_DAYS:
        out.append(
            f"Race day is {a.days_left} days away: taper. Cut weekly distance by 30–50%, keep "
            f"a few short efforts at goal pace ({fmt(target_pace)} /km), and rest well."
        )
    else:
        if weekly < guide.weekly_km * GUIDE_TOLERANCE:
            out.append(
                f"Build weekly distance towards {guide.weekly_km:.0f} km (you've averaged "
                f"{weekly:.0f} km over the last 4 weeks). Add no more than about 10% a week."
            )
        if longest < guide.long_run_km * GUIDE_TOLERANCE:
            out.append(
                f"Your longest run in the last 4 weeks is {longest:.1f} km. Build your long "
                f"run towards {guide.long_run_km:.0f} km, adding 1–2 km a week."
            )
        fast_km = max((_km_at_pace(r, target_pace) for r in recent), default=0.0)
        if fast_km < MIN_PACE_KM:
            out.append(
                f"None of your recent runs spent {MIN_PACE_KM:.0f} km at goal pace "
                f"({fmt(target_pace)} /km). Add one session a week, e.g. 3 × 2 km at goal pace "
                "with 2-minute recoveries."
            )
        shorter = [e for e in a.equivalents if e[0] in ("5k", "10k")]
        if shorter and a.status not in ("already_there",) and a.days_left > 21:
            name, _, t = shorter[0]
            out.append(
                f"Checkpoint: a {name} in {fmt(t)} or faster within the next "
                f"{max(2, a.days_left // 14)} weeks would show you're on track."
            )
    if not out:
        out.append("Your training lines up with this goal. Keep it consistent and stay healthy.")
    return out[:5]


def _km_at_pace(run: RunInfo, target_pace: float) -> float:
    if run.splits:
        return sum(d for d, p in run.splits if p <= target_pace + PACE_TOLERANCE_S) / 1000
    pace = run.moving_s / (run.distance_m / 1000)
    return run.distance_m / 1000 if pace <= target_pace + PACE_TOLERANCE_S else 0.0


def _label(e: Effort) -> str:
    kind = "race" if e.is_race else "best effort"
    return f"your {round(e.distance_m / 1000, 1):g} km {kind} on {e.day.isoformat()}"
