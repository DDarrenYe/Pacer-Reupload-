import uuid
from datetime import date, timedelta

import pytest

from tests.conftest import auth

ALICE = uuid.uuid4()
TODAY = date.today()


def manual(client, km, seconds, days_ago=3, user=ALICE, is_race=False):
    r = client.post(
        "/runs/manual",
        json={
            "distance_km": km,
            "duration_s": seconds,
            "is_race": is_race,
            "started_at": (TODAY - timedelta(days=days_ago)).isoformat() + "T07:00:00Z",
        },
        headers=auth(user),
    )
    assert r.status_code == 201
    return r.json()


def card(client, user=ALICE):
    return client.get("/runner-card", headers=auth(user)).json()


def test_empty_card(client):
    assert card(client) == {"name": None, "rank": None, "bests": []}


def test_bests_only_for_distances_you_have_run(client):
    manual(client, 5, 1500)  # 25:00
    manual(client, 5.1, 1500)  # 5.1 km in 25:00: 24:31 for the 5k, a new best
    manual(client, 10.6, 3600)  # more than 5% over 10k: doesn't count as a 10k
    manual(client, 20.5, 7200)  # more than 2% short of a half: doesn't count either
    bests = card(client)["bests"]
    assert [b["name"] for b in bests] == ["5k"]
    assert bests[0]["time_s"] == round(1500 * 5 / 5.1, 1)


def test_a_race_gps_measured_slightly_short_still_counts(client):
    manual(client, 9.95, 2580, is_race=True)  # a 10k race that GPS called 9.95 km
    (best,) = card(client)["bests"]
    assert best["name"] == "10k" and best["time_s"] == round(2580 * 10 / 9.95, 1)


def test_bests_from_gpx_best_efforts(client, data_dir):
    with open(data_dir / "sample.gpx", "rb") as f:
        run = client.post("/runs", files={"file": ("sample.gpx", f)}, headers=auth(ALICE)).json()
    detail = client.get(f"/runs/{run['id']}", headers=auth(ALICE)).json()
    expected = {e["name"]: e["duration_s"] for e in detail["best_efforts"]}
    bests = {b["name"]: b["time_s"] for b in card(client)["bests"]}
    assert set(bests) <= {"5k", "10k", "Half marathon", "Marathon"}
    for name, time_s in bests.items():
        assert time_s == round(expected[name], 1)


def test_name_and_rank(client):
    manual(client, 10, 2700, is_race=True)
    assert card(client)["rank"] is None  # no age or sex yet
    client.put(
        "/profile",
        json={"display_name": "Darren", "birth_year": TODAY.year - 32, "sex": "male"},
        headers=auth(ALICE),
    )
    body = card(client)
    assert body["name"] == "Darren"
    assert body["rank"]["rank"] == "Platinum"
    assert [b["name"] for b in body["bests"]] == ["10k"]


def test_cards_are_private(client):
    manual(client, 5, 1500)
    assert card(client, user=uuid.uuid4())["bests"] == []


def test_name_falls_back_to_strava(client, db_session_factory):
    from app.models import StravaConnection

    with db_session_factory() as db:
        db.add(
            StravaConnection(
                user_id=ALICE,
                athlete_id=1,
                athlete_name="Darren Strava",
                access_token="x",
                refresh_token="x",
                expires_at=0,
                scope="activity:read_all",
                sync_after=0,
            )
        )
        db.commit()
    assert card(client)["name"] == "Darren Strava"
    client.put("/profile", json={"display_name": "D"}, headers=auth(ALICE))
    assert card(client)["name"] == "D"


def test_a_real_best_time_earns_a_rank(client):
    # A treadmill 5k that isn't a race doesn't feed predictions, but it's a real time.
    manual(client, 5, 1500)
    client.put("/profile", json={"birth_year": TODAY.year - 32, "sex": "male"}, headers=auth(ALICE))
    rank = card(client)["rank"]
    assert rank["source"] == "best time" and rank["distance"] == "5k"
    from app.analytics.compare import age_grade

    assert rank["age_grade"] == round(age_grade(1500, 5000, 32, "male"), 1)
    assert rank["rank"] == "Gold"  # about 51%
    # The Trends banner uses the same rule, so the two always agree.
    assert client.get("/comparison", headers=auth(ALICE)).json()["overall"] == rank


def test_rank_takes_the_better_of_best_time_and_prediction():
    from app.analytics import compare as cmp

    row = cmp.ComparisonRow("10k", 10000, 2700, None, False, 58.7, None, None, cmp.rank_for(58.7))
    best = cmp.best_rank([row], [("5k", 5000, 1500)], 32, "male")
    assert (best.distance, best.source, best.rank.name) == ("10k", "prediction", "Platinum")
    best = cmp.best_rank([row], [("5k", 5000, 1200)], 32, "male")  # a 20:00 5k: 64.1%
    assert (best.distance, best.source, best.rank.name) == ("5k", "best time", "Diamond")
    assert cmp.age_grade(best.next_rank_time_s, 5000, 32, "male") == pytest.approx(70, abs=0.01)
    assert cmp.best_rank([], [], 32, "male") is None
