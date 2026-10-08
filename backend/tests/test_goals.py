import uuid
from datetime import date, timedelta

import pytest

from app.analytics.goals import RunInfo, WeekPoint, analyse, equivalents, project
from app.analytics.predict import Effort
from tests.conftest import auth

TODAY = date(2026, 10, 8)
HALF = 21097.5
ALICE = uuid.uuid4()
BOB = uuid.uuid4()


def ten_k_race(days_ago: int, minutes: float) -> Effort:
    return Effort(
        "u", f"r{days_ago}", TODAY - timedelta(days=days_ago), 10000, minutes * 60, is_race=True
    )


def training(weeks=4, km=(8, 10, 16), pace=330) -> list[RunInfo]:
    runs = []
    for w in range(weeks):
        for i, d in enumerate(km):
            day = TODAY - timedelta(days=7 * w + 2 * i + 1)
            runs.append(RunInfo(day, d * 1000, d * pace))
    return runs


def test_no_data():
    a = analyse(
        distance_m=HALF,
        target_s=7800,
        race_date=TODAY + timedelta(days=60),
        today=TODAY,
        efforts=[],
        runs=[],
    )
    assert a.status == "no_data"
    assert a.now_s is None
    assert "Upload a few recent runs" in a.recommendations[0]
    assert a.target_pace_s_per_km == pytest.approx(7800 / 21.0975, abs=0.1)


def test_already_there():
    a = analyse(
        distance_m=HALF,
        target_s=2 * 3600,
        race_date=TODAY + timedelta(days=60),
        today=TODAY,
        efforts=[ten_k_race(10, 50)],
        runs=training(),
    )
    assert a.now_s == pytest.approx(3000 * (2.10975) ** 1.06, abs=1)  # Riegel from the 10k
    assert a.status == "already_there"
    assert "10 km race" in a.anchor


def test_within_reach_and_stretch():
    # Flat history: predictions don't move, so there's no projected improvement.
    efforts = [ten_k_race(d, 60) for d in (10, 40, 70)]
    now = 3600 * 2.10975**1.06  # about 2:07:45
    reach = analyse(
        distance_m=HALF,
        target_s=now * 0.97,
        race_date=TODAY + timedelta(weeks=10),
        today=TODAY,
        efforts=efforts,
        runs=training(),
    )
    stretch = analyse(
        distance_m=HALF,
        target_s=now * 0.85,
        race_date=TODAY + timedelta(weeks=4),
        today=TODAY,
        efforts=efforts,
        runs=training(),
    )
    assert reach.status == "within_reach" and reach.needed_pct_per_week == pytest.approx(
        0.3, abs=0.05
    )
    assert stretch.status == "stretch" and stretch.needed_pct_per_week > 0.5


def test_on_track_from_improving_trend():
    # A 10k race every two weeks, each 30 s faster
    efforts = [ten_k_race(d, 55 - 0.5 * i) for i, d in enumerate(range(84, 0, -14))]
    a = analyse(
        distance_m=HALF,
        target_s=1.0,
        race_date=TODAY + timedelta(weeks=8),
        today=TODAY,
        efforts=efforts,
        runs=training(),
    )
    assert a.projected_s < a.now_s  # projected faster than now
    target = (a.now_s + a.projected_s) / 2
    b = analyse(
        distance_m=HALF,
        target_s=target,
        race_date=TODAY + timedelta(weeks=8),
        today=TODAY,
        efforts=efforts,
        runs=training(),
    )
    assert b.status == "on_track"


def test_flat_trend_projects_current_time():
    # Steady training with no new bests: the prediction doesn't move, which is still a trend.
    flat = [WeekPoint(TODAY - timedelta(weeks=11 - i), 7000.0) for i in range(12)]
    projected, note, basis = project(flat, 7000, 8)
    assert (projected, basis) == (7000, "trend")
    assert "hasn't changed in the last 12 weeks" in note


def test_short_history_assumes_current_fitness():
    points = [WeekPoint(TODAY - timedelta(weeks=11 - i), None) for i in range(10)]
    points += [WeekPoint(TODAY - timedelta(weeks=1), 7100.0), WeekPoint(TODAY, 7000.0)]
    projected, note, basis = project(points, 7000, 8)
    assert (projected, basis) == (7000, "current")
    assert "Only 2 weeks of data" in note


def test_steep_trend_is_clamped():
    steep = [WeekPoint(TODAY - timedelta(weeks=11 - i), 8000 - 300 * i) for i in range(12)]
    projected, note, basis = project(steep, 4700, 10)
    assert projected == pytest.approx(4700 - 0.01 * 4700 * 10)  # capped at 1% a week
    assert "caps" in note and basis == "trend"


def test_single_race_still_gives_a_race_day_projection():
    a = analyse(
        distance_m=HALF,
        target_s=2 * 3600,
        race_date=TODAY + timedelta(weeks=8),
        today=TODAY,
        efforts=[ten_k_race(3, 55)],
        runs=[],
    )
    assert a.projected_s == a.now_s is not None
    assert a.projection_basis == "current"


def test_equivalents_are_shorter_checkpoints():
    eq = {name: t for name, _, t in equivalents(HALF, 7800, 1.06)}
    assert set(eq) == {"5k", "10k"}
    assert eq["10k"] == pytest.approx(7800 * (10000 / HALF) ** 1.06, abs=0.1)


def test_recommendations_volume_long_run_pace_and_checkpoint():
    a = analyse(
        distance_m=HALF,
        target_s=7800,
        race_date=TODAY + timedelta(weeks=10),
        today=TODAY,
        efforts=[ten_k_race(10, 62)],
        runs=training(km=(5, 6, 8), pace=400),
    )
    text = " ".join(a.recommendations)
    assert "Build weekly distance towards 30 km" in text
    assert "longest run in the last 4 weeks is 8.0 km" in text
    assert "goal pace" in text
    assert "Checkpoint: a 5k in" in text


def test_recommendations_quiet_when_training_matches():
    runs = training(km=(10, 12, 18), pace=360)
    runs.append(RunInfo(TODAY - timedelta(days=3), 6000, 6000 * 0.36, splits=((1000, 355.0),) * 6))
    a = analyse(
        distance_m=HALF,
        target_s=2 * 3600 + 600,
        race_date=TODAY + timedelta(weeks=10),
        today=TODAY,
        efforts=[ten_k_race(10, 58)],
        runs=runs,
    )
    text = " ".join(a.recommendations)
    assert (
        "weekly distance" not in text
        and "long run" not in text
        and "None of your recent runs" not in text
    )


def test_nearly_meeting_a_guide_counts_as_meeting_it():
    # 29.6 km a week and a 15.9 km long run: within 5% of the half's 30 km / 16 km guides.
    a = analyse(
        distance_m=HALF,
        target_s=2 * 3600 + 600,
        race_date=TODAY + timedelta(weeks=10),
        today=TODAY,
        efforts=[ten_k_race(10, 58)],
        runs=training(km=(6.0, 7.7, 15.9), pace=360),
    )
    text = " ".join(a.recommendations)
    assert "weekly distance" not in text and "long run" not in text


def test_taper_and_load_spike():
    spike = training(weeks=4, km=(5,), pace=330) + [
        RunInfo(TODAY - timedelta(days=i), 15000, 15000 * 0.33) for i in range(1, 6)
    ]
    a = analyse(
        distance_m=HALF,
        target_s=7800,
        race_date=TODAY + timedelta(days=10),
        today=TODAY,
        efforts=[ten_k_race(30, 58), ten_k_race(5, 57)],
        runs=spike,
    )
    assert "taper" in a.recommendations[1] or "taper" in a.recommendations[0]
    assert any("training load has jumped" in r for r in a.recommendations)
    assert not any("Build weekly distance" in r for r in a.recommendations)


def test_race_day_passed_with_result():
    race_day = TODAY - timedelta(days=3)
    runs = [RunInfo(race_day, 21150, 7700, is_race=True)]
    a = analyse(
        distance_m=HALF, target_s=7800, race_date=race_day, today=TODAY, efforts=[], runs=runs
    )
    assert a.status == "passed" and a.result_s == 7700 and a.result_hit is True
    b = analyse(
        distance_m=HALF, target_s=7600, race_date=race_day, today=TODAY, efforts=[], runs=runs
    )
    assert b.result_hit is False
    c = analyse(
        distance_m=HALF, target_s=7600, race_date=race_day, today=TODAY, efforts=[], runs=[]
    )
    assert c.status == "passed" and c.result_s is None


# --- API ------------------------------------------------------------------------------


def _goal(**overrides):
    body = {
        "distance_km": 21.0975,
        "target_time_s": 7800,
        "race_date": (date.today() + timedelta(days=60)).isoformat(),
    }
    return {**body, **overrides}


def test_goal_crud(client):
    r = client.post("/goals", json=_goal(), headers=auth(ALICE))
    assert r.status_code == 201, r.text
    goal = r.json()
    assert goal["name"] == "Half marathon goal"
    assert goal["analysis"]["status"] == "no_data"

    r = client.put(
        f"/goals/{goal['id']}",
        json=_goal(name="Auckland Half", target_time_s=7500),
        headers=auth(ALICE),
    )
    assert r.json()["name"] == "Auckland Half" and r.json()["target_time_s"] == 7500

    assert [g["id"] for g in client.get("/goals", headers=auth(ALICE)).json()] == [goal["id"]]
    assert client.get("/goals", headers=auth(BOB)).json() == []
    assert client.put(f"/goals/{goal['id']}", json=_goal(), headers=auth(BOB)).status_code == 404
    assert client.delete(f"/goals/{goal['id']}", headers=auth(BOB)).status_code == 404
    assert client.delete(f"/goals/{goal['id']}", headers=auth(ALICE)).status_code == 204
    assert client.get("/goals", headers=auth(ALICE)).json() == []


def test_goal_uses_your_runs(client):
    client.post(
        "/runs/manual",
        json={
            "distance_km": 10,
            "duration_s": 3000,
            "is_race": True,
            "started_at": (date.today() - timedelta(days=5)).isoformat() + "T07:00:00Z",
        },
        headers=auth(ALICE),
    )
    a = client.post("/goals", json=_goal(target_time_s=2 * 3600), headers=auth(ALICE)).json()[
        "analysis"
    ]
    assert a["status"] == "already_there"
    assert a["now_s"] == pytest.approx(3000 * 2.10975**1.06, abs=1)
    assert a["projected_s"] == a["now_s"] and a["projection_basis"] == "current"


@pytest.mark.parametrize(
    "overrides",
    [
        {"distance_km": 0.5},
        {"distance_km": 150},
        {"target_time_s": 600},  # a 10-minute half marathon
        {"race_date": (date.today() - timedelta(days=1)).isoformat()},
    ],
)
def test_goal_validation(client, overrides):
    assert client.post("/goals", json=_goal(**overrides), headers=auth(ALICE)).status_code == 422


def test_demo_goals_are_read_only(client):
    token = client.post("/demo/session").json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    assert client.get("/goals", headers=h).status_code == 200
    assert client.post("/goals", json=_goal(), headers=h).status_code == 403


def test_account_deletion_removes_goals(client, db_session_factory):
    from app.models import Goal

    client.post("/goals", json=_goal(), headers=auth(ALICE))
    client.post("/goals", json=_goal(), headers=auth(BOB))
    client.delete("/account", headers=auth(ALICE))
    with db_session_factory() as db:
        assert [g.user_id for g in db.query(Goal).all()] == [BOB]
