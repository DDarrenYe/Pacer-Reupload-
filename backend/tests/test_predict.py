import math
import random
from datetime import date, timedelta

import pytest

from app.analytics.predict import (
    Effort,
    RunVolume,
    build_pairs,
    closest_anchor,
    envelope,
    evaluate,
    fit_pooled,
    is_target,
    personal_fit,
    predict_for_runner,
    riegel,
)
from app.analytics.trends import weekly_trends

START = date(2026, 1, 5)


def law(distance_m, b, five_k_s):
    """Time for a distance from a power law anchored at a given 5k time."""
    return five_k_s * (distance_m / 5000) ** b


def test_riegel_formula():
    anchor = Effort("u", "r", START, 5000, 1200)
    assert riegel(anchor, 10000) == pytest.approx(1200 * 2**1.06)
    assert riegel(anchor, 5000) == 1200


def test_envelope_keeps_fastest_recent_effort_and_ignores_short_ones():
    efforts = [
        Effort("u", "a", START, 5000, 1300),
        Effort("u", "b", START + timedelta(days=10), 5000, 1250),
        Effort("u", "c", START + timedelta(days=11), 400, 70),  # too short
        Effort("u", "d", START + timedelta(days=12), 5000, 1500),  # easy run
        Effort("u", "e", START - timedelta(days=200), 5000, 1100),  # too old
    ]
    env = envelope(efforts, before=START + timedelta(days=20))
    assert [(e.run_id, e.time_s) for e in env] == [("b", 1250)]


def test_envelope_never_includes_the_day_itself():
    efforts = [Effort("u", "a", START, 5000, 1200)]
    assert envelope(efforts, before=START) == []
    assert len(envelope(efforts, before=START + timedelta(days=1))) == 1


def test_closest_anchor_is_nearest_in_log_distance():
    env = [Effort("u", "a", START, 1000, 220), Effort("u", "b", START, 5000, 1200)]
    assert closest_anchor(env, 10000).run_id == "b"
    assert closest_anchor(env, 1609).run_id == "a"


def test_evaluation_anchor_crosses_distances():
    env = [Effort("u", "a", START, 5000, 1200), Effort("u", "b", START, 10000, 2500)]
    assert closest_anchor(env, 5000).run_id == "a"
    assert closest_anchor(env, 5000, exclude_same_distance=True).run_id == "b"
    assert closest_anchor([env[0]], 5000, exclude_same_distance=True) is None


def test_targets_are_races_or_new_bests():
    first = Effort("u", "a", START, 5000, 1300)
    slower = Effort("u", "b", START + timedelta(days=3), 5000, 1400)
    faster = Effort("u", "c", START + timedelta(days=6), 5000, 1250)
    race = Effort("u", "d", START + timedelta(days=9), 5000, 1500, is_race=True)
    all_ = [first, slower, faster, race]
    assert [is_target(e, all_) for e in all_] == [False, False, True, True]


def test_personal_fit_recovers_the_exponent():
    env = [Effort("u", str(d), START, d, law(d, 1.09, 1200)) for d in (1000, 1609.344, 5000, 10000)]
    fit = personal_fit(env)
    assert fit.b == pytest.approx(1.09, abs=1e-6)
    assert fit.predict(5000) == pytest.approx(1200)
    assert fit.extrapolated(42195) and not fit.extrapolated(15000)


def test_personal_fit_accepts_a_measured_10k_against_a_5k():
    env = [Effort("u", "a", START, 5000, 1200), Effort("u", "b", START, 9996, 2500)]
    assert personal_fit(env) is not None


def test_personal_fit_needs_a_spread_of_distances():
    assert personal_fit([Effort("u", "a", START, 5000, 1200)]) is None
    assert (
        personal_fit([Effort("u", "a", START, 5000, 1200), Effort("u", "b", START, 8000, 2000)])
        is None
    )


def synthetic_runner(user, b, five_k, weeks=30, seed=0, volume_km=30.0, improve=0.0):
    """A runner who races or runs hard now and then, mostly easy, following T = a·D^b."""
    rnd = random.Random(seed)
    efforts, volumes = [], []
    for w in range(weeks):
        fitness = five_k * (1 - improve * w / weeks)
        for day_offset, dist in ((1, 5000), (3, 10000), (5, 1000)):
            day = START + timedelta(days=7 * w + day_offset)
            hard = rnd.random() < 0.35
            factor = rnd.uniform(0.99, 1.02) if hard else rnd.uniform(1.12, 1.25)
            efforts.append(
                Effort(
                    user,
                    f"{user}{w}{day_offset}",
                    day,
                    dist,
                    law(dist, b, fitness) * factor,
                    is_race=hard and dist == 10000,
                )
            )
            volumes.append(RunVolume(user, day, volume_km * 1000 / 3))
    return efforts, volumes


def test_pairs_only_use_earlier_days_and_other_distances():
    efforts, volumes = synthetic_runner("u", 1.06, 1200)
    pairs = build_pairs(efforts, volumes)
    assert pairs
    for p in pairs:
        assert p.anchor.day < p.target.day
        assert p.anchor.distance_key != p.target.distance_key


def test_evaluation_reports_not_enough_data():
    efforts = [
        Effort("u", "a", START, 5000, 1200),
        Effort("u", "b", START + timedelta(days=7), 10000, 2500),
    ]
    result = evaluate(efforts, [])
    assert result.enough_data is False
    assert result.scores == []


def test_evaluation_is_time_ordered_and_scores_all_methods():
    efforts, volumes = [], []
    for i, (b, fk) in enumerate([(1.06, 1200), (1.10, 1300), (1.04, 1100)]):
        e, v = synthetic_runner(f"u{i}", b, fk, seed=i, improve=0.05)
        efforts += e
        volumes += v
    result = evaluate(efforts, volumes)
    assert result.enough_data
    assert result.n_train + result.n_test == result.n_pairs
    scores = {s.method: s for s in result.scores}
    assert all(s.n > 0 and s.mae_s is not None for s in scores.values())
    # Each runner's own exponent should beat a one-size-fits-all 1.06 on this data.
    assert scores["Personal exponent"].mape_pct < scores["Riegel (b = 1.06)"].mape_pct
    assert {c["term"] for c in result.coefficients} >= {
        "log_ratio",
        "log_ratio:log_wkm",
    }


def test_pooled_model_recovers_a_volume_effect():
    """Runners with more volume fade less over distance: b = 1.12 - 0.02·log(km+1)."""
    efforts, volumes = [], []
    for i, km in enumerate([10, 20, 40, 60, 80, 100]):
        b = 1.12 - 0.02 * math.log(km + 1)
        e, v = synthetic_runner(f"u{i}", b, 1200, seed=i, volume_km=km, improve=0.04)
        efforts += e
        volumes += v
    model = fit_pooled(build_pairs(efforts, volumes))
    params = model.result.params
    assert params["log_ratio:log_wkm"] < 0  # more volume, smaller exponent
    assert model.exponent(10) > model.exponent(100)


def test_predict_for_runner():
    efforts = [
        Effort("me", "a", START, 5000, 1200),
        Effort("me", "b", START + timedelta(days=2), 10000, 1200 * 2**1.08),
        Effort("other", "c", START, 5000, 900),
    ]
    out = predict_for_runner("me", efforts, [], START + timedelta(days=3), model=None)
    preds = {p.name: p for p in out.predictions}
    assert preds["5k"].riegel_s == 1200  # anchored on the 5k itself
    assert preds["10k"].riegel_s == pytest.approx(1200 * 2**1.08, abs=0.1)
    assert out.personal_exponent == pytest.approx(1.08, abs=0.001)
    assert preds["Marathon"].extrapolated is True
    assert preds["10k"].extrapolated is False
    assert out.envelope_size == 2


def test_predict_with_no_data():
    out = predict_for_runner("me", [], [], START, model=None)
    assert all(p.riegel_s is None and p.personal_s is None for p in out.predictions)
    assert out.personal_exponent is None


def test_weekly_trends():
    today = date(2026, 3, 18)  # a Wednesday
    monday = date(2026, 3, 16)
    runs = [
        (monday, 5000, 1500),
        (monday + timedelta(days=1), 10000, 3000),
        (monday - timedelta(days=7), 8000, 2400),
    ]
    efforts = [Effort("me", "x", monday, 5000, 1500)]
    rows = weekly_trends(runs, efforts, "me", today, weeks=3)
    assert [r.week_start for r in rows] == [
        monday - timedelta(days=14),
        monday - timedelta(days=7),
        monday,
    ]
    assert [r.distance_km for r in rows] == [0, 8, 15]
    assert rows[-1].avg_pace_s_per_km == 300
    assert rows[0].avg_pace_s_per_km is None
    assert rows[-1].predicted_5k_s == 1500
    assert rows[0].predicted_5k_s is None
