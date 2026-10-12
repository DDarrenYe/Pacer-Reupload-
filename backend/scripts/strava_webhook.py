"""Register (or show) the Strava webhook, so Pacer hears when someone revokes access.

    cd backend && python scripts/strava_webhook.py https://run-analytics-api.onrender.com

Reads STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET and STRAVA_WEBHOOK_VERIFY_TOKEN from
backend/.env. The API must be awake and deployed with the same verify token, because
Strava calls it to check the subscription. Strava allows one subscription per app.
"""

import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402

URL = "https://www.strava.com/api/v3/push_subscriptions"


def main() -> None:
    s = get_settings()
    if not (s.strava_client_id and s.strava_client_secret and s.strava_webhook_verify_token):
        sys.exit(
            "Set STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET and STRAVA_WEBHOOK_VERIFY_TOKEN first."
        )
    creds = {"client_id": s.strava_client_id, "client_secret": s.strava_client_secret}

    existing = httpx.get(URL, params=creds, timeout=30).json()
    if existing:
        print(f"Already subscribed: {existing}")
        return
    if len(sys.argv) < 2:
        sys.exit("Pass the API's base URL, e.g. https://run-analytics-api.onrender.com")
    callback = sys.argv[1].rstrip("/") + "/strava/webhook"
    r = httpx.post(
        URL,
        data={**creds, "callback_url": callback, "verify_token": s.strava_webhook_verify_token},
        timeout=60,
    )
    print(r.status_code, r.text)


if __name__ == "__main__":
    main()
