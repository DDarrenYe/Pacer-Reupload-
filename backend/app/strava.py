"""Talking to Strava: OAuth tokens, activities and streams, plus turning streams into GPX.

Strava's API has no GPX download for activities, only the raw recorded streams (time,
position, altitude, heart rate). Rebuilding a GPX from them lets imported runs go
through exactly the same parser and analytics as uploaded files.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Annotated, Any
from xml.sax.saxutils import escape

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends, HTTPException

from app.config import get_settings
from app.models import StravaConnection

logger = logging.getLogger(__name__)

# Read access to all activities, including private ones and their streams.
REQUIRED_SCOPE = "activity:read_all"
RUN_TYPES = {"Run", "TrailRun", "VirtualRun"}
# Strava's workout_type for a run marked as a race.
RACE_WORKOUT_TYPE = 1
STREAM_KEYS = "time,latlng,altitude,heartrate"


class StravaError(RuntimeError):
    """Strava couldn't be reached or returned an error."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class StravaRateLimited(StravaError):
    pass


class StravaRevoked(StravaError):
    """The athlete has revoked access (or the token is otherwise no longer valid)."""


class StravaClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        http: httpx.Client | None = None,
        base_url: str = "https://www.strava.com",
    ):
        self.client_id = client_id
        self._secret = client_secret
        self._http = http or httpx.Client(timeout=30)
        self._api = f"{base_url.rstrip('/')}/api/v3"
        self._oauth = f"{base_url.rstrip('/')}/oauth"

    # OAuth
    def exchange_code(self, code: str) -> dict:
        return self._token({"grant_type": "authorization_code", "code": code})

    def refresh(self, refresh_token: str) -> dict:
        try:
            return self._token({"grant_type": "refresh_token", "refresh_token": refresh_token})
        except StravaError as exc:
            # A refresh token Strava rejects means the athlete revoked access.
            if exc.status == 400:
                raise StravaRevoked("Strava rejected the refresh token", 400) from exc
            raise

    def deauthorize(self, access_token: str) -> None:
        self._call("POST", f"{self._oauth}/deauthorize", data={"access_token": access_token})

    # Data
    def activities(self, access_token: str, after: int, per_page: int) -> list[dict]:
        """Activities that started after `after` (Unix seconds), oldest first."""
        return self._call(
            "GET",
            f"{self._api}/athlete/activities",
            token=access_token,
            params={"after": after, "per_page": per_page, "page": 1},
        )

    def streams(self, access_token: str, activity_id: int) -> dict[str, list]:
        body = self._call(
            "GET",
            f"{self._api}/activities/{activity_id}/streams",
            token=access_token,
            params={"keys": STREAM_KEYS, "key_by_type": "true"},
        )
        return {key: value.get("data", []) for key, value in body.items()}

    def _token(self, data: dict) -> dict:
        data = {**data, "client_id": self.client_id, "client_secret": self._secret}
        return self._call("POST", f"{self._oauth}/token", data=data)

    def _call(self, method: str, url: str, token: str | None = None, **kwargs) -> Any:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        try:
            r = self._http.request(method, url, headers=headers, **kwargs)
        except httpx.HTTPError as exc:
            raise StravaError(f"Strava unreachable: {exc}") from exc
        if r.status_code == 429:
            raise StravaRateLimited("Strava rate limit reached", 429)
        if r.status_code == 401:
            raise StravaRevoked("Strava refused the token", 401)
        if r.is_error:
            raise StravaError(
                f"Strava request failed ({r.status_code}): {r.text[:200]}", r.status_code
            )
        return r.json() if r.content else None


def get_strava() -> StravaClient:
    s = get_settings()
    if not s.strava_enabled:
        raise HTTPException(404, "Strava import isn't set up on this server.")
    return StravaClient(s.strava_client_id, s.strava_client_secret, base_url=s.strava_base_url)


def get_optional_strava() -> StravaClient | None:
    return get_strava() if get_settings().strava_enabled else None


StravaDep = Annotated[StravaClient, Depends(get_strava)]
OptionalStravaDep = Annotated[StravaClient | None, Depends(get_optional_strava)]


# Tokens at rest
def _fernet() -> Fernet:
    return Fernet(get_settings().strava_token_key.encode())


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as exc:  # the key was changed: the stored tokens are unusable
        raise StravaRevoked("Stored Strava token can't be decrypted") from exc


def expired(expires_at: int, margin_s: int = 60) -> bool:
    return expires_at <= time.time() + margin_s


def deauthorize_quietly(conn: StravaConnection, strava: StravaClient) -> None:
    """Tell Strava to revoke our access. Failing is fine: the data goes regardless."""
    try:
        strava.deauthorize(decrypt(conn.access_token))
    except StravaError as exc:
        logger.warning("Strava deauthorize failed for athlete %s: %s", conn.athlete_id, exc)


# Streams -> GPX
def is_run(activity: dict) -> bool:
    return (activity.get("sport_type") or activity.get("type")) in RUN_TYPES


def has_gps(activity: dict) -> bool:
    return bool(activity.get("start_latlng")) and not activity.get("trainer")


def start_time(activity: dict) -> datetime:
    return datetime.fromisoformat(activity["start_date"].replace("Z", "+00:00"))


def streams_to_gpx(start: datetime, streams: dict[str, list], name: str = "") -> bytes:
    """Build a GPX track from Strava streams, with heart rate as a Garmin extension."""
    times, latlng = streams.get("time", []), streams.get("latlng", [])
    altitude, heartrate = streams.get("altitude", []), streams.get("heartrate", [])
    points = []
    for i, (t, ll) in enumerate(zip(times, latlng, strict=False)):
        stamp = (start + timedelta(seconds=t)).strftime("%Y-%m-%dT%H:%M:%SZ")
        ele = f"<ele>{altitude[i]:.1f}</ele>" if i < len(altitude) else ""
        hr = (
            "<extensions><gpxtpx:TrackPointExtension>"
            f"<gpxtpx:hr>{int(heartrate[i])}</gpxtpx:hr>"
            "</gpxtpx:TrackPointExtension></extensions>"
            if i < len(heartrate)
            else ""
        )
        points.append(
            f'<trkpt lat="{ll[0]:.7f}" lon="{ll[1]:.7f}">{ele}<time>{stamp}</time>{hr}</trkpt>'
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<gpx version="1.1" creator="Pacer (from Strava)" '
        'xmlns="http://www.topografix.com/GPX/1/1" '
        'xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1">\n'
        f"<trk><name>{escape(name)}</name><trkseg>\n"
        + "\n".join(points)
        + "\n</trkseg></trk>\n</gpx>\n"
    ).encode()
