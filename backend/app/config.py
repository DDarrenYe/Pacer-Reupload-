from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Read from environment variables, or backend/.env when running locally."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./local.db"
    supabase_url: str = ""
    # Publishable ("anon") key. Safe to expose; only used by scripts/get_token.py for now.
    supabase_publishable_key: str = ""
    # Service-role ("secret") key. Server only: never send it to the browser.
    supabase_secret_key: str = ""
    # Only for older Supabase projects that sign tokens with a shared HS256 secret.
    # Newer projects use asymmetric keys, which are fetched from the JWKS endpoint.
    supabase_jwt_secret: str = ""
    storage_bucket: str = "raw-uploads"


@lru_cache
def get_settings() -> Settings:
    return Settings()
