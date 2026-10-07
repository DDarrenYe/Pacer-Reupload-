import time

import jwt
from fastapi import APIRouter, HTTPException

from app.auth import DEMO_AUDIENCE
from app.config import get_settings

router = APIRouter(prefix="/demo", tags=["demo"])

DEMO_TOKEN_SECONDS = 2 * 3600


@router.post("/session")
def create_demo_session() -> dict:
    """A short-lived, read-only token for the demo account (sample runs, no sign-up).

    Signed by this API rather than Supabase, so there's no shared password anyone could
    change, and every write route refuses it.
    """
    s = get_settings()
    if not s.demo_token_secret:
        raise HTTPException(404, "The demo isn't available right now.")
    now = int(time.time())
    token = jwt.encode(
        {"sub": s.demo_user_id, "aud": DEMO_AUDIENCE, "iat": now, "exp": now + DEMO_TOKEN_SECONDS},
        s.demo_token_secret,
        algorithm="HS256",
    )
    return {"access_token": token, "expires_in": DEMO_TOKEN_SECONDS}
