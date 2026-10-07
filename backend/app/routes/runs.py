import hashlib
import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Form, HTTPException, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.analytics.best_efforts import compute_best_efforts
from app.analytics.fatigue import pace_drift
from app.analytics.series import RunSeries
from app.analytics.splits import compute_splits, fastest_and_slowest, split_type
from app.auth import CurrentUserId
from app.db import DbSession
from app.models import BestEffort, Run, Split
from app.routes.files import CONTENT_TYPES, parse_file, read_upload
from app.schemas.run import RunDetail, RunOut, RunSummary
from app.storage import Storage, StorageDep, StorageError

router = APIRouter(prefix="/runs", tags=["runs"])

DEFAULT_SURFACE = {"gpx": "road", "csv": "treadmill"}
# Track sessions are split per lap of a 400 m track; everything else per km.
SPLIT_LENGTH_M = {"track": 400.0}


@router.post("", response_model=RunDetail, status_code=201)
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
    """Upload a GPX or CSV file and save it as one of your runs, with its analytics."""
    suffix, content = read_upload(file)
    summary, series = parse_file(suffix, content)

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
        is_race=is_race,
        raw_file_key=key,
        file_hash=file_hash,
        notes=notes,
    )
    _apply_summary(run, summary)
    _apply_analytics(run, series)
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


@router.post("/reprocess-all")
def reprocess_all_runs(user_id: CurrentUserId, db: DbSession, storage: StorageDep) -> dict:
    """Recalculate every one of your runs from its stored file (after a parser fix)."""
    runs = db.scalars(select(Run).where(Run.user_id == user_id)).all()
    done = failed = 0
    for run in runs:
        try:
            _reprocess(run, storage)
            db.commit()
            done += 1
        except (HTTPException, StorageError):
            db.rollback()
            failed += 1
    return {"reprocessed": done, "failed": failed}


@router.get("", response_model=list[RunOut])
def list_runs(user_id: CurrentUserId, db: DbSession) -> list[Run]:
    """Your runs, newest first."""
    return list(
        db.scalars(select(Run).where(Run.user_id == user_id).order_by(Run.started_at.desc()))
    )


@router.get("/{run_id}", response_model=RunDetail)
def get_run(
    run_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
) -> Run:
    """One of your runs, with splits and best efforts."""
    return _get_own_run(db, run_id, user_id)


@router.post("/{run_id}/reprocess", response_model=RunDetail)
def reprocess_run(
    run_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
    storage: StorageDep,
) -> Run:
    """Re-run parsing and analytics from the stored original file.

    Use this for runs uploaded before an analytics change, or after changing the surface.
    """
    run = _get_own_run(db, run_id, user_id)
    _reprocess(run, storage)
    db.commit()
    return run


def _reprocess(run: Run, storage: Storage) -> None:
    suffix = "." + run.raw_file_key.rsplit(".", 1)[-1]
    summary, series = parse_file(suffix, storage.download(run.raw_file_key))
    _apply_summary(run, summary)
    _apply_analytics(run, series)


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


def _apply_summary(run: Run, summary: RunSummary) -> None:
    run.distance_m = summary.distance_m
    run.elapsed_s = summary.elapsed_s
    run.moving_time_s = summary.moving_time_s
    run.avg_pace_s_per_km = summary.avg_pace_s_per_km
    run.elevation_gain_m = summary.elevation_gain_m
    run.avg_hr = summary.avg_hr


def _apply_analytics(run: Run, series: RunSeries) -> None:
    split_length = SPLIT_LENGTH_M.get(run.surface, 1000.0)
    splits = compute_splits(series, split_length)
    run.split_type = split_type(series)
    run.pace_drift_s_per_km = pace_drift(splits)
    run.fastest_split_no, run.slowest_split_no = fastest_and_slowest(splits)
    run.splits = [
        Split(
            split_no=s.split_no,
            split_length_m=split_length,
            distance_m=s.distance_m,
            duration_s=s.duration_s,
            pace_s_per_km=s.pace_s_per_km,
            avg_hr=s.avg_hr,
            is_partial=s.is_partial,
        )
        for s in splits
    ]
    run.best_efforts = [
        BestEffort(
            name=e.name,
            distance_m=e.distance_m,
            duration_s=e.duration_s,
            start_offset_m=e.start_offset_m,
        )
        for e in compute_best_efforts(series)
    ]


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
