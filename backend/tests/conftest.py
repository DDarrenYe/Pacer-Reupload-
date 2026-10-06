import os
import time
import uuid
from pathlib import Path

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.db import Base, get_db, normalize_url
from app.main import app
from app.storage import get_storage

DATA = Path(__file__).parent / "data"
JWT_SECRET = "test-secret-at-least-32-bytes-long!!"


@pytest.fixture
def data_dir() -> Path:
    return DATA


class FakeStorage:
    def __init__(self):
        self.files: dict[str, bytes] = {}

    def upload(self, key: str, content: bytes, content_type: str) -> None:
        self.files[key] = content

    def delete(self, key: str) -> None:
        self.files.pop(key, None)


@pytest.fixture(autouse=True)
def test_settings(monkeypatch):
    # Environment variables beat backend/.env, so tests never touch real Supabase.
    monkeypatch.setenv("SUPABASE_JWT_SECRET", JWT_SECRET)
    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def db_session_factory():
    # Set TEST_DATABASE_URL to run against Postgres; SQLite in memory by default.
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        engine = create_engine(normalize_url(url))
    else:
        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def storage() -> FakeStorage:
    return FakeStorage()


@pytest.fixture
def client(db_session_factory, storage):
    def override_db():
        with db_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_storage] = lambda: storage
    yield TestClient(app)
    app.dependency_overrides.clear()


def make_token(user_id: uuid.UUID, *, expires_in: int = 3600, aud: str = "authenticated") -> str:
    claims = {"sub": str(user_id), "aud": aud, "exp": int(time.time()) + expires_in}
    return jwt.encode(claims, JWT_SECRET, algorithm="HS256")


def auth(user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(user_id)}"}
