import json
import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.analytics import compare as cmp
from app.analytics.predict import Effort
from app.models import Profile
from tests.conftest import auth

TODAY = date.today()
ALICE = uuid.uuid4()


def table(**bands) -> dict:
    """A percentile table whose age grades run evenly from `lo` to `hi`."""

    def band(min_age, max_age, lo, hi, n=1000):
        return {
            "min_age": min_age,
            "max_age": max_age,
            "n": n,
            "q": [round(lo + (hi - lo) * i / 98, 2) for i in range(99)],
        }

    return {
        "source": "test data",
        "finishers": 4000,
        "male": [band(5, 29, 40, 80), band(30, 34, 40, 80), band(35, 100, 30, 70)],
        "female": [band(5, 100, 35, 75)],
        **bands,
    }


@pytest.fixture
def percentiles(tmp_path, monkeypatch):
    """Point the app at a test percentile table (the real one is built by Darren)."""
    path = tmp_path / "finisher_percentiles.json"
    path.write_text(json.dumps(table()))
    monkeypatch.setattr(cmp, "PERCENTILES_FILE", path)
    cmp.percentile_table.cache_clear()
    yield path
    cmp.percentile_table.cache_clear()


@pytest.fixture
def no_percentiles(tmp_path, monkeypatch):
    monkeypatch.setattr(cmp, "PERCENTILES_FILE", tmp_path / "missing.json")
    cmp.percentile_table.cache_clear()
    yield
    cmp.percentile_table.cache_clear()


def test_age_grade_uses_the_2025_standards():
    # Men aged 30: the 5 km standard is 12:49 (769 s), so a 20:00 5k is 64.1%.
    assert cmp.age_grade(1200, 5000, 30, "male") == pytest.approx(64.08, abs=0.01)
    # Same time, older runner: a higher grade.
    assert cmp.age_grade(1200, 5000, 60, "male") > cmp.age_grade(1200, 5000, 30, "male")
    # Women's standards are slower, so the same time grades higher.
    assert cmp.age_grade(1200, 5000, 30, "female") > cmp.age_grade(1200, 5000, 30, "male")
    # Ages outside the tables use the nearest one.
    assert cmp.age_grade(3600, 10000, 104, "female") == cmp.age_grade(3600, 10000, 100, "female")
    for distance in cmp.DISTANCES.values():
        assert cmp.standard_s(distance, 40, "female") > 0


@pytest.mark.parametrize(
    ("grade", "label"),
    [
        (95, "World class"),
        (85, "National class"),
        (72, "Regional class"),
        (61, "Local class"),
        (45, "Recreational"),
    ],
)
def test_band_labels(grade, label):
    assert cmp.band_label(grade) == label


def test_percentile_lookup(percentiles):
    mid = cmp.percentile(60, 32, "male")
    assert mid.faster_than_pct == pytest.approx(50, abs=1)
    assert mid.group == "men aged 30–34"
    assert cmp.percentile(90, 32, "male").faster_than_pct == 100
    assert cmp.percentile(20, 32, "male").faster_than_pct < 1
    assert cmp.percentile(60, 50, "male").group == "men aged 35+"
    assert cmp.percentile(55, 40, "female").group == "women aged 5+"


def test_percentile_uses_nearest_band_outside_the_data():
    t = table(male=[{"min_age": 20, "max_age": 60, "n": 9, "q": list(range(1, 100))}])
    assert cmp.percentile(50, 12, "male", t).group == "men aged 20–60"
    assert cmp.percentile(50, 75, "male", t).group == "men aged 20–60"


def test_no_percentile_table_means_no_percentile(no_percentiles):
    assert cmp.percentile(60, 32, "male") is None


def race(days_ago, km, minutes):
    return Effort(
        "u", f"r{days_ago}", TODAY - timedelta(days=days_ago), km * 1000, minutes * 60, is_race=True
    )


def test_compare_gives_all_five_distances(percentiles):
    rows = cmp.compare([race(10, 10, 45)], 32, "male", TODAY)
    assert [r.name for r in rows] == ["5k", "10k", "15k", "Half marathon", "Marathon"]
    ten = rows[1]
    assert (
        ten.time_s == 2700
        and ten.anchor == "your 10 km race on " + (TODAY - timedelta(days=10)).isoformat()
    )
    assert ten.age_grade == pytest.approx(100 * 1584 / 2700, abs=0.1)
    assert ten.band == "Recreational" and ten.percentile.group == "men aged 30–34"
    assert not ten.extrapolated and rows[4].extrapolated  # a marathon from a 10k


def test_compare_without_efforts():
    rows = cmp.compare([], 30, "female", TODAY)
    assert all(r.time_s is None and r.age_grade is None for r in rows)


# API


def test_profile_starts_empty_and_saves(client):
    assert client.get("/profile", headers=auth(ALICE)).json() == {
        "display_name": None,
        "birth_year": None,
        "sex": None,
        "age": None,
    }
    r = client.put(
        "/profile",
        json={"display_name": "  Darren   Y ", "birth_year": 1994, "sex": "male"},
        headers=auth(ALICE),
    )
    assert r.json() == {
        "display_name": "Darren Y",
        "birth_year": 1994,
        "sex": "male",
        "age": TODAY.year - 1994,
    }
    r = client.put("/profile", json={"birth_year": 1990, "sex": "female"}, headers=auth(ALICE))
    assert r.json()["sex"] == "female"
    assert client.get("/profile", headers=auth(uuid.uuid4())).json()["birth_year"] is None


@pytest.mark.parametrize(
    "body",
    [{"birth_year": 1900}, {"birth_year": TODAY.year}, {"sex": "other"}],
)
def test_profile_validation(client, body):
    assert client.put("/profile", json=body, headers=auth(ALICE)).status_code == 422


def test_demo_profile_is_read_only(client):
    token = client.post("/demo/session").json()["access_token"]
    r = client.put(
        "/profile", json={"birth_year": 1990}, headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 403


def test_comparison_needs_a_profile(client, no_percentiles):
    body = client.get("/comparison", headers=auth(ALICE)).json()
    assert body["rows"] == [] and body["sources"]["percentiles"] is None
    assert "Alan Jones" in body["sources"]["age_grade"]


def test_comparison_with_runs(client, percentiles):
    client.put("/profile", json={"birth_year": TODAY.year - 32, "sex": "male"}, headers=auth(ALICE))
    client.post(
        "/runs/manual",
        json={
            "distance_km": 10,
            "duration_s": 2700,
            "is_race": True,
            "started_at": (TODAY - timedelta(days=5)).isoformat() + "T07:00:00Z",
        },
        headers=auth(ALICE),
    )
    body = client.get("/comparison", headers=auth(ALICE)).json()
    assert body["profile"]["age"] == 32
    assert body["sources"]["finishers"] == 4000
    ten = body["rows"][1]
    assert ten["name"] == "10k" and ten["time_s"] == 2700
    assert ten["group"] == "men aged 30–34" and 0 < ten["faster_than_pct"] < 100


def test_account_deletion_removes_profile(client, db_session_factory):
    client.put("/profile", json={"birth_year": 1994, "sex": "male"}, headers=auth(ALICE))
    assert client.delete("/account", headers=auth(ALICE)).status_code == 204
    with db_session_factory() as db:
        assert db.scalar(select(Profile)) is None


# The build script


def test_build_percentiles_script(tmp_path, monkeypatch):
    from scripts import build_percentiles as bp

    monkeypatch.setattr(bp, "MIN_PER_BAND", 3)
    rows = ["Gender,Age,Finish"]
    for i in range(6):
        rows.append(f"M,{31 + i % 3},{3 * 3600 + i * 600}")  # men 30-34: 6 finishers
        rows.append(f"F,{42},{4 * 3600 + i * 300}")  # women 40-44
    rows.append("M,72,04:30:00")  # a lone man aged 70-74: merged into the band before
    rows += ["X,40,14400", "M,,14400", "M,40,600", "F,30,not a time"]  # all skipped
    csv = tmp_path / "Results.csv"
    csv.write_text("\n".join(rows) + "\n")

    t = bp.build(str(csv))
    assert t["finishers"] == 13
    male = t["male"]
    assert [(b["min_age"], b["max_age"], b["n"]) for b in male] == [(30, 100, 7)]
    assert len(male[0]["q"]) == 99 and male[0]["q"] == sorted(male[0]["q"])
    assert [(b["min_age"], b["n"]) for b in t["female"]] == [(40, 6)]


def test_build_percentiles_reads_time_formats():
    from scripts import build_percentiles as bp

    assert bp.to_seconds("3:30:00") == 12600
    assert bp.to_seconds("45:10") == 2710
    assert bp.to_seconds("12600") == 12600
    assert bp.to_seconds("") is None and bp.to_seconds("dnf") is None
    assert bp.to_sex("Female") == "female" and bp.to_sex("M") == "male" and bp.to_sex("X") is None
    assert bp.band_of(17) == 0 and bp.band_of(33) == 30 and bp.band_of(91) == 80


# Ranks


@pytest.mark.parametrize(
    ("grade", "name", "tier", "next_name"),
    [
        (12.0, "Bronze", 1, "Silver"),
        (34.9, "Bronze", 1, "Silver"),
        (35.0, "Silver", 2, "Gold"),
        (48.0, "Gold", 3, "Platinum"),
        (52.0, "Platinum", 4, "Diamond"),
        (60.0, "Diamond", 5, "Emerald"),
        (75.0, "Emerald", 6, "Pace Setter"),
        (85.0, "Pace Setter", 7, "Apex"),
        (90.0, "Apex", 8, None),
        (104.0, "Apex", 8, None),
    ],
)
def test_rank_thresholds(grade, name, tier, next_name):
    rank = cmp.rank_for(grade)
    assert (rank.name, rank.tier, rank.next_name) == (name, tier, next_name)


def test_rank_progress():
    assert cmp.rank_for(65.0).progress(65.0) == 50.0  # halfway through Diamond (60-70)
    assert cmp.rank_for(95.0).progress(95.0) is None  # nothing above Apex


@pytest.mark.parametrize(
    ("grade", "label", "step"),
    [
        (0.0, "Bronze 3", ("Bronze 2", 11.7)),
        (11.6, "Bronze 3", ("Bronze 2", 11.7)),
        (11.7, "Bronze 2", ("Bronze 1", 23.4)),
        (23.4, "Bronze 1", ("Silver 3", 35.0)),
        (47.3, "Gold 3", ("Gold 2", 47.4)),
        (60.0, "Diamond 3", ("Diamond 2", 63.4)),
        (63.3, "Diamond 3", ("Diamond 2", 63.4)),
        (63.4, "Diamond 2", ("Diamond 1", 66.7)),
        (66.7, "Diamond 1", ("Emerald 3", 70.0)),
        (79.9, "Emerald 1", ("Pace Setter", 80.0)),
        (85.0, "Pace Setter", ("Apex", 90.0)),
        (95.0, "Apex", None),
    ],
)
def test_rank_divisions(grade, label, step):
    rank = cmp.rank_for(grade)
    assert rank.label(grade) == label
    assert rank.next_step(grade) == step


def test_divisions_split_each_rank_in_thirds():
    for name, floor in cmp.RANKS:
        rank = cmp.rank_for(floor)
        if name in cmp.UNDIVIDED:
            assert rank.division(floor) is None
            continue
        floors = rank.floors()
        assert floors[0] == floor and len(floors) == 3
        span = (rank.next_floor - floor) / 3
        # each boundary is the true third, rounded up to the next 0.1%
        assert all(0 <= f - (floor + i * span) < 0.1 for i, f in enumerate(floors))
        assert [rank.division(f) for f in floors] == [3, 2, 1]


def test_time_for_next_step_earns_it():
    best = cmp.best_rank([], [("10k", 10000, 2830)], 32, "male")  # 56%
    assert best.label == "Platinum 2" and best.division == 2
    assert best.next_step == "Platinum 1"
    grade = round(cmp.age_grade(best.next_step_time_s, 10000, 32, "male"), 1)  # as the app rounds
    assert cmp.rank_for(grade).label(grade) == "Platinum 1"
    assert grade == pytest.approx(best.next_step_age_grade, abs=0.01)


def test_time_for_next_rank_earns_it(percentiles):
    rows = cmp.compare([race(10, 10, 45)], 32, "male", TODAY)
    ten = rows[1]
    assert ten.rank.name == "Platinum" and ten.rank.next_name == "Diamond"
    assert cmp.age_grade(ten.next_rank_time_s, 10000, 32, "male") == pytest.approx(60.0, abs=0.01)


def test_best_row_ignores_extrapolated_distances():
    row = lambda name, grade, extrapolated: cmp.ComparisonRow(  # noqa: E731
        name, 0, 1, None, extrapolated, grade, None, None, cmp.rank_for(grade)
    )
    rows = [row("5k", 55, False), row("Marathon", 70, True)]
    assert cmp.best_row(rows).name == "5k"
    assert cmp.best_row([row("Marathon", 70, True)]).name == "Marathon"
    assert cmp.best_row([]) is None


def test_comparison_includes_overall_rank(client, percentiles):
    client.put("/profile", json={"birth_year": TODAY.year - 32, "sex": "male"}, headers=auth(ALICE))
    assert client.get("/comparison", headers=auth(ALICE)).json()["overall"] is None  # no runs yet
    client.post(
        "/runs/manual",
        json={
            "distance_km": 10,
            "duration_s": 2700,
            "is_race": True,
            "started_at": (TODAY - timedelta(days=5)).isoformat() + "T07:00:00Z",
        },
        headers=auth(ALICE),
    )
    body = client.get("/comparison", headers=auth(ALICE)).json()
    overall = body["overall"]
    assert overall["rank"] == "Platinum" and overall["tier"] == 4
    assert overall["label"] == f"Platinum {overall['division']}"
    assert overall["next_step"] and overall["next_step_age_grade"] > overall["age_grade"]
    best = max((r for r in body["rows"] if not r["extrapolated"]), key=lambda r: r["age_grade"])
    assert overall["distance"] == best["name"] and overall["age_grade"] == best["age_grade"]
    assert overall["next_rank"] == "Diamond" and 0 < overall["progress_pct"] < 100
    assert overall["next_rank_time_s"] <= overall["next_step_time_s"] < best["time_s"]
    assert body["rows"][1]["rank"] == "Platinum"
    assert body["rows"][1]["rank_label"].startswith("Platinum ")
