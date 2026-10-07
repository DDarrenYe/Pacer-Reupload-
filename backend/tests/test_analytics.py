from datetime import date, timedelta

import numpy as np
import pytest

from app.analytics.best_efforts import compute_best_efforts
from app.analytics.fatigue import pace_drift
from app.analytics.load import training_load
from app.analytics.series import RunSeries
from app.analytics.splits import compute_splits, fastest_and_slowest, split_type


def km_series(paces_s_per_km, hr=None):
    """A run made of whole km at the given paces, one sample every 10 m."""
    dist, time = [0.0], [0.0]
    for pace in paces_s_per_km:
        for _ in range(100):
            dist.append(dist[-1] + 10)
            time.append(time[-1] + pace / 100)
    hr_arr = np.full(len(dist), np.nan if hr is None else float(hr))
    return RunSeries(np.array(dist), np.array(time), hr_arr)


def test_even_run():
    s = km_series([300, 300, 300])
    splits = compute_splits(s)
    assert [sp.pace_s_per_km for sp in splits] == [300, 300, 300]
    assert split_type(s) == "even"
    assert pace_drift(splits) == 0.0


def test_slowing_down_is_positive_split_and_positive_drift():
    s = km_series([280, 290, 300, 310])
    splits = compute_splits(s)
    assert split_type(s) == "positive"
    assert pace_drift(splits) == pytest.approx(10)  # 10 s/km slower every km
    assert fastest_and_slowest(splits) == (1, 4)


def test_speeding_up_is_negative_split():
    s = km_series([310, 300, 290, 280])
    assert split_type(s) == "negative"
    assert pace_drift(compute_splits(s)) == pytest.approx(-10)


def test_partial_last_split():
    s = RunSeries(np.array([0, 1000, 1500.0]), np.array([0, 300, 450.0]), np.full(3, np.nan))
    splits = compute_splits(s)
    assert [(sp.distance_m, sp.is_partial) for sp in splits] == [(1000, False), (500, True)]
    assert splits[1].pace_s_per_km == 300
    # Partial splits don't count for fastest/slowest or drift
    assert fastest_and_slowest(splits) == (1, 1)
    assert pace_drift(splits) is None


def test_tiny_leftover_folds_into_last_split():
    s = RunSeries(
        np.array([0, 1000, 2000, 2020.0]), np.array([0, 300, 600, 606.0]), np.full(4, np.nan)
    )
    splits = compute_splits(s)
    assert [sp.distance_m for sp in splits] == [1000, 1020]


def test_track_splits_per_400m():
    s = km_series([300, 300])
    splits = compute_splits(s, split_length_m=400)
    assert [sp.distance_m for sp in splits] == [400, 400, 400, 400, 400]
    assert splits[0].duration_s == 120


def test_split_heart_rate_from_laps():
    # Two 1 km laps: 140 bpm then 160 bpm
    s = RunSeries(
        np.array([0, 1000, 2000.0]), np.array([0, 300, 600.0]), np.array([np.nan, 140, 160])
    )
    splits = compute_splits(s)
    assert [sp.avg_hr for sp in splits] == [140, 160]
    halves = compute_splits(s, split_length_m=2000)
    assert halves[0].avg_hr == 150


def test_best_efforts_find_the_fast_middle_km():
    s = km_series([320, 270, 320, 320, 320])
    efforts = {e.name: e for e in compute_best_efforts(s)}
    assert efforts["1k"].duration_s == 270
    assert efforts["1k"].start_offset_m == 1000
    assert efforts["400m"].duration_s == pytest.approx(108)
    assert efforts["5k"].duration_s == 1550
    assert "10k" not in efforts  # longer than the run


def test_best_effort_ties_pick_the_earliest():
    s = km_series([300, 300, 300])
    assert {e.name: e for e in compute_best_efforts(s)}["1k"].start_offset_m == 0


def test_training_load_acwr():
    end = date(2026, 10, 31)
    # 4 weeks of 3 x 60 min, then a big final week of 3 x 120 min
    runs = []
    for week in range(5):
        minutes = 120 if week == 4 else 60
        for day in (0, 2, 4):
            runs.append((end - timedelta(days=34) + timedelta(days=week * 7 + day), minutes))
    days = training_load(runs, end=end, days=7)
    last = days[-1]
    assert last.acute_7d == 360
    assert last.chronic_28d == pytest.approx((360 + 3 * 180) / 4)
    assert last.acwr == pytest.approx(360 / 225, abs=0.01)
    assert last.flag == "spike"
    assert len(days) == 7


def test_training_load_needs_history():
    end = date(2026, 10, 31)
    days = training_load([(end, 30)], end=end, days=7)
    assert days[-1].load_min == 30
    assert days[-1].acwr is None and days[-1].flag is None
