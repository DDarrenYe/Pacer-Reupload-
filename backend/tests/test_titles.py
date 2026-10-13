import uuid

import pytest

from app.analytics import titles as t
from tests.conftest import auth

STEADY = (300.0, 301.0, 299.0, 300.0, 300.0, 301.0)


def run(paces, *, split_type="even", km=None, climb=0.0):
    km = km if km is not None else len(paces)
    return t.RunSplits(tuple(paces), km * 1000, split_type, climb)


def title_for(runs, best_1k=None, best_5k=None):
    return t.assign_title(runs, best_1k, best_5k)


@pytest.mark.parametrize(
    ("make", "expected"),
    [
        (lambda: run((285, 300, 305, 310, 315), split_type="positive"), "The Rabbit"),
        (lambda: run((300, 302, 301, 300, 285)), "The Kicker"),
        (lambda: run(STEADY), "The Metronome"),
        (lambda: run((330, 300, 301, 299, 300, 300, 301, 300, 300), km=9), "The Diesel"),
        (
            lambda: run((310, 306, 302, 298, 294, 292), split_type="negative"),
            "The Negative Splitter",
        ),
        (lambda: run((300, 301, 285, 301, 300, 300)), "The Surge Runner"),
        (lambda: run((300, 305, 298, 303, 300), climb=100), "The Mountain Goat"),
    ],
)
def test_each_trait_wins_when_it_dominates(make, expected):
    title = title_for([make() for _ in range(4)])
    assert title.name == expected
    assert title.reason.startswith("4 of your 4 recent runs") and title.runs_considered == 4


def test_power_sprinter_from_best_efforts():
    # 1k in 3:00, 5k in 21:00 (4:12/km): 5k pace is 40% slower, far beyond the usual 10%.
    title = title_for([run(STEADY) for _ in range(4)], best_1k=180, best_5k=1260)
    assert title.name == "The Power Sprinter" and "1k pace is 40% quicker" in title.reason
    # A normal speed gap doesn't make you a sprinter.
    assert title_for([run(STEADY)] * 4, best_1k=270, best_5k=5 * 297).name == "The Metronome"


def test_majority_trait_wins_and_ties_follow_the_order():
    runs = [run((300, 302, 301, 300, 285))] * 3 + [run(STEADY)] * 2
    assert title_for(runs).name == "The Kicker"
    tie = [run((300, 302, 301, 300, 285))] * 2 + [run(STEADY)] * 2
    assert title_for(tie).name == "The Kicker"  # Kicker comes before Metronome


def test_fallback_when_no_trait_shows():
    # Uneven (over 4% variation) but no clean trait: no fade, no kick, no single surge.
    wobbly = run((300, 340, 330, 320, 315), split_type="even")
    title = title_for([wobbly] * 3)
    assert title.name == "The Surge Runner" and "moves around" in title.reason
    calm = run((300, 302, 304, 306, 308), split_type="positive")
    assert title_for([calm] * 3).name == "The Metronome"


def test_needs_three_runs_with_splits():
    assert title_for([run(STEADY), run(STEADY)]) is None
    assert title_for([run(STEADY)] * 2 + [run((300, 301))]) is None  # 2 splits don't count


def test_runner_card_title(client):
    alice = uuid.uuid4()
    for days in (1, 2):
        client.post(
            "/runs/manual",
            json={
                "distance_km": 5,
                "duration_s": 1500,
                "started_at": f"2026-10-0{days}T07:00:00Z",
            },
            headers=auth(alice),
        )
    # Manual runs have no splits, so they don't count towards a title.
    title = client.get("/runner-card", headers=auth(alice)).json()["title"]
    assert title == {"locked": True, "runs_considered": 0, "needed": 3}


def test_runner_card_title_from_gpx_runs(client, data_dir, monkeypatch):
    monkeypatch.setattr(t, "MIN_RUNS", 1)
    monkeypatch.setattr("app.routes.profile.MIN_RUNS", 1)
    alice = uuid.uuid4()
    with open(data_dir / "sample.gpx", "rb") as f:
        client.post("/runs", files={"file": ("sample.gpx", f)}, headers=auth(alice))
    title = client.get("/runner-card", headers=auth(alice)).json()["title"]
    assert title["locked"] is False and title["name"] in t.TITLES and title["runs_considered"] == 1
