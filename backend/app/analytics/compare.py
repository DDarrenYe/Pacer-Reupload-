"""How your times compare with other runners of your age and sex.

Two measures:
- Age grade: an official standard time for your age and sex at that distance, divided by
  your time. 100% is world-record level for your age; it's comparable across ages,
  sexes and distances. Standards: 2025 road tables by Alan Jones and Tom Bernhard
  (USATF Masters Long Distance Running, public domain).
- Percentile: the share of 2023 US marathon finishers of your sex and age band whose age
  grade was lower than yours. There's no open dataset of shorter races, so other
  distances are compared on age grade, which puts every distance on the same scale.
"""

from __future__ import annotations

import bisect
import json
from dataclasses import dataclass
from datetime import date, timedelta
from functools import cache
from pathlib import Path

from app.analytics.goals import effort_label, predict_at
from app.analytics.predict import EXTRAPOLATION_RATIO, Effort, envelope

DATA = Path(__file__).resolve().parent.parent / "data"
STANDARDS_FILE = DATA / "age_standards_2025.json"
PERCENTILES_FILE = DATA / "finisher_percentiles.json"

DISTANCES = {
    "5k": 5000.0,
    "10k": 10000.0,
    "15k": 15000.0,
    "Half marathon": 21097.5,
    "Marathon": 42195.0,
}
MIN_AGE, MAX_AGE = 5, 100
SEXES = ("female", "male")
# The usual age-grade bands, as used by parkrun and road-race scorers.
BANDS = [(90, "World class"), (80, "National class"), (70, "Regional class"), (60, "Local class")]
# Game-style ranks by age grade, lowest first. The bottom four split the bulk of race
# finishers (median about 48%, 75th percentile about 57%, 90th about 65%); from Diamond
# up they match the official classes above (local 60, regional 70, national 80, world 90).
RANKS = [
    ("Bronze", 0.0),
    ("Silver", 35.0),
    ("Gold", 45.0),
    ("Platinum", 52.0),
    ("Diamond", 60.0),
    ("Emerald", 70.0),
    ("Pace Setter", 80.0),
    ("Apex", 90.0),
]


@cache
def _standards() -> dict:
    return json.loads(STANDARDS_FILE.read_text())


@cache
def percentile_table() -> dict | None:
    """The finisher distribution, or None until scripts/build_percentiles.py has run."""
    if not PERCENTILES_FILE.exists():
        return None
    return json.loads(PERCENTILES_FILE.read_text())


def standard_s(distance_m: float, age: int, sex: str) -> float:
    ages = _standards()[sex][f"{distance_m:g}"]
    return float(ages[str(min(max(age, MIN_AGE), MAX_AGE))])


def age_grade(time_s: float, distance_m: float, age: int, sex: str) -> float:
    """Age grade in %: the age standard for this distance divided by your time."""
    return 100 * standard_s(distance_m, age, sex) / time_s


def band_label(grade: float) -> str:
    return next((label for floor, label in BANDS if grade >= floor), "Recreational")


@dataclass(frozen=True)
class Rank:
    name: str
    tier: int  # 1 (Bronze) to 8 (Apex)
    floor: float
    next_name: str | None
    next_floor: float | None

    def progress(self, grade: float) -> float | None:
        """How far through this rank you are, 0-100, or None at the top."""
        if self.next_floor is None:
            return None
        return round(100 * (grade - self.floor) / (self.next_floor - self.floor), 1)


def rank_for(grade: float) -> Rank:
    tier = max(i for i, (_, floor) in enumerate(RANKS) if grade >= floor)
    name, floor = RANKS[tier]
    following = RANKS[tier + 1] if tier + 1 < len(RANKS) else (None, None)
    return Rank(name, tier + 1, floor, following[0], following[1])


def time_for_grade(grade: float, distance_m: float, age: int, sex: str) -> float:
    """The time at this distance that earns this age grade."""
    return standard_s(distance_m, age, sex) / (grade / 100)


@dataclass(frozen=True)
class Percentile:
    faster_than_pct: float  # share of the group with a lower age grade
    group: str  # e.g. "men aged 30–34"


def percentile(grade: float, age: int, sex: str, table: dict | None = None) -> Percentile | None:
    table = table if table is not None else percentile_table()
    if not table:
        return None
    bands = table[sex]
    band = next((b for b in bands if b["min_age"] <= age <= b["max_age"]), None)
    if band is None:  # younger or older than anyone in the data: use the nearest band
        band = bands[0] if age < bands[0]["min_age"] else bands[-1]
    q = band["q"]  # age grade at the 1st..99th percentiles, ascending
    i = bisect.bisect_left(q, grade)
    if i == 0:
        pct = 1.0 * grade / q[0] if q[0] else 0.0
    elif i == len(q):
        pct = 99.0 + (1.0 if grade > q[-1] else 0.0)
    else:  # interpolate between the i-th and (i+1)-th percentile
        lo, hi = q[i - 1], q[i]
        pct = i + (grade - lo) / (hi - lo) if hi > lo else i
    return Percentile(round(min(max(pct, 0.0), 100.0), 1), _group(sex, band))


def _group(sex: str, band: dict) -> str:
    who = "women" if sex == "female" else "men"
    lo, hi = band["min_age"], band["max_age"]
    if hi >= MAX_AGE:
        return f"{who} aged {lo}+"
    return f"{who} aged {lo}–{hi}"


@dataclass(frozen=True)
class ComparisonRow:
    name: str
    distance_m: float
    time_s: float | None
    anchor: str | None
    extrapolated: bool
    age_grade: float | None
    band: str | None
    percentile: Percentile | None
    rank: Rank | None = None
    # The time at this distance that reaches the next rank.
    next_rank_time_s: float | None = None


def compare(efforts: list[Effort], age: int, sex: str, today: date) -> list[ComparisonRow]:
    """Your predicted time at each distance, its age grade and percentile."""
    recent = envelope(efforts, before=today + timedelta(days=1))
    longest = max((e.distance_m for e in recent), default=0.0)
    rows = []
    for name, distance in DISTANCES.items():
        predicted = predict_at(efforts, distance, today)
        if predicted is None:
            rows.append(ComparisonRow(name, distance, None, None, False, None, None, None))
            continue
        time_s, anchor = predicted
        grade = round(age_grade(time_s, distance, age, sex), 1)
        rank = rank_for(grade)
        rows.append(
            ComparisonRow(
                name=name,
                distance_m=distance,
                time_s=round(time_s, 1),
                anchor=effort_label(anchor),
                extrapolated=bool(longest) and distance > EXTRAPOLATION_RATIO * longest,
                age_grade=grade,
                band=band_label(grade),
                percentile=percentile(grade, age, sex),
                rank=rank,
                next_rank_time_s=round(time_for_grade(rank.next_floor, distance, age, sex), 1)
                if rank.next_floor
                else None,
            )
        )
    return rows


def best_row(rows: list[ComparisonRow]) -> ComparisonRow | None:
    """Your best predicted age grade, ignoring extrapolated distances unless there's
    nothing else (a marathon guessed from a 5k isn't earned)."""
    graded = [r for r in rows if r.age_grade is not None]
    solid = [r for r in graded if not r.extrapolated] or graded
    return max(solid, key=lambda r: r.age_grade, default=None)


@dataclass(frozen=True)
class BestRank:
    distance: str  # e.g. "5k"
    age_grade: float
    rank: Rank
    next_rank_time_s: float | None
    source: str  # "best time" (a time you actually ran) or "prediction"


def best_rank(
    rows: list[ComparisonRow], bests: list[tuple[str, float, float]], age: int, sex: str
) -> BestRank | None:
    """Your rank: the best age grade from either a time you've actually run at a standard
    distance (name, distance_m, time_s) or a prediction at a distance you've run near."""
    candidates = []
    row = best_row(rows)
    if row is not None:
        candidates.append((row.age_grade, row.name, row.distance_m, "prediction"))
    for name, distance, time_s in bests:
        grade = round(age_grade(time_s, distance, age, sex), 1)
        candidates.append((grade, name, distance, "best time"))
    if not candidates:
        return None
    grade, name, distance, source = max(candidates, key=lambda c: c[0])
    rank = rank_for(grade)
    next_time = (
        round(time_for_grade(rank.next_floor, distance, age, sex), 1) if rank.next_floor else None
    )
    return BestRank(name, grade, rank, next_time, source)
