import hashlib
import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Form, HTTPException, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import CurrentUserId
from app.db import DbSession
from app.models import Run
from app.routes.files import CONTENT_TYPES, read_upload, summarize
from app.schemas.run import RunOut
from app.storage import StorageDep

router = APIRouter(prefix="/runs", tags=["runs"])

DEFAULT_SURFACE = {"gpx": "road", "csv": "treadmill"}


@router.post("", response_model=RunOut, status_code=201)
def create_run(
    file: UploadFile,
    user_id: CurrentUserId,
    db: DbSession,
    storage: StorageDep,
    surface: Annotated[Literal["road", "track", "treadmill"] | None, Form()] = None,
    is_race: Annotated[bool, Form()] = False,
    name: Annotated[str | None, Form(max_length=200)] = None,
    started_at: Annotated[datetime | None, Form(description="Needed for CSV files")] = None,
    notes: Annotated[str | None, Form()] = None,
) -> Run:
    """Upload a GPX or CSV file and save it as one of your runs."""
    suffix, content = read_upload(file)
    summary = summarize(suffix, content)

    file_hash = hashlib.sha256(content).hexdigest()
    existing = db.scalar(select(Run.id).where(Run.user_id == user_id, Run.file_hash == file_hash))
    if existing:
        raise _duplicate(existing)

    key = f"{user_id}/{file_hash}{suffix}"
    storage.upload(key, content, CONTENT_TYPES[suffix])

    run = Run(
        user_id=user_id,
        name=name or file.filename,
        started_at=summary.start_time or started_at or datetime.now(UTC),
        source=summary.source,
        surface=surface or DEFAULT_SURFACE[summary.source],
        distance_m=summary.distance_m,
        elapsed_s=summary.elapsed_s,
        moving_time_s=summary.moving_time_s,
        avg_pace_s_per_km=summary.avg_pace_s_per_km,
        elevation_gain_m=summary.elevation_gain_m,
        avg_hr=summary.avg_hr,
        is_race=is_race,
        raw_file_key=key,
        file_hash=file_hash,
        notes=notes,
    )
    db.add(run)
    try:
        db.commit()
    except IntegrityError:
        # The same file was uploaded twice at once. The other request owns the stored
        # file (same key), so don't delete it.
        db.rollback()
        existing = db.scalar(
            select(Run.id).where(Run.user_id == user_id, Run.file_hash == file_hash)
        )
        raise _duplicate(existing) from None
    except Exception:
        db.rollback()
        storage.delete(key)
        raise
    return run


@router.get("", response_model=list[RunOut])
def list_runs(user_id: CurrentUserId, db: DbSession) -> list[Run]:
    """Your runs, newest first."""
    return list(
        db.scalars(select(Run).where(Run.user_id == user_id).order_by(Run.started_at.desc()))
    )


@router.get("/{run_id}", response_model=RunOut)
def get_run(
    run_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
) -> Run:
    return _get_own_run(db, run_id, user_id)


@router.delete("/{run_id}", status_code=204)
def delete_run(
    run_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
    storage: StorageDep,
) -> Response:
    """Delete a run and its uploaded file."""
    run = _get_own_run(db, run_id, user_id)
    storage.delete(run.raw_file_key)
    db.delete(run)
    db.commit()
    return Response(status_code=204)


def _get_own_run(db: Session, run_id: uuid.UUID, user_id: uuid.UUID) -> Run:
    run = db.get(Run, run_id)
    # Someone else's run gets the same 404 as a missing one, so ids can't be probed.
    if run is None or run.user_id != user_id:
        raise HTTPException(404, "Run not found.")
    return run


def _duplicate(run_id: uuid.UUID | None) -> HTTPException:
    return HTTPException(
        409, {"message": "You've already uploaded this file.", "run_id": str(run_id)}
    )
