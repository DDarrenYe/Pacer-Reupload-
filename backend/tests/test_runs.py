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
