"""Verify Supabase access tokens and return the caller's user id."""

import uuid
from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings

bearer = HTTPBearer(auto_error=False, description="Supabase access token")

AUDIENCE = "authenticated"


@lru_cache
def _jwks_client(supabase_url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json")


def _decode(token: str) -> dict:
    s = get_settings()
    if s.supabase_jwt_secret:
        return jwt.decode(token, s.supabase_jwt_secret, algorithms=["HS256"], audience=AUDIENCE)
    if not s.supabase_url:
        raise HTTPException(503, "Auth isn't configured (SUPABASE_URL is missing).")
    key = _jwks_client(s.supabase_url).get_signing_key_from_jwt(token)
    return jwt.decode(token, key.key, algorithms=["ES256", "RS256"], audience=AUDIENCE)


def get_current_user_id(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> uuid.UUID:
    if creds is None:
        raise HTTPException(401, "Log in first: missing bearer token.")
    try:
        claims = _decode(creds.credentials)
        return uuid.UUID(claims["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(401, "Invalid or expired token.") from exc


CurrentUserId = Annotated[uuid.UUID, Depends(get_current_user_id)]
