"""Load efforts and volumes from the database into the plain shapes predict.py uses."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.predict import Effort, RunVolume
from app.config import get_settings
from app.models import BestEffort, Run

MIN_SHARE_OF_RUN = 0.75


def load_efforts(db: Session, user_id: uuid.UUID | None = None) -> list[Effort]:
    """GPX best efforts plus whole races (any source). All users if user_id is None."""
    # Only GPX best efforts: in a CSV, distance is known only at lap ends, so a "best
    # 1 km" inside a single 5 km lap is just the lap's average pace, not a real effort.
    # And only efforts covering most of their run: a fast km inside a 10k was run at 10k
    # pace, not flat out for 1 km, so it would make short distances look slow.
    best = (
        select(
            Run.user_id,
            Run.id,
            Run.started_at,
            Run.surface,
            BestEffort.distance_m,
            BestEffort.duration_s,
        )
        .join(BestEffort, BestEffort.run_id == Run.id)
        .where(Run.source == "gpx")
        .where(BestEffort.distance_m >= MIN_SHARE_OF_RUN * Run.distance_m)
    )
    races = select(
        Run.user_id, Run.id, Run.started_at, Run.surface, Run.distance_m, Run.moving_time_s
    ).where(Run.is_race.is_(True))
    if user_id is not None:
        best = best.where(Run.user_id == user_id)
        races = races.where(Run.user_id == user_id)
    else:  # pooled data: never the demo's synthetic runs, nor Strava's (see _pooled)
        best = _pooled(best)
        races = _pooled(races)

    efforts = [
        Effort(str(u), str(r), started.date(), dist, secs, surface, is_race=False)
        for u, r, started, surface, dist, secs in db.execute(best)
    ]
    efforts += [
        Effort(str(u), str(r), started.date(), dist, secs, surface, is_race=True)
        for u, r, started, surface, dist, secs in db.execute(races)
    ]
    return efforts


def load_volumes(db: Session, user_id: uuid.UUID | None = None) -> list[RunVolume]:
    query = select(Run.user_id, Run.started_at, Run.distance_m)
    if user_id is not None:
        query = query.where(Run.user_id == user_id)
    else:
        query = _pooled(query)
    return [RunVolume(str(u), started.date(), dist) for u, started, dist in db.execute(query)]


def _pooled(query):
    """Only runs that may shape everyone's model: not the demo's synthetic runs, and not
    runs imported from Strava, whose terms forbid using their data across users or for
    machine learning. Strava runs still count for their owner's own predictions."""
    return query.where(Run.user_id != _demo_id(), Run.strava_activity_id.is_(None))


def _demo_id() -> uuid.UUID:
    return uuid.UUID(get_settings().demo_user_id)
