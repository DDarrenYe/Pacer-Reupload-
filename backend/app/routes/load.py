from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.analytics.load import LoadDay, training_load
from app.auth import CurrentUserId
from app.db import DbSession
from app.models import Run
from app.schemas.run import LoadDayOut

router = APIRouter(prefix="/training-load", tags=["analytics"])


@router.get("", response_model=list[LoadDayOut])
def get_training_load(
    user_id: CurrentUserId,
    db: DbSession,
    days: Annotated[int, Query(ge=7, le=365)] = 56,
) -> list[LoadDay]:
    """Daily load (moving minutes), 7-day acute, 28-day chronic and their ratio (ACWR).

    Dates are in UTC.
    """
    rows = db.execute(select(Run.started_at, Run.moving_time_s).where(Run.user_id == user_id)).all()
    runs = [(started.date(), moving / 60) for started, moving in rows]
    return training_load(runs, end=datetime.now(UTC).date(), days=days)
