"""Raw upload storage in a private Supabase Storage bucket."""

from typing import Annotated, Protocol

import httpx
from fastapi import Depends

from app.config import get_settings


class StorageError(RuntimeError):
    pass


class Storage(Protocol):
    def upload(self, key: str, content: bytes, content_type: str) -> None: ...

    def delete(self, key: str) -> None: ...


class SupabaseStorage:
    def __init__(self, url: str, secret_key: str, bucket: str):
        self._base = f"{url.rstrip('/')}/storage/v1/object/{bucket}"
        self._headers = {"Authorization": f"Bearer {secret_key}", "apikey": secret_key}

    def upload(self, key: str, content: bytes, content_type: str) -> None:
        try:
            r = httpx.post(
                f"{self._base}/{key}",
                content=content,
                headers={**self._headers, "Content-Type": content_type, "x-upsert": "true"},
                timeout=30,
            )
        except httpx.HTTPError as exc:
            raise StorageError(f"Storage unreachable: {exc}") from exc
        if r.is_error:
            raise StorageError(f"Storage upload failed ({r.status_code}): {r.text}")

    def delete(self, key: str) -> None:
        try:
            r = httpx.delete(f"{self._base}/{key}", headers=self._headers, timeout=30)
        except httpx.HTTPError as exc:
            raise StorageError(f"Storage unreachable: {exc}") from exc
        if r.is_error and r.status_code != 404:
            raise StorageError(f"Storage delete failed ({r.status_code}): {r.text}")


def get_storage() -> Storage:
    s = get_settings()
    if not s.supabase_url or not s.supabase_secret_key:
        raise StorageError("SUPABASE_URL and SUPABASE_SECRET_KEY must be set to store uploads.")
    return SupabaseStorage(s.supabase_url, s.supabase_secret_key, s.storage_bucket)


StorageDep = Annotated[Storage, Depends(get_storage)]
