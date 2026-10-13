"""Build the finisher percentile table from the 2023 US marathon results.

    python scripts/build_percentiles.py ~/Downloads/Results.csv

Data: "2023 Marathon Results" by Running with Rock on Kaggle (CC BY 4.0), about 429,000
finishers of 641 US marathons: https://www.kaggle.com/datasets/runningwithrock/2023-marathon-results

Each finisher's time is turned into an age grade (using the same 2025 age standards as
the app), then the 1st-99th percentiles of age grade are stored per sex and 5-year age
band. Only these aggregates are written: no names, no individual results.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.analytics.compare import PERCENTILES_FILE, age_grade  # noqa: E402

MARATHON_M = 42195.0
BAND_YEARS = 5
FIRST_BAND_MAX = 19  # everyone under 20 in one band
LAST_BAND_MIN = 80  # and everyone 80 or over
# A band with fewer finishers than this is merged into its neighbour.
MIN_PER_BAND = 500
# Times outside this range are typos or partial results.
MIN_S, MAX_S = 2 * 3600, 9 * 3600

SEX_COLUMNS = ("gender", "sex")
AGE_COLUMNS = ("age",)
TIME_COLUMNS = ("finish", "finish_time", "finishtime", "time", "net_time", "chip_time", "seconds")


def find_column(header: list[str], candidates: tuple[str, ...]) -> str:
    lower = {h.strip().lower().replace(" ", "_"): h for h in header}
    for c in candidates:
        if c in lower:
            return lower[c]
    sys.exit(f"Couldn't find a column like {candidates} in: {header}")


def to_seconds(value: str) -> float | None:
    value = value.strip()
    if not value:
        return None
    if ":" in value:
        parts = [float(p) for p in value.split(":")]
        while len(parts) < 3:
            parts.insert(0, 0.0)
        h, m, s = parts[-3:]
        return h * 3600 + m * 60 + s
    try:
        return float(value)
    except ValueError:
        return None


def to_sex(value: str) -> str | None:
    v = value.strip().lower()
    if v in ("m", "male", "man", "men"):
        return "male"
    if v in ("f", "female", "woman", "women", "w"):
        return "female"
    return None  # the age standards only exist for women and men


def band_of(age: int) -> int:
    if age <= FIRST_BAND_MAX:
        return 0
    return min(age, LAST_BAND_MIN) // BAND_YEARS * BAND_YEARS


def bands_for(grades_by_band: dict[int, list[float]]) -> list[dict]:
    """5-year bands; any band with too few finishers is merged into a neighbour."""
    starts = sorted(grades_by_band)
    groups = [
        [
            5 if start == 0 else start,
            (starts[i + 1] - 1) if i + 1 < len(starts) else 100,
            list(grades_by_band[start]),
        ]
        for i, start in enumerate(starts)
    ]
    while len(groups) > 1:
        small = next((i for i, g in enumerate(groups) if len(g[2]) < MIN_PER_BAND), None)
        if small is None:
            break
        other = small - 1 if small > 0 else 1  # merge into the band before, or after if first
        a, b = sorted((small, other))
        groups[a] = [groups[a][0], groups[b][1], groups[a][2] + groups[b][2]]
        del groups[b]
    return [
        {
            "min_age": lo,
            "max_age": hi,
            "n": len(grades),
            "q": [round(float(x), 2) for x in np.percentile(grades, range(1, 100))],
        }
        for lo, hi, grades in groups
    ]


def build(path: str) -> dict:
    grades: dict[str, dict[int, list[float]]] = {
        "female": defaultdict(list),
        "male": defaultdict(list),
    }
    kept = skipped = 0
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        sex_col = find_column(header, SEX_COLUMNS)
        age_col = find_column(header, AGE_COLUMNS)
        time_col = find_column(header, TIME_COLUMNS)
        print(f"Using columns: sex={sex_col!r}, age={age_col!r}, time={time_col!r}")
        for row in reader:
            sex = to_sex(row[sex_col] or "")
            seconds = to_seconds(row[time_col] or "")
            try:
                age = int(float(row[age_col]))
            except (TypeError, ValueError):
                age = None
            if sex is None or seconds is None or age is None or not 10 <= age <= 100:
                skipped += 1
                continue
            if not MIN_S <= seconds <= MAX_S:
                skipped += 1
                continue
            grades[sex][band_of(age)].append(age_grade(seconds, MARATHON_M, age, sex))
            kept += 1
    print(f"Kept {kept:,} finishers, skipped {skipped:,} (missing or implausible values)")
    return {
        "source": "2023 Marathon Results by Running with Rock (Kaggle, CC BY 4.0), "
        "https://www.kaggle.com/datasets/runningwithrock/2023-marathon-results",
        "finishers": kept,
        "female": bands_for(grades["female"]),
        "male": bands_for(grades["male"]),
    }


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("Usage: python scripts/build_percentiles.py path/to/Results.csv")
    table = build(sys.argv[1])
    PERCENTILES_FILE.write_text(json.dumps(table, separators=(",", ":")) + "\n")
    for sex in ("female", "male"):
        for b in table[sex]:
            median = b["q"][49]
            print(
                f"  {sex:6} {b['min_age']:>3}-{b['max_age']:<3} n={b['n']:>7,}  "
                f"median age grade {median:.1f}%"
            )
    print(f"Wrote {PERCENTILES_FILE}")


if __name__ == "__main__":
    main()
