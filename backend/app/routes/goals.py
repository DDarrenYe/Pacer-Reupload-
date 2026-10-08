import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.analytics.data import load_efforts
from app.analytics.goals import GoalAnalysis, RunInfo, analyse
from app.auth import CurrentUserId, WritableUserId
from app.db import DbSession
from app.models import Goal, Run
from app.schemas.goal import AnalysisOut, EquivalentOut, GoalIn, GoalOut, WeekPointOut

router = APIRouter(prefix="/goals", tags=["goals"])

PRESET_NAMES = {5.0: "5k", 10.0: "10k", 21.0975: "Half marathon", 42.195: "Marathon"}


@router.get("", response_model=list[GoalOut])
def list_goals(user_id: CurrentUserId, db: DbSession) -> list[GoalOut]:
    """Your goals, soonest race first, each with where you stand and what to do."""
    goals = db.scalars(select(Goal).where(Goal.user_id == user_id).order_by(Goal.race_date)).all()
    if not goals:
        return []
    efforts, runs = load_efforts(db, user_id), _run_infos(db, user_id)
    today = datetime.now(UTC).date()
    return [_out(g, efforts, runs, today) for g in goals]


@router.post("", response_model=GoalOut, status_code=201)
def create_goal(body: GoalIn, user_id: WritableUserId, db: DbSession) -> GoalOut:
    today = datetime.now(UTC).date()
    if body.race_date < today:
        raise HTTPException(422, "Pick a race date that's today or later.")
    goal = Goal(user_id=user_id)
    _apply(goal, body)
    db.add(goal)
    db.commit()
    return _out(goal, load_efforts(db, user_id), _run_infos(db, user_id), today)


@router.put("/{goal_id}", response_model=GoalOut)
def update_goal(
    goal_id: uuid.UUID, body: GoalIn, user_id: WritableUserId, db: DbSession
) -> GoalOut:
    goal = _own(db, goal_id, user_id)
    _apply(goal, body)
    db.commit()
    today = datetime.now(UTC).date()
    return _out(goal, load_efforts(db, user_id), _run_infos(db, user_id), today)


@router.delete("/{goal_id}", status_code=204)
def delete_goal(goal_id: uuid.UUID, user_id: WritableUserId, db: DbSession) -> Response:
    db.delete(_own(db, goal_id, user_id))
    db.commit()
    return Response(status_code=204)


def _apply(goal: Goal, body: GoalIn) -> None:
    preset = PRESET_NAMES.get(round(body.distance_km, 4))
    goal.name = body.name or (preset or f"{body.distance_km:g} km") + " goal"
    goal.distance_m = round(body.distance_km * 1000, 1)
    goal.target_time_s = body.target_time_s
    goal.race_date = body.race_date


def _own(db: Session, goal_id: uuid.UUID, user_id: uuid.UUID) -> Goal:
    goal = db.get(Goal, goal_id)
    if goal is None or goal.user_id != user_id:
        raise HTTPException(404, "Goal not found.")
    return goal


def _run_infos(db: Session, user_id: uuid.UUID) -> list[RunInfo]:
    runs = db.scalars(
        select(Run).where(Run.user_id == user_id).options(selectinload(Run.splits))
    ).all()
    return [
        RunInfo(
            day=r.started_at.date(),
            distance_m=r.distance_m,
            moving_s=r.moving_time_s,
            is_race=r.is_race,
            splits=tuple((s.distance_m, s.pace_s_per_km) for s in r.splits if not s.is_partial),
        )
        for r in runs
    ]


def _out(goal: Goal, efforts, runs, today) -> GoalOut:
    a: GoalAnalysis = analyse(
        distance_m=goal.distance_m,
        target_s=goal.target_time_s,
        race_date=goal.race_date,
        today=today,
        efforts=efforts,
        runs=runs,
    )
    return GoalOut(
        id=goal.id,
        name=goal.name,
        distance_m=goal.distance_m,
        target_time_s=goal.target_time_s,
        race_date=goal.race_date,
        created_at=goal.created_at,
        analysis=AnalysisOut(
            status=a.status,
            days_left=a.days_left,
            target_pace_s_per_km=a.target_pace_s_per_km,
            now_s=a.now_s,
            personal_now_s=a.personal_now_s,
            anchor=a.anchor,
            projected_s=a.projected_s,
            projection_note=a.projection_note,
            projection_basis=a.projection_basis,
            needed_pct_per_week=a.needed_pct_per_week,
            weekly=[WeekPointOut.model_validate(p) for p in a.weekly],
            equivalents=[
                EquivalentOut(name=n, distance_m=d, time_s=t) for n, d, t in a.equivalents
            ],
            recommendations=a.recommendations,
            result_s=a.result_s,
            result_hit=a.result_hit,
        ),
    )
