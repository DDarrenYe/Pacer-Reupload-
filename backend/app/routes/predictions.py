from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.analytics.data import load_efforts, load_volumes
from app.analytics.predict import (
    Evaluation,
    RunnerPredictions,
    build_pairs,
    evaluate,
    fit_pooled,
    predict_for_runner,
)
from app.analytics.trends import WeekRow, weekly_trends
from app.auth import CurrentUserId
from app.db import DbSession
from app.models import Run
from app.schemas.run import EvaluationOut, RunnerPredictionsOut, WeekOut

router = APIRouter(tags=["analytics"])


@router.get("/predictions", response_model=RunnerPredictionsOut)
def get_predictions(user_id: CurrentUserId, db: DbSession) -> RunnerPredictions:
    """Predicted 5k, 10k, half and marathon from your last 180 days, by three methods.

    The pooled regression is fitted on every runner's data (only aggregate coefficients
    are used; no one else's runs are returned).
    """
    all_efforts, all_volumes = load_efforts(db), load_volumes(db)
    model = fit_pooled(build_pairs(all_efforts, all_volumes))
    today = datetime.now(UTC).date()
    return predict_for_runner(str(user_id), all_efforts, all_volumes, today, model)


@router.get("/predictions/evaluation", response_model=EvaluationOut)
def get_evaluation(user_id: CurrentUserId, db: DbSession) -> Evaluation:
    """How accurate each method has been: time-ordered test on all runners' data."""
    return evaluate(load_efforts(db), load_volumes(db))


@router.get("/trends", response_model=list[WeekOut])
def get_trends(
    user_id: CurrentUserId,
    db: DbSession,
    weeks: Annotated[int, Query(ge=4, le=104)] = 26,
) -> list[WeekRow]:
    """Weekly distance, average pace and predicted 5k (Riegel), oldest week first."""
    rows = db.execute(
        select(Run.started_at, Run.distance_m, Run.moving_time_s).where(Run.user_id == user_id)
    ).all()
    runs = [(started.date(), dist, moving) for started, dist, moving in rows]
    today = datetime.now(UTC).date()
    return weekly_trends(runs, load_efforts(db, user_id), str(user_id), today, weeks)
