"""Supabase Auth admin calls (server side only, with the secret key)."""

import uuid
from typing import Annotated, Protocol

import httpx
from fastapi import Depends

from app.config import get_settings


class AdminError(RuntimeError):
    pass


class Admin(Protocol):
    def delete_user(self, user_id: uuid.UUID) -> None: ...


class SupabaseAdmin:
    def __init__(self, url: str, secret_key: str):
        self._base = f"{url.rstrip('/')}/auth/v1/admin/users"
        self._headers = {"Authorization": f"Bearer {secret_key}", "apikey": secret_key}

    def delete_user(self, user_id: uuid.UUID) -> None:
        try:
            r = httpx.delete(f"{self._base}/{user_id}", headers=self._headers, timeout=30)
        except httpx.HTTPError as exc:
            raise AdminError(f"Supabase unreachable: {exc}") from exc
        if r.is_error and r.status_code != 404:  # 404: already gone, which is the goal
            raise AdminError(f"Deleting the user failed ({r.status_code}): {r.text}")


def get_admin() -> Admin:
    s = get_settings()
    if not s.supabase_url or not s.supabase_secret_key:
        raise AdminError("SUPABASE_URL and SUPABASE_SECRET_KEY must be set.")
    return SupabaseAdmin(s.supabase_url, s.supabase_secret_key)


AdminDep = Annotated[Admin, Depends(get_admin)]
