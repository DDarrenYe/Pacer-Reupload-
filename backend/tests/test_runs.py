import uuid

import pytest

from app.storage import StorageError
from tests.conftest import auth, make_token

ALICE = uuid.uuid4()
BOB = uuid.uuid4()


def upload(client, data_dir, filename="sample.gpx", user=ALICE, **form):
    with open(data_dir / filename, "rb") as f:
        return client.post("/runs", files={"file": (filename, f)}, data=form, headers=auth(user))


def test_upload_gpx_saves_run_and_file(client, data_dir, storage):
    r = upload(client, data_dir, is_race="true", name="Parkrun")
    assert r.status_code == 201, r.text
    run = r.json()
    assert run["source"] == "gpx"
    assert run["surface"] == "road"
    assert run["is_race"] is True
    assert run["name"] == "Parkrun"
    assert run["distance_m"] == pytest.approx(3000, abs=1)
    assert run["started_at"].startswith("2026-10-04T07:00:00")

    [key] = storage.files
    assert key.startswith(f"{ALICE}/") and key.endswith(".gpx")
    assert storage.files[key] == (data_dir / "sample.gpx").read_bytes()


def test_csv_defaults_to_treadmill(client, data_dir):
    r = upload(client, data_dir, "treadmill.csv", started_at="2026-10-05T18:30:00Z")
    assert r.status_code == 201, r.text
    run = r.json()
    assert run["surface"] == "treadmill"
    assert run["started_at"].startswith("2026-10-05T18:30:00")
    # duration-weighted mean of the four laps that have heart rate
    assert run["avg_hr"] == pytest.approx(
        (142 * 300 + 150 * 295 + 156 * 290 + 161 * 285) / 1170, abs=0.1
    )


def test_surface_override(client, data_dir):
    r = upload(client, data_dir, surface="track")
    assert r.json()["surface"] == "track"


def test_duplicate_upload_is_rejected(client, data_dir, storage):
    first = upload(client, data_dir).json()
    r = upload(client, data_dir)
    assert r.status_code == 409
    assert r.json()["detail"]["run_id"] == first["id"]
    assert len(storage.files) == 1


def test_same_file_for_different_users_is_fine(client, data_dir):
    assert upload(client, data_dir, user=ALICE).status_code == 201
    assert upload(client, data_dir, user=BOB).status_code == 201


def test_list_and_get_only_your_own_runs(client, data_dir):
    alice_run = upload(client, data_dir, user=ALICE).json()
    upload(client, data_dir, "treadmill.csv", user=BOB)

    runs = client.get("/runs", headers=auth(ALICE)).json()
    assert [r["id"] for r in runs] == [alice_run["id"]]

    assert client.get(f"/runs/{alice_run['id']}", headers=auth(ALICE)).status_code == 200
    assert client.get(f"/runs/{alice_run['id']}", headers=auth(BOB)).status_code == 404


def test_list_is_newest_first(client, data_dir):
    upload(client, data_dir, "treadmill.csv", started_at="2026-10-01T06:00:00Z")
    upload(client, data_dir, "sample.gpx")  # 2026-10-04
    dates = [r["started_at"][:10] for r in client.get("/runs", headers=auth(ALICE)).json()]
    assert dates == ["2026-10-04", "2026-10-01"]


def test_delete_removes_row_and_file(client, data_dir, storage):
    run = upload(client, data_dir).json()
    assert client.delete(f"/runs/{run['id']}", headers=auth(BOB)).status_code == 404
    assert client.delete(f"/runs/{run['id']}", headers=auth(ALICE)).status_code == 204
    assert client.get(f"/runs/{run['id']}", headers=auth(ALICE)).status_code == 404
    assert storage.files == {}


def test_bad_file_stores_nothing(client, data_dir, storage):
    r = upload(client, data_dir, "not_gpx.gpx")
    assert r.status_code == 422
    assert storage.files == {}
    assert client.get("/runs", headers=auth(ALICE)).json() == []


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer not-a-jwt"},
        {"Authorization": f"Bearer {make_token(ALICE, expires_in=-10)}"},
        {"Authorization": f"Bearer {make_token(ALICE, aud='anon')}"},
    ],
    ids=["missing", "garbage", "expired", "wrong-audience"],
)
def test_requires_valid_token(client, headers):
    assert client.get("/runs", headers=headers).status_code == 401


def test_upload_returns_analytics(client, data_dir):
    run = upload(client, data_dir).json()
    assert [s["pace_s_per_km"] for s in run["splits"]] == [300, 300, 300]
    assert run["split_type"] == "even"
    assert run["pace_drift_s_per_km"] == 0
    assert run["avg_hr"] == pytest.approx(149, abs=0.5)
    efforts = {e["name"]: e["duration_s"] for e in run["best_efforts"]}
    assert efforts == {"400m": 120, "1k": 300, "1 mile": pytest.approx(482.8, abs=0.1)}

    detail = client.get(f"/runs/{run['id']}", headers=auth(ALICE)).json()
    assert detail["splits"] == run["splits"]
    assert detail["best_efforts"] == run["best_efforts"]


def test_track_runs_split_every_400m(client, data_dir):
    run = upload(client, data_dir, surface="track").json()
    assert len(run["splits"]) == 8  # 7 x 400 m + 200 m
    assert run["splits"][-1]["is_partial"] is True
    assert all(s["split_length_m"] == 400 for s in run["splits"])


def test_list_has_summary_fields_but_not_splits(client, data_dir):
    upload(client, data_dir)
    [run] = client.get("/runs", headers=auth(ALICE)).json()
    assert run["split_type"] == "even"
    assert "splits" not in run


def test_reprocess_rebuilds_analytics_from_stored_file(client, data_dir, db_session_factory):
    from app.models import Run

    run_id = upload(client, data_dir).json()["id"]
    # Simulate a run saved before analytics existed
    with db_session_factory() as db:
        run = db.get(Run, uuid.UUID(run_id))
        run.splits, run.best_efforts, run.split_type = [], [], None
        db.commit()
    assert client.get(f"/runs/{run_id}", headers=auth(ALICE)).json()["splits"] == []

    r = client.post(f"/runs/{run_id}/reprocess", headers=auth(ALICE))
    assert r.status_code == 200
    assert len(r.json()["splits"]) == 3
    assert r.json()["split_type"] == "even"
    assert client.post(f"/runs/{run_id}/reprocess", headers=auth(BOB)).status_code == 404


def test_delete_removes_splits_and_best_efforts(client, data_dir, db_session_factory):
    from app.models import BestEffort, Split

    run_id = upload(client, data_dir).json()["id"]
    client.delete(f"/runs/{run_id}", headers=auth(ALICE))
    with db_session_factory() as db:
        assert db.query(Split).count() == 0
        assert db.query(BestEffort).count() == 0


def test_training_load(client, data_dir):
    upload(client, data_dir, "treadmill.csv", started_at=_today_iso())
    days = client.get("/training-load?days=7", headers=auth(ALICE)).json()
    assert len(days) == 7
    today = days[-1]
    assert today["load_min"] == pytest.approx(1450 / 60, abs=0.1)
    assert today["acute_7d"] == today["load_min"]
    assert today["acwr"] is None  # not enough history yet

    assert client.get("/training-load", headers=auth(BOB)).json()[-1]["load_min"] == 0
    assert client.get("/training-load?days=3", headers=auth(ALICE)).status_code == 422
    assert client.get("/training-load").status_code == 401


def _today_iso() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).replace(hour=0, minute=1).isoformat()


def _csv_run(km, minutes):
    return f"distance_km,time\n{km},{minutes}:00\n".encode()


def _upload_csv(client, user, km, minutes, day, race=False):
    return client.post(
        "/runs",
        files={"file": (f"{km}-{day}.csv", _csv_run(km, minutes))},
        data={"started_at": f"{day}T07:00:00Z", "is_race": str(race).lower()},
        headers=auth(user),
    )


def test_predictions_from_uploaded_runs(client):
    assert _upload_csv(client, ALICE, 5, 20, "2026-09-01", race=True).status_code == 201
    assert _upload_csv(client, ALICE, 10, 42, "2026-09-08", race=True).status_code == 201
    body = client.get("/predictions", headers=auth(ALICE)).json()
    preds = {p["name"]: p for p in body["predictions"]}
    # The 10k race anchors the 10k prediction: you've just run it.
    assert preds["10k"]["riegel_s"] == pytest.approx(42 * 60, abs=1)
    assert preds["5k"]["riegel_s"] == pytest.approx(20 * 60, abs=1)
    assert body["personal_exponent"] == pytest.approx(1.07, abs=0.01)  # log2(42/20)
    assert preds["Marathon"]["extrapolated"] is True
    assert body["pooled_exponent"] is None  # far too little data to fit

    # Another runner sees only their own (empty) predictions.
    bob = client.get("/predictions", headers=auth(BOB)).json()
    assert all(p["riegel_s"] is None for p in bob["predictions"])


def test_evaluation_endpoint_with_little_data(client):
    _upload_csv(client, ALICE, 5, 20, "2026-09-01", race=True)
    body = client.get("/predictions/evaluation", headers=auth(ALICE)).json()
    assert body["enough_data"] is False
    assert body["scores"] == []


def test_trends(client):
    from datetime import UTC, datetime, timedelta

    today = datetime.now(UTC).date()
    monday = today - timedelta(days=today.weekday())
    _upload_csv(client, ALICE, 5, 25, monday.isoformat())
    weeks = client.get("/trends?weeks=4", headers=auth(ALICE)).json()
    assert len(weeks) == 4
    assert weeks[-1]["week_start"] == monday.isoformat()
    assert weeks[-1]["distance_km"] == 5
    assert weeks[-1]["avg_pace_s_per_km"] == 300
    assert weeks[0]["runs"] == 0
    assert client.get("/trends?weeks=4", headers=auth(BOB)).json()[-1]["runs"] == 0
    assert client.get("/trends").status_code == 401


def test_which_efforts_feed_predictions(db_session_factory):
    from datetime import UTC, datetime

    from app.analytics.data import load_efforts
    from app.models import BestEffort, Run

    def run(source, distance, race=False, efforts=()):
        return Run(
            user_id=ALICE,
            started_at=datetime(2026, 9, 1, tzinfo=UTC),
            source=source,
            surface="road",
            distance_m=distance,
            elapsed_s=1,
            moving_time_s=distance / 4,
            avg_pace_s_per_km=250,
            is_race=race,
            raw_file_key=str(uuid.uuid4()),
            file_hash=str(uuid.uuid4()),
            best_efforts=[
                BestEffort(name=n, distance_m=d, duration_s=d / 4, start_offset_m=0)
                for n, d in efforts
            ],
        )

    with db_session_factory() as db:
        db.add_all(
            [
                # GPX 5.2 km run: its 5k counts, its 1k (nested, 19% of the run) doesn't
                run("gpx", 5200, efforts=[("5k", 5000), ("1k", 1000)]),
                # CSV: interpolated efforts never count
                run("csv", 5000, efforts=[("5k", 5000)]),
                # A race counts as a whole, from any source
                run("csv", 10000, race=True),
            ]
        )
        db.commit()
        efforts = load_efforts(db, ALICE)
    assert sorted((e.distance_m, e.is_race) for e in efforts) == [(5000, False), (10000, True)]


def test_reprocess_all_only_touches_your_runs(client, data_dir, db_session_factory):
    from app.models import Run

    mine = upload(client, data_dir, user=ALICE).json()["id"]
    theirs = upload(client, data_dir, user=BOB).json()["id"]
    with db_session_factory() as db:  # pretend both were saved with old numbers
        for rid in (mine, theirs):
            db.get(Run, uuid.UUID(rid)).distance_m = 1.0
        db.commit()

    r = client.post("/runs/reprocess-all", headers=auth(ALICE))
    assert r.json() == {"reprocessed": 1, "failed": 0}
    with db_session_factory() as db:
        assert db.get(Run, uuid.UUID(mine)).distance_m == pytest.approx(3000, abs=1)
        assert db.get(Run, uuid.UUID(theirs)).distance_m == 1.0


def test_reprocess_all_counts_missing_files(client, data_dir, storage):
    upload(client, data_dir)
    storage.files.clear()  # the stored original has gone
    storage.download = lambda key: (_ for _ in ()).throw(StorageError("missing"))
    assert client.post("/runs/reprocess-all", headers=auth(ALICE)).json() == {
        "reprocessed": 0,
        "failed": 1,
    }


def _manual(client, user=ALICE, **overrides):
    body = {"distance_km": 5, "duration_s": 1650, "started_at": "2026-10-06T18:00:00Z"}
    return client.post("/runs/manual", json={**body, **overrides}, headers=auth(user))


def test_manual_run_calculates_pace(client):
    r = _manual(client, avg_hr=150)
    assert r.status_code == 201, r.text
    run = r.json()
    assert run["source"] == "manual"
    assert run["surface"] == "treadmill"
    assert run["distance_m"] == 5000
    assert run["moving_time_s"] == run["elapsed_s"] == 1650
    assert run["avg_pace_s_per_km"] == 330  # 27:30 over 5 km = 5:30 /km
    assert run["avg_hr"] == 150
    assert run["name"] == "5 km treadmill run"
    # No made-up splits or efforts from a single total
    assert run["splits"] == [] and run["best_efforts"] == []
    assert run["split_type"] is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"distance_km": 0},
        {"duration_s": -5},
        {"distance_km": 50, "duration_s": 1200},  # 50 km in 20 min
        {"distance_km": 1, "duration_s": 3 * 3600},  # 3 h for 1 km
        {"surface": "moon"},
        {"avg_hr": 400},
    ],
)
def test_manual_run_validation(client, overrides):
    assert _manual(client, **overrides).status_code == 422


def test_manual_runs_appear_in_list_and_load_and_can_be_deleted(client, storage):
    from datetime import UTC, datetime

    today = datetime.now(UTC).replace(hour=6).isoformat()
    run_id = _manual(client, started_at=today).json()["id"]
    assert [r["id"] for r in client.get("/runs", headers=auth(ALICE)).json()] == [run_id]
    assert client.get("/training-load?days=7", headers=auth(ALICE)).json()[-1]["load_min"] == 27.5
    assert client.get(f"/runs/{run_id}", headers=auth(BOB)).status_code == 404

    assert client.post(f"/runs/{run_id}/reprocess", headers=auth(ALICE)).status_code == 409
    assert client.post("/runs/reprocess-all", headers=auth(ALICE)).json() == {
        "reprocessed": 0,
        "failed": 0,
    }
    assert client.delete(f"/runs/{run_id}", headers=auth(ALICE)).status_code == 204
    assert client.get("/runs", headers=auth(ALICE)).json() == []


def test_manual_races_count_for_prediction(client):
    _manual(client, distance_km=5, duration_s=1200, started_at="2026-09-01T07:00:00Z", is_race=True)
    _manual(
        client, distance_km=10, duration_s=2520, started_at="2026-09-08T07:00:00Z", is_race=True
    )
    _manual(client, distance_km=8, duration_s=3000, started_at="2026-09-10T07:00:00Z")  # easy
    body = client.get("/predictions", headers=auth(ALICE)).json()
    assert body["envelope_size"] == 2  # the two races; the easy run isn't an effort


def test_two_manual_runs_do_not_clash_as_duplicates(client):
    assert _manual(client).status_code == 201
    assert _manual(client).status_code == 201
