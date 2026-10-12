import time
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

from app.analytics.data import load_efforts, load_volumes
from app.config import get_settings
from app.main import app
from app.models import Run, StravaConnection
from app.parsing.gpx_parser import parse_gpx, summarize_track
from app.strava import StravaClient, get_optional_strava, get_strava, streams_to_gpx
from tests.conftest import auth

ALICE = uuid.uuid4()
BOB = uuid.uuid4()
ATHLETE = 4242
START = datetime.now(UTC).replace(microsecond=0) - timedelta(days=3)


def gps_streams(km=5.0, pace_s=300, step_s=2):
    """A straight run north at a steady pace, recorded every `step_s` seconds."""
    speed = 1000 / pace_s
    n = int(km * pace_s / step_s) + 1
    times = [i * step_s for i in range(n)]
    return {
        "time": times,
        "latlng": [[51.5 + speed * t / 111_195, -0.12] for t in times],
        "altitude": [20.0 + (i % 10) * 0.1 for i in range(n)],
        "heartrate": [150] * n,
    }


def activity(id, *, start=START, kind="Run", km=5.0, gps=True, race=False, name=None):
    return {
        "id": id,
        "name": name or f"Activity {id}",
        "sport_type": kind,
        "start_date": start.isoformat().replace("+00:00", "Z"),
        "distance": km * 1000,
        "moving_time": km * 300,
        "elapsed_time": km * 300 + 20,
        "start_latlng": [51.5, -0.12] if gps else [],
        "trainer": not gps,
        "workout_type": 1 if race else 0,
        "average_heartrate": 148.0,
    }


class FakeStrava:
    """Just enough of Strava's API, tracking what was asked of it."""

    def __init__(self):
        self.activities: list[dict] = []
        self.streams: dict[int, dict] = {}
        self.calls: list[str] = []
        self.revoked = False
        self.rate_limited = False
        self.deauthorized: list[str] = []
        self.expires_in = 6 * 3600
        self.token_no = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.calls.append(path)
        if self.rate_limited:
            return httpx.Response(429, json={"message": "Rate Limit Exceeded"})
        if path == "/oauth/token":
            form = dict(x.split("=", 1) for x in request.content.decode().split("&"))
            if form["grant_type"] == "refresh_token" and self.revoked:
                return httpx.Response(400, json={"message": "Bad Request"})
            if form.get("code") == "bad":
                return httpx.Response(400, json={"message": "Bad Request"})
            self.token_no += 1
            return httpx.Response(
                200,
                json={
                    "access_token": f"access-{self.token_no}",
                    "refresh_token": f"refresh-{self.token_no}",
                    "expires_at": int(time.time()) + self.expires_in,
                    "athlete": {"id": ATHLETE, "firstname": "Darren", "lastname": "Y"},
                },
            )
        if path == "/oauth/deauthorize":
            self.deauthorized.append(request.content.decode())
            return httpx.Response(200, json={})
        if self.revoked:
            return httpx.Response(401, json={"message": "Authorization Error"})
        if path == "/api/v3/athlete/activities":
            after = int(request.url.params["after"])
            per_page = int(request.url.params["per_page"])
            newer = [
                a
                for a in self.activities
                if datetime.fromisoformat(a["start_date"].replace("Z", "+00:00")).timestamp()
                > after
            ]
            newer.sort(key=lambda a: a["start_date"])
            return httpx.Response(200, json=newer[:per_page])
        if path.startswith("/api/v3/activities/") and path.endswith("/streams"):
            activity_id = int(path.split("/")[4])
            streams = self.streams.get(activity_id, {})
            return httpx.Response(200, json={k: {"data": v} for k, v in streams.items()})
        return httpx.Response(404)


@pytest.fixture(autouse=True)
def strava_settings(monkeypatch):
    monkeypatch.setenv("STRAVA_CLIENT_ID", "123")
    monkeypatch.setenv("STRAVA_CLIENT_SECRET", "shh")
    monkeypatch.setenv("STRAVA_TOKEN_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("STRAVA_WEBHOOK_VERIFY_TOKEN", "verify-me")
    get_settings.cache_clear()


@pytest.fixture
def fake(client) -> FakeStrava:
    fake = FakeStrava()
    http = httpx.Client(transport=httpx.MockTransport(fake.handler))
    client_ = StravaClient("123", "shh", http)
    app.dependency_overrides[get_strava] = lambda: client_
    app.dependency_overrides[get_optional_strava] = lambda: client_
    return fake


def connect(client, user=ALICE, scope="read,activity:read_all"):
    return client.post("/strava/connect", json={"code": "ok", "scope": scope}, headers=auth(user))


def sync(client, user=ALICE):
    return client.post("/strava/sync", headers=auth(user))


def runs(client, user=ALICE):
    return client.get("/runs", headers=auth(user)).json()


def test_streams_to_gpx_round_trips_through_the_parser():
    gpx = streams_to_gpx(START, gps_streams(km=5), name="Tempo & <hills>")
    summary = summarize_track(parse_gpx(gpx))
    assert summary.distance_m == pytest.approx(5000, rel=0.01)
    assert summary.moving_time_s == pytest.approx(1500, abs=4)
    assert summary.avg_hr == 150
    assert summary.start_time == START


def test_status_when_not_connected_and_when_switched_off(client, fake, monkeypatch):
    body = client.get("/strava", headers=auth(ALICE)).json()
    assert body == {
        "enabled": True,
        "client_id": "123",
        "connected": False,
        "athlete_name": None,
        "last_synced_at": None,
    }
    monkeypatch.setenv("STRAVA_TOKEN_KEY", "")
    get_settings.cache_clear()
    app.dependency_overrides.pop(get_strava)
    app.dependency_overrides.pop(get_optional_strava)
    assert client.get("/strava", headers=auth(ALICE)).json()["enabled"] is False
    assert sync(client).status_code == 404


def test_connect_stores_encrypted_tokens(client, fake, db_session_factory):
    r = connect(client)
    assert r.status_code == 200 and r.json()["athlete_name"] == "Darren Y"
    with db_session_factory() as db:
        conn = db.scalar(select(StravaConnection))
    assert conn.athlete_id == ATHLETE and conn.user_id == ALICE
    assert "access-1" not in conn.access_token and "refresh-1" not in conn.refresh_token
    status = client.get("/strava", headers=auth(ALICE)).json()
    assert status["connected"] is True and status["athlete_name"] == "Darren Y"


def test_connect_needs_activity_scope_and_a_free_athlete(client, fake):
    assert connect(client, scope="read").status_code == 400
    assert connect(client).status_code == 200
    assert connect(client).status_code == 200  # reconnecting yourself is fine
    assert connect(client, user=BOB).status_code == 409


def test_connect_reports_strava_errors(client, fake):
    r = client.post(
        "/strava/connect", json={"code": "bad", "scope": "activity:read_all"}, headers=auth(ALICE)
    )
    assert r.status_code == 502


def test_sync_imports_gps_and_treadmill_runs(client, fake):
    fake.activities = [
        activity(1, start=START, race=True, name="Parkrun"),
        activity(2, start=START + timedelta(days=1), gps=False, km=8, name="Treadmill"),
        activity(3, start=START + timedelta(days=2), kind="Ride"),
    ]
    fake.streams[1] = gps_streams()
    connect(client)
    r = sync(client)
    assert r.json() == {"imported": 2, "skipped": 1, "more": False}

    by_name = {run["name"]: run for run in runs(client)}
    parkrun, treadmill = by_name["Parkrun"], by_name["Treadmill"]
    assert parkrun["strava_activity_id"] == 1 and parkrun["is_race"]
    assert parkrun["source"] == "gpx" and parkrun["split_type"] == "even"
    detail = client.get(f"/runs/{parkrun['id']}", headers=auth(ALICE)).json()
    assert len(detail["splits"]) == 5
    assert treadmill["surface"] == "treadmill" and treadmill["source"] == "manual"
    assert treadmill["avg_pace_s_per_km"] == 300

    # Nothing new: a second sync imports nothing and asks Strava only for the list.
    fake.calls.clear()
    assert sync(client).json() == {"imported": 0, "skipped": 0, "more": False}
    assert fake.calls == ["/api/v3/athlete/activities"]


def test_sync_skips_runs_already_uploaded_by_hand(client, fake, data_dir):
    with open(data_dir / "sample.gpx", "rb") as f:
        uploaded = client.post(
            "/runs", files={"file": ("sample.gpx", f)}, headers=auth(ALICE)
        ).json()
    started = datetime.fromisoformat(uploaded["started_at"])
    fake.activities = [activity(7, start=started, km=uploaded["distance_m"] / 1000)]
    connect(client)
    assert sync(client).json()["skipped"] == 1
    assert len(runs(client)) == 1


def test_sync_in_batches(client, fake, monkeypatch):
    monkeypatch.setattr("app.routes.strava.SYNC_BATCH", 2)
    fake.activities = [
        activity(i, start=START + timedelta(hours=i), gps=False) for i in range(1, 4)
    ]
    connect(client)
    assert sync(client).json() == {"imported": 2, "skipped": 0, "more": True}
    assert sync(client).json() == {"imported": 1, "skipped": 0, "more": False}


def test_sync_skips_tracks_that_cannot_be_parsed(client, fake):
    fake.activities = [activity(5)]
    fake.streams[5] = {"time": [0], "latlng": [[51.5, -0.12]]}  # one point: no track
    connect(client)
    assert sync(client).json() == {"imported": 0, "skipped": 1, "more": False}


def test_expired_token_is_refreshed(client, fake):
    fake.expires_in = 0
    connect(client)
    fake.activities = [activity(1, gps=False)]
    assert sync(client).json()["imported"] == 1
    assert fake.calls.count("/oauth/token") == 2  # the connect, then a refresh


def test_rate_limit_is_explained(client, fake):
    connect(client)
    fake.rate_limited = True
    r = sync(client)
    assert r.status_code == 503 and "rate limit" in r.json()["detail"]


def test_revoked_access_removes_strava_runs(client, fake):
    fake.activities = [activity(1, gps=False)]
    connect(client)
    sync(client)
    fake.revoked = True
    r = sync(client)
    assert r.status_code == 409 and "revoked" in r.json()["detail"]
    assert runs(client) == []
    assert client.get("/strava", headers=auth(ALICE)).json()["connected"] is False


def test_disconnect_deletes_strava_runs_and_files(client, fake, storage, data_dir):
    with open(data_dir / "sample.gpx", "rb") as f:
        client.post("/runs", files={"file": ("mine.gpx", f)}, headers=auth(ALICE))
    fake.activities = [activity(1, start=START - timedelta(days=30))]
    fake.streams[1] = gps_streams()
    connect(client)
    sync(client)
    assert len(runs(client)) == 2 and len(storage.files) == 2

    assert client.delete("/strava", headers=auth(ALICE)).status_code == 204
    assert [r["name"] for r in runs(client)] == ["mine.gpx"]  # your own upload stays
    assert len(storage.files) == 1
    assert fake.deauthorized and "access_token=access-1" in fake.deauthorized[0]
    assert client.get("/strava", headers=auth(ALICE)).json()["connected"] is False


def test_sync_needs_a_connection(client, fake):
    assert sync(client).status_code == 409


def test_demo_cannot_connect_or_sync(client, fake):
    token = client.post("/demo/session").json()["access_token"]
    demo = {"Authorization": f"Bearer {token}"}
    assert client.get("/strava", headers=demo).json()["enabled"] is False
    r = client.post(
        "/strava/connect", json={"code": "ok", "scope": "activity:read_all"}, headers=demo
    )
    assert r.status_code == 403
    assert client.post("/strava/sync", headers=demo).status_code == 403


def test_webhook_verification(client):
    params = {"hub.mode": "subscribe", "hub.verify_token": "verify-me", "hub.challenge": "abc"}
    assert client.get("/strava/webhook", params=params).json() == {"hub.challenge": "abc"}
    params["hub.verify_token"] = "wrong"
    assert client.get("/strava/webhook", params=params).status_code == 403


def revocation(owner=ATHLETE):
    return {
        "object_type": "athlete",
        "object_id": owner,
        "aspect_type": "update",
        "owner_id": owner,
        "updates": {"authorized": "false"},
    }


def test_webhook_revocation_is_checked_before_deleting(client, fake):
    fake.activities = [activity(1, gps=False)]
    connect(client)
    sync(client)

    # A forged event: the refresh token still works, so nothing is deleted.
    assert client.post("/strava/webhook", json=revocation()).json() == {"ok": True}
    assert len(runs(client)) == 1

    fake.revoked = True
    client.post("/strava/webhook", json=revocation())
    assert runs(client) == []
    assert client.get("/strava", headers=auth(ALICE)).json()["connected"] is False


def test_webhook_ignores_other_events(client, fake):
    assert client.post("/strava/webhook", json={"object_type": "activity"}).json() == {"ok": True}
    assert client.post("/strava/webhook", json=revocation(owner=999)).json() == {"ok": True}


def test_strava_runs_stay_out_of_pooled_data(client, fake, db_session_factory):
    fake.activities = [activity(1, race=True)]
    fake.streams[1] = gps_streams()
    connect(client)
    sync(client)
    with db_session_factory() as db:
        assert load_efforts(db) == [] and load_volumes(db) == []
        assert len(load_efforts(db, ALICE)) > 0  # still yours, for your own predictions


def test_account_deletion_revokes_strava(client, fake, db_session_factory):
    connect(client)
    assert client.delete("/account", headers=auth(ALICE)).status_code == 204
    assert fake.deauthorized
    with db_session_factory() as db:
        assert db.scalar(select(StravaConnection)) is None
        assert db.scalar(select(Run)) is None
