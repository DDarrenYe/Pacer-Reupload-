import uuid

import pytest

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
