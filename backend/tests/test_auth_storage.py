import time
import uuid

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app import auth
from app.config import Settings, get_settings
from app.storage import StorageError, SupabaseStorage, get_storage


def test_asymmetric_supabase_token(monkeypatch):
    """Newer Supabase projects sign with ES256; the public key comes from JWKS."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    user = uuid.uuid4()
    token = jwt.encode(
        {"sub": str(user), "aud": "authenticated", "exp": int(time.time()) + 60},
        private_key,
        algorithm="ES256",
    )

    class FakeJwks:
        def get_signing_key_from_jwt(self, _token):
            return jwt.PyJWK.from_dict(
                jwt.algorithms.ECAlgorithm.to_jwk(private_key.public_key(), as_dict=True)
            )

    monkeypatch.setenv("SUPABASE_JWT_SECRET", "")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    get_settings.cache_clear()
    monkeypatch.setattr(auth, "_jwks_client", lambda url: FakeJwks())

    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    assert auth.get_current_user_id(creds) == user

    other_key = ec.generate_private_key(ec.SECP256R1())
    forged = jwt.encode(
        {"sub": str(user), "aud": "authenticated", "exp": int(time.time()) + 60},
        other_key,
        algorithm="ES256",
    )
    with pytest.raises(HTTPException) as exc:
        auth.get_current_user_id(HTTPAuthorizationCredentials(scheme="Bearer", credentials=forged))
    assert exc.value.status_code == 401


def test_storage_requests(monkeypatch):
    calls = []

    def fake(method):
        def send(url, **kwargs):
            calls.append((method, url, kwargs["headers"]))
            return httpx.Response(200, request=httpx.Request(method, url))

        return send

    monkeypatch.setattr(httpx, "post", fake("POST"))
    monkeypatch.setattr(httpx, "get", fake("GET"))
    monkeypatch.setattr(httpx, "delete", fake("DELETE"))

    s = SupabaseStorage("https://abc.supabase.co/", "secret", "raw-uploads")
    s.upload("user/hash.gpx", b"data", "application/gpx+xml")
    s.download("user/hash.gpx")
    s.delete("user/hash.gpx")

    url = "https://abc.supabase.co/storage/v1/object/raw-uploads/user/hash.gpx"
    assert [(m, u) for m, u, _ in calls] == [("POST", url), ("GET", url), ("DELETE", url)]
    assert calls[0][2]["Authorization"] == "Bearer secret"


def test_storage_error_on_failure(monkeypatch):
    monkeypatch.setattr(
        httpx, "post", lambda url, **kw: httpx.Response(400, request=httpx.Request("POST", url))
    )
    with pytest.raises(StorageError):
        SupabaseStorage("https://abc.supabase.co", "k", "b").upload("k", b"", "text/csv")


def test_storage_unreachable():
    # Nothing listens on port 9, so the connection is refused.
    with pytest.raises(StorageError, match="unreachable"):
        SupabaseStorage("http://127.0.0.1:9", "k", "b").upload("k", b"", "text/csv")


def test_storage_not_configured():
    with pytest.raises(StorageError):
        get_storage()


@pytest.mark.parametrize(
    "pasted",
    [
        "https://abc.supabase.co",
        "https://abc.supabase.co/",
        "https://abc.supabase.co/rest/v1",
        "https://abc.supabase.co/rest/v1/",
        "  https://abc.supabase.co/rest/v1/  ",
    ],
)
def test_supabase_url_is_normalised(pasted):
    assert Settings(supabase_url=pasted).supabase_url == "https://abc.supabase.co"


def test_admin_delete_user_request(monkeypatch):
    from app.supabase_admin import SupabaseAdmin

    calls = []

    def fake_delete(url, **kwargs):
        calls.append((url, kwargs["headers"]["apikey"]))
        return httpx.Response(200, request=httpx.Request("DELETE", url))

    monkeypatch.setattr(httpx, "delete", fake_delete)
    uid = uuid.uuid4()
    SupabaseAdmin("https://abc.supabase.co/", "secret").delete_user(uid)
    assert calls == [(f"https://abc.supabase.co/auth/v1/admin/users/{uid}", "secret")]


@pytest.mark.parametrize("status", [404, 500])
def test_admin_delete_user_errors(monkeypatch, status):
    from app.supabase_admin import AdminError, SupabaseAdmin

    monkeypatch.setattr(
        httpx,
        "delete",
        lambda url, **kw: httpx.Response(status, request=httpx.Request("DELETE", url)),
    )
    admin = SupabaseAdmin("https://abc.supabase.co", "k")
    if status == 404:
        admin.delete_user(uuid.uuid4())  # already gone is fine
    else:
        with pytest.raises(AdminError):
            admin.delete_user(uuid.uuid4())


def test_admin_not_configured():
    from app.supabase_admin import AdminError, get_admin

    with pytest.raises(AdminError):
        get_admin()
