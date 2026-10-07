"""Log in as a Supabase user and print an access token for testing the API.

    cd backend && python scripts/get_token.py

Paste the token into /docs -> Authorize. Tokens expire after about an hour.
This stands in for the login page until the front end exists (Week 4).
"""

import getpass
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402


def main() -> None:
    s = get_settings()
    if not s.supabase_url or not s.supabase_publishable_key:
        sys.exit("Set SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY in backend/.env first.")

    email = input("Email: ").strip()
    password = getpass.getpass("Password: ")
    r = httpx.post(
        f"{s.supabase_url.rstrip('/')}/auth/v1/token",
        params={"grant_type": "password"},
        headers={"apikey": s.supabase_publishable_key},
        json={"email": email, "password": password},
        timeout=30,
    )
    if r.is_error:
        sys.exit(f"Login failed ({r.status_code}): {r.text}")
    try:
        print(r.json()["access_token"])
    except (ValueError, KeyError):
        sys.exit(
            f"Unexpected response ({r.status_code}): {r.text[:300]}\n"
            "Check that SUPABASE_URL in .env is just https://<project>.supabase.co"
        )


if __name__ == "__main__":
    main()
