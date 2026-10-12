"""Connect a Strava account and import its runs.

The browser does the OAuth redirect and hands the code to POST /strava/connect with the
user's normal login, so the API never has to trust an unauthenticated redirect.
"""

import logging
import time
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.auth import CurrentUserId, WritableUserId, is_demo_user
from app.config import get_settings
from app.db import DbSession
from app.models import Run, StravaConnection
from app.routes.runs import save_file_run
from app.storage import Storage, StorageDep, StorageError
from app.strava import (
    RACE_WORKOUT_TYPE,
    REQUIRED_SCOPE,
    OptionalStravaDep,
    StravaClient,
    StravaDep,
    StravaError,
    StravaRateLimited,
    StravaRevoked,
    deauthorize_quietly,
    decrypt,
    encrypt,
    expired,
    has_gps,
    is_run,
    start_time,
    streams_to_gpx,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/strava", tags=["strava"])

# Activities handled per sync: one list call plus one streams call each keeps a sync
# well inside Strava's limit of about 100 requests per 15 minutes.
SYNC_BATCH = 30
# The first sync goes back as far as race predictions look.
FIRST_SYNC_DAYS = 180
# A run already uploaded by hand: same start (within a minute) and distance (within 3%).
SAME_START_S = 60
SAME_DISTANCE = 0.03


class ConnectIn(BaseModel):
    code: str = Field(min_length=1, max_length=200)
    scope: str = Field(default="", max_length=200)


@router.get("")
def strava_status(user_id: CurrentUserId, db: DbSession) -> dict:
    """Whether Strava import is available, and whether you've connected."""
    s = get_settings()
    conn = _connection(db, user_id)
    return {
        "enabled": s.strava_enabled and not is_demo_user(user_id),
        "client_id": s.strava_client_id or None,
        "connected": conn is not None,
        "athlete_name": conn.athlete_name if conn else None,
        "last_synced_at": conn.last_synced_at if conn else None,
    }


@router.post("/connect")
def connect(body: ConnectIn, user_id: WritableUserId, db: DbSession, strava: StravaDep) -> dict:
    """Swap the code from Strava's redirect for tokens and remember the connection."""
    if REQUIRED_SCOPE not in body.scope.split(","):
        raise HTTPException(
            400,
            "Pacer needs permission to read your activities. "
            "Connect again and keep that box ticked.",
        )
    try:
        tokens = strava.exchange_code(body.code)
    except StravaError as exc:
        raise _unavailable(exc) from exc
    athlete = tokens.get("athlete") or {}
    if not athlete.get("id"):
        raise HTTPException(502, "Strava didn't say which account you connected. Try again.")
    athlete_id = int(athlete["id"])
    taken = db.scalar(select(StravaConnection).where(StravaConnection.athlete_id == athlete_id))
    if taken and taken.user_id != user_id:
        raise HTTPException(
            409, "That Strava account is already connected to another Pacer account."
        )

    conn = _connection(db, user_id) or StravaConnection(
        user_id=user_id,
        sync_after=int((datetime.now(UTC) - timedelta(days=FIRST_SYNC_DAYS)).timestamp()),
    )
    conn.athlete_id = athlete_id
    name = " ".join(filter(None, [athlete.get("firstname"), athlete.get("lastname")]))
    conn.athlete_name = name or None
    conn.scope = body.scope
    _store_tokens(conn, tokens)
    db.add(conn)
    db.commit()
    return {"connected": True, "athlete_name": conn.athlete_name}


@router.post("/sync")
def sync(user_id: WritableUserId, db: DbSession, storage: StorageDep, strava: StravaDep) -> dict:
    """Import new runs from Strava, oldest first, up to 30 at a time."""
    conn = _connection(db, user_id)
    if conn is None:
        raise HTTPException(409, "Connect your Strava account first.")
    try:
        token = _access_token(db, conn, strava)
        activities = strava.activities(token, after=conn.sync_after, per_page=SYNC_BATCH)
        imported = skipped = 0
        for activity in activities:
            if _import(db, storage, strava, token, user_id, activity):
                imported += 1
            else:
                skipped += 1
            conn.sync_after = max(conn.sync_after, int(start_time(activity).timestamp()))
            db.commit()
    except StravaRevoked as exc:
        db.rollback()
        _remove(db, storage, user_id)
        raise HTTPException(
            409,
            "Strava access was revoked, so your Strava runs were removed. "
            "Connect again to re-import them.",
        ) from exc
    except StravaError as exc:
        db.rollback()
        raise _unavailable(exc) from exc
    conn.last_synced_at = datetime.now(UTC)
    db.commit()
    return {"imported": imported, "skipped": skipped, "more": len(activities) == SYNC_BATCH}


@router.delete("", status_code=204)
def disconnect(
    user_id: WritableUserId, db: DbSession, storage: StorageDep, strava: StravaDep
) -> Response:
    """Revoke Pacer's access on Strava and delete every run imported from it."""
    conn = _connection(db, user_id)
    if conn is not None:
        deauthorize_quietly(conn, strava)
    _remove(db, storage, user_id)
    return Response(status_code=204)


@router.get("/webhook")
def verify_webhook(
    mode: str = Query(alias="hub.mode"),
    token: str = Query(alias="hub.verify_token"),
    challenge: str = Query(alias="hub.challenge"),
) -> dict:
    """Strava calls this once when the webhook subscription is created."""
    expected = get_settings().strava_webhook_verify_token
    if mode != "subscribe" or not expected or token != expected:
        raise HTTPException(403, "Verification failed.")
    return {"hub.challenge": challenge}


@router.post("/webhook")
async def webhook(
    request: Request, db: DbSession, storage: StorageDep, strava: OptionalStravaDep
) -> dict:
    """Strava events. Only "athlete revoked access" matters: their data must then go.

    Strava doesn't sign webhook calls, so a revocation is checked before deleting
    anything: if the stored refresh token still works, the event was fake.
    """
    event = await request.json()
    revoked = (
        event.get("object_type") == "athlete"
        and str((event.get("updates") or {}).get("authorized")).lower() == "false"
    )
    if not revoked:
        return {"ok": True}
    conn = db.scalar(
        select(StravaConnection).where(StravaConnection.athlete_id == int(event["owner_id"]))
    )
    if conn is None or strava is None:
        return {"ok": True}
    try:
        strava.refresh(decrypt(conn.refresh_token))
    except StravaRevoked:
        _remove(db, storage, conn.user_id)
    except StravaError:
        logger.warning("Couldn't confirm a Strava revocation for athlete %s", conn.athlete_id)
    return {"ok": True}


def _import(
    db: Session,
    storage: Storage,
    strava: StravaClient,
    token: str,
    user_id,
    activity: dict,
) -> bool:
    """Save one Strava activity as a run. False if it was skipped."""
    activity_id = int(activity["id"])
    if not is_run(activity) or not activity.get("distance"):
        return False
    if db.scalar(
        select(Run.id).where(Run.user_id == user_id, Run.strava_activity_id == activity_id)
    ):
        return False
    if _already_uploaded(db, user_id, activity):
        return False
    started = start_time(activity)
    name = activity.get("name") or "Strava run"
    is_race = activity.get("workout_type") == RACE_WORKOUT_TYPE
    if not has_gps(activity):
        _save_without_gps(db, user_id, activity, started, name, is_race)
        return True
    streams = strava.streams(token, activity_id)
    if not streams.get("latlng"):
        _save_without_gps(db, user_id, activity, started, name, is_race)
        return True
    try:
        save_file_run(
            db,
            storage,
            user_id,
            suffix=".gpx",
            content=streams_to_gpx(started, streams, name),
            name=name,
            is_race=is_race,
            strava_activity_id=activity_id,
        )
    except HTTPException:  # unreadable track or a duplicate file: leave it out
        db.rollback()
        return False
    return True


def _save_without_gps(db, user_id, activity, started, name, is_race) -> None:
    """Treadmill and other indoor runs: distance and time only, like a manual entry."""
    distance = float(activity["distance"])
    moving = float(activity.get("moving_time") or activity.get("elapsed_time"))
    db.add(
        Run(
            user_id=user_id,
            name=name,
            started_at=started,
            source="manual",
            surface="treadmill",
            distance_m=round(distance, 1),
            elapsed_s=float(activity.get("elapsed_time") or moving),
            moving_time_s=moving,
            avg_pace_s_per_km=round(moving / (distance / 1000), 1),
            elevation_gain_m=None,
            avg_hr=activity.get("average_heartrate"),
            is_race=is_race,
            strava_activity_id=int(activity["id"]),
        )
    )
    db.commit()


def _already_uploaded(db: Session, user_id, activity: dict) -> bool:
    """A run you uploaded as a GPX yourself before connecting Strava."""
    started = start_time(activity)
    distance = float(activity["distance"])
    window = timedelta(seconds=SAME_START_S)
    candidates = db.scalars(
        select(Run.distance_m).where(
            Run.user_id == user_id,
            and_(Run.started_at >= started - window, Run.started_at <= started + window),
        )
    ).all()
    return any(abs(d - distance) <= SAME_DISTANCE * distance for d in candidates)


def _access_token(db: Session, conn: StravaConnection, strava: StravaClient) -> str:
    if expired(conn.expires_at):
        _store_tokens(conn, strava.refresh(decrypt(conn.refresh_token)))
        db.commit()
    return decrypt(conn.access_token)


def _store_tokens(conn: StravaConnection, tokens: dict) -> None:
    conn.access_token = encrypt(tokens["access_token"])
    conn.refresh_token = encrypt(tokens["refresh_token"])
    conn.expires_at = int(tokens.get("expires_at") or time.time() + tokens.get("expires_in", 0))


def _remove(db: Session, storage: Storage, user_id) -> None:
    """Delete the connection and every run imported from Strava, with their files."""
    runs = db.scalars(
        select(Run).where(Run.user_id == user_id, Run.strava_activity_id.is_not(None))
    ).all()
    for run in runs:
        if run.raw_file_key:
            try:
                storage.delete(run.raw_file_key)
            except StorageError:
                logger.error("Couldn't delete %s while removing Strava data", run.raw_file_key)
        db.delete(run)
    conn = _connection(db, user_id)
    if conn is not None:
        db.delete(conn)
    db.commit()


def _connection(db: Session, user_id) -> StravaConnection | None:
    return db.scalar(select(StravaConnection).where(StravaConnection.user_id == user_id))


def _unavailable(exc: StravaError) -> HTTPException:
    if isinstance(exc, StravaRateLimited):
        return HTTPException(503, "Strava's rate limit was reached. Try again in 15 minutes.")
    logger.error("Strava error: %s", exc)
    return HTTPException(502, "Strava isn't responding right now. Try again in a few minutes.")
