import time
import uuid

import jwt
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from tests.conftest import DEMO_SECRET, auth

ALICE = uuid.uuid4()
BOB = uuid.uuid4()


def demo_headers(client) -> dict[str, str]:
    r = client.post("/demo/session")
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def manual(client, headers, **overrides):
    body = {"distance_km": 5, "duration_s": 1500, "started_at": "2026-10-01T07:00:00Z"}
    return client.post("/runs/manual", json={**body, **overrides}, headers=headers)


# --- demo account -----------------------------------------------------------------


def test_demo_can_read(client):
    h = demo_headers(client)
    assert client.get("/runs", headers=h).status_code == 200
    assert client.get("/trends", headers=h).status_code == 200
    assert client.get("/predictions", headers=h).status_code == 200
    assert client.get("/account", headers=h).json() == {"run_count": 0, "is_demo": True}


def test_demo_cannot_write(client, data_dir):
    h = demo_headers(client)
    some_id = uuid.uuid4()
    with open(data_dir / "sample.gpx", "rb") as f:
        assert client.post("/runs", files={"file": ("a.gpx", f)}, headers=h).status_code == 403
    assert manual(client, h).status_code == 403
    body = {"distance_km": 5, "duration_s": 1500, "started_at": "2026-10-01T07:00:00Z"}
    assert client.put(f"/runs/{some_id}/manual", json=body, headers=h).status_code == 403
    assert client.post(f"/runs/{some_id}/reprocess", headers=h).status_code == 403
    assert client.post("/runs/reprocess-all", headers=h).status_code == 403
    assert client.delete(f"/runs/{some_id}", headers=h).status_code == 403
    r = client.delete("/account", headers=h)
    assert r.status_code == 403
    assert "read-only" in r.json()["detail"]


def test_demo_tokens_must_be_genuine(client):
    claims = {"sub": get_settings().demo_user_id, "aud": "pacer-demo", "exp": int(time.time()) + 60}
    forged = jwt.encode(claims, "not-the-secret-but-32-bytes-long!!", algorithm="HS256")
    expired = jwt.encode({**claims, "exp": int(time.time()) - 10}, DEMO_SECRET, algorithm="HS256")
    other_user = jwt.encode({**claims, "sub": str(ALICE)}, DEMO_SECRET, algorithm="HS256")
    for token in (forged, expired, other_user):
        r = client.get("/runs", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401


def test_demo_off_without_secret(client, monkeypatch):
    monkeypatch.setenv("DEMO_TOKEN_SECRET", "")
    get_settings.cache_clear()
    assert client.post("/demo/session").status_code == 404


def test_demo_runs_never_shape_real_predictions(client, db_session_factory):
    from app.analytics.data import load_efforts, load_volumes
    from app.models import Run

    demo_id = uuid.UUID(get_settings().demo_user_id)
    with db_session_factory() as db:
        for uid in (demo_id, ALICE):
            db.add(
                Run(
                    user_id=uid,
                    started_at=__import__("datetime").datetime(2026, 9, 1),
                    source="manual",
                    surface="road",
                    distance_m=5000,
                    elapsed_s=1200,
                    moving_time_s=1200,
                    avg_pace_s_per_km=240,
                    is_race=True,
                )
            )
        db.commit()
        assert {e.user_id for e in load_efforts(db)} == {str(ALICE)}
        assert {v.user_id for v in load_volumes(db)} == {str(ALICE)}
        # ...but the demo still sees its own data
        assert len(load_efforts(db, demo_id)) == 1


# --- account deletion -------------------------------------------------------------


def test_delete_account_removes_everything_of_yours_only(client, data_dir, storage, admin):
    from tests.test_runs import upload

    upload(client, data_dir, user=ALICE)
    manual(client, auth(ALICE))
    client.post("/feedback", json={"message": "love it"}, headers=auth(ALICE))
    upload(client, data_dir, user=BOB)
    assert len(storage.files) == 2

    assert client.get("/account", headers=auth(ALICE)).json() == {"run_count": 2, "is_demo": False}
    assert client.delete("/account", headers=auth(ALICE)).status_code == 204

    assert admin.deleted == [ALICE]
    assert client.get("/runs", headers=auth(ALICE)).json() == []
    assert [k.split("/")[0] for k in storage.files] == [str(BOB)]
    assert len(client.get("/runs", headers=auth(BOB)).json()) == 1


def test_delete_account_reports_login_removal_failure(client, admin):
    from app.supabase_admin import AdminError

    def boom(user_id):
        raise AdminError("down")

    admin.delete_user = boom
    manual(client, auth(ALICE))
    r = client.delete("/account", headers=auth(ALICE))
    assert r.status_code == 502
    assert client.get("/runs", headers=auth(ALICE)).json() == []  # data still gone


# --- feedback -----------------------------------------------------------------------


def test_feedback(client, db_session_factory):
    from app.models import Feedback

    r = client.post(
        "/feedback",
        json={"message": "  Splits look great  ", "page": "/runs/x"},
        headers=auth(ALICE),
    )
    assert r.status_code == 201
    assert (
        client.post(
            "/feedback", json={"message": "from the demo"}, headers=demo_headers(client)
        ).status_code
        == 201
    )
    with db_session_factory() as db:
        rows = db.query(Feedback).order_by(Feedback.created_at).all()
        assert [(f.message, f.page) for f in rows][0] == ("Splits look great", "/runs/x")
        assert len(rows) == 2


@pytest.mark.parametrize("message", ["", "   ", "x" * 2001])
def test_feedback_validation(client, message):
    assert (
        client.post("/feedback", json={"message": message}, headers=auth(ALICE)).status_code == 422
    )


def test_feedback_needs_login(client):
    assert client.post("/feedback", json={"message": "hi"}).status_code == 401


# --- errors ---------------------------------------------------------------------------


def test_unexpected_errors_hide_internals():
    @app.get("/__boom")
    def boom():
        raise RuntimeError("secret internal detail")

    try:
        r = TestClient(app, raise_server_exceptions=False).get("/__boom")
        assert r.status_code == 500
        assert r.json() == {"detail": "Something went wrong on our side."}
        assert "secret" not in r.text
    finally:
        app.router.routes = [rt for rt in app.router.routes if getattr(rt, "path", "") != "/__boom"]
