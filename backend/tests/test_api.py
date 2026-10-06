import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_parse_gpx(data_dir):
    with open(data_dir / "sample.gpx", "rb") as f:
        r = client.post("/uploads/parse", files={"file": ("run.gpx", f)})
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "gpx"
    assert body["distance_m"] == pytest.approx(3000, abs=1)
    assert body["moving_time_s"] == 900


def test_parse_csv(data_dir):
    with open(data_dir / "treadmill.csv", "rb") as f:
        r = client.post("/uploads/parse", files={"file": ("Treadmill.CSV", f)})
    assert r.status_code == 200
    assert r.json()["distance_m"] == 5000


def test_bad_file_returns_422(data_dir):
    with open(data_dir / "not_gpx.gpx", "rb") as f:
        r = client.post("/uploads/parse", files={"file": ("bad.gpx", f)})
    assert r.status_code == 422
    assert "valid GPX" in r.json()["detail"]


def test_unsupported_type_returns_415():
    r = client.post("/uploads/parse", files={"file": ("run.fit", b"\x00\x01")})
    assert r.status_code == 415
