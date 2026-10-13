"""Runner titles: one archetype per runner, from how their recent runs were paced.

Each title is a trait a single run can show (a fast last km, a fast start that fades,
even splits...). A title's score is the share of your recent runs showing it; the
highest wins, and the reason names the evidence. The Power Sprinter is the exception:
it's about speed over distance, so it comes from your best 1k against your best 5k.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass

MIN_RUNS = 3
MIN_SPLITS = 3
MAX_RUNS = 30

FAST_START = 0.03  # first split this much faster than the run's median
KICK = 0.03  # last split this much faster than the median
METRONOME_CV = 0.02  # split-to-split variation at most this
DIESEL_MIN_KM = 8.0
DIESEL_SLOW_START = 0.03
DIESEL_REST_CV = 0.025
SURGE = 0.03  # a middle split this much faster than both neighbours
SURGE_MIN_SPLITS = 5
GOAT_CLIMB_M_PER_KM = 15.0
GOAT_CV = 0.03
# Riegel puts 1k pace about 10% quicker than 5k pace (5^0.06); a much bigger gap is speed.
SPRINT_RATIO_FLOOR = 1.08
SPRINT_RATIO_SPAN = 0.12
FALLBACK_CV = 0.04

# In tie order: the more distinctive titles first.
TITLES = [
    "The Rabbit",
    "The Kicker",
    "The Power Sprinter",
    "The Surge Runner",
    "The Mountain Goat",
    "The Diesel",
    "The Negative Splitter",
    "The Metronome",
]


@dataclass(frozen=True)
class RunSplits:
    paces: tuple[float, ...]  # full splits only, s/km, in order
    distance_m: float
    split_type: str | None  # negative | even | positive
    elevation_gain_m: float | None


@dataclass(frozen=True)
class Title:
    name: str
    reason: str
    runs_considered: int


def _cv(paces) -> float:
    return statistics.pstdev(paces) / statistics.fmean(paces) if len(paces) > 1 else 0.0


def run_traits(run: RunSplits) -> set[str]:
    """Which titles' traits this one run shows."""
    p = run.paces
    m = statistics.median(p)
    traits = set()
    cv = _cv(p)
    if (m - p[0]) / m >= FAST_START and run.split_type == "positive":
        traits.add("The Rabbit")
    kick = (m - p[-1]) / m
    if kick >= KICK:
        traits.add("The Kicker")
    if cv <= METRONOME_CV and run.split_type == "even":
        traits.add("The Metronome")
    rest = p[1:]
    if (
        run.distance_m >= DIESEL_MIN_KM * 1000
        and (p[0] - statistics.median(rest)) / m >= DIESEL_SLOW_START
        and _cv(rest) <= DIESEL_REST_CV
    ):
        traits.add("The Diesel")
    if run.split_type == "negative" and kick < KICK:
        traits.add("The Negative Splitter")
    if len(p) >= SURGE_MIN_SPLITS and any(
        p[i] <= min(p[i - 1], p[i + 1]) * (1 - SURGE) for i in range(1, len(p) - 1)
    ):
        traits.add("The Surge Runner")
    climb = (run.elevation_gain_m or 0) / (run.distance_m / 1000)
    if climb >= GOAT_CLIMB_M_PER_KM and cv <= GOAT_CV:
        traits.add("The Mountain Goat")
    return traits


# What each trait looks like, after "N of your M recent runs ..."
REASONS = {
    "The Rabbit": "started at least 3% quicker than your usual pace, then faded",
    "The Kicker": "finished with a last km at least 3% quicker than your usual pace",
    "The Metronome": "had km splits within 2% of each other, start to finish",
    "The Diesel": "started slowly, then held a steady pace for 8 km or more",
    "The Negative Splitter": "got progressively faster, with a quicker second half",
    "The Surge Runner": "had a mid-run surge at least 3% quicker than the km either side",
    "The Mountain Goat": "climbed 15 m or more per km, with your pace barely changing",
}


def assign_title(
    runs: list[RunSplits], best_1k_s: float | None = None, best_5k_s: float | None = None
) -> Title | None:
    """Your one title, or None until there are enough runs with splits."""
    runs = [r for r in runs if len(r.paces) >= MIN_SPLITS][:MAX_RUNS]
    total = len(runs)
    if total < MIN_RUNS:
        return None
    counts = {name: 0 for name in TITLES}
    for run in runs:
        for trait in run_traits(run):
            counts[trait] += 1
    scores = {name: counts[name] / total for name in TITLES}

    sprint_ratio = None
    if best_1k_s and best_5k_s:
        sprint_ratio = (best_5k_s / 5) / best_1k_s  # 5k pace over 1k pace
        scores["The Power Sprinter"] = min(
            1.0, max(0.0, (sprint_ratio - SPRINT_RATIO_FLOOR) / SPRINT_RATIO_SPAN)
        )

    best = max(TITLES, key=lambda name: (scores[name], -TITLES.index(name)))
    if scores[best] == 0:
        typical_cv = statistics.median(_cv(r.paces) for r in runs)
        best = "The Metronome" if typical_cv <= FALLBACK_CV else "The Surge Runner"
        reason = (
            "Your pacing is steady from km to km more than anything else"
            if best == "The Metronome"
            else "Your pace moves around a lot from km to km"
        )
        return Title(best, reason + f" (from your {total} recent runs).", total)
    if best == "The Power Sprinter":
        reason = (
            f"Your best 1k pace is {100 * (sprint_ratio - 1):.0f}% quicker than your best 5k pace, "
            "a bigger gap than most runners have: raw speed is your weapon."
        )
    else:
        reason = f"{counts[best]} of your {total} recent runs {REASONS[best]}."
    return Title(best, reason, total)
