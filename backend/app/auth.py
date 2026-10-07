"""Verify access tokens and return the caller's user id.

Two kinds of token are accepted: Supabase access tokens for real users, and short-lived
read-only demo tokens that this API signs itself (see routes/demo.py).
"""

import uuid
from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings

bearer = HTTPBearer(auto_error=False, description="Supabase access token")

AUDIENCE = "authenticated"
DEMO_AUDIENCE = "pacer-demo"


@lru_cache
def _jwks_client(supabase_url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json")


def _decode(token: str) -> dict:
    s = get_settings()
    # Peek (unverified) at the audience only to pick the right key; it's verified below.
    if jwt.decode(token, options={"verify_signature": False}).get("aud") == DEMO_AUDIENCE:
        if not s.demo_token_secret:
            raise jwt.InvalidTokenError("Demo mode is off.")
        claims = jwt.decode(
            token, s.demo_token_secret, algorithms=["HS256"], audience=DEMO_AUDIENCE
        )
        if claims.get("sub") != s.demo_user_id:
            raise jwt.InvalidTokenError("Demo tokens are only for the demo user.")
        return claims
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


def is_demo_user(user_id: uuid.UUID) -> bool:
    return str(user_id) == get_settings().demo_user_id


def get_writable_user_id(user_id: CurrentUserId) -> uuid.UUID:
    """Like CurrentUserId, but the demo account (read-only) gets a 403."""
    if is_demo_user(user_id):
        raise HTTPException(403, "The demo account is read-only. Sign up to add your own runs.")
    return user_id


WritableUserId = Annotated[uuid.UUID, Depends(get_writable_user_id)]
