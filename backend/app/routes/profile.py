from datetime import UTC, date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.analytics.compare import best_rank, compare, percentile_table
from app.analytics.data import load_efforts
from app.analytics.runner_card import personal_bests
from app.analytics.titles import MAX_RUNS, MIN_RUNS, MIN_SPLITS, RunSplits, assign_title
from app.auth import CurrentUserId, WritableUserId
from app.db import DbSession
from app.models import BestEffort, Profile, Run, StravaConnection

router = APIRouter(tags=["profile"])

MIN_BIRTH_YEAR = 1920
MIN_AGE = 5


class ProfileIn(BaseModel):
    display_name: str | None = Field(default=None, max_length=60)
    birth_year: int | None = Field(default=None)
    sex: Literal["female", "male"] | None = None

    @field_validator("birth_year")
    @classmethod
    def _plausible(cls, year: int | None) -> int | None:
        latest = date.today().year - MIN_AGE
        if year is not None and not MIN_BIRTH_YEAR <= year <= latest:
            raise ValueError(f"Year of birth should be between {MIN_BIRTH_YEAR} and {latest}.")
        return year

    @field_validator("display_name")
    @classmethod
    def _tidy(cls, name: str | None) -> str | None:
        name = " ".join(name.split()) if name else None
        return name or None


class ProfileOut(BaseModel):
    display_name: str | None
    birth_year: int | None
    sex: Literal["female", "male"] | None
    age: int | None


@router.get("/profile", response_model=ProfileOut)
def get_profile(user_id: CurrentUserId, db: DbSession) -> ProfileOut:
    return _out(_profile(db, user_id))


@router.put("/profile", response_model=ProfileOut)
def put_profile(body: ProfileIn, user_id: WritableUserId, db: DbSession) -> ProfileOut:
    """Save your year of birth and sex (both optional), used only for comparisons."""
    profile = _profile(db, user_id) or Profile(user_id=user_id)
    profile.display_name = body.display_name
    profile.birth_year = body.birth_year
    profile.sex = body.sex
    db.add(profile)
    db.commit()
    return _out(profile)


@router.get("/comparison")
def comparison(user_id: CurrentUserId, db: DbSession) -> dict:
    """Your predicted time at 5k to marathon, its age grade, and a percentile among
    2023 US marathon finishers of your sex and age (compared on age grade)."""
    profile = _out(_profile(db, user_id))
    table = percentile_table()
    sources = {
        "age_grade": "2025 road age standards by Alan Jones and Tom Bernhard (USATF Masters "
        "Long Distance Running, public domain)",
        "percentiles": table["source"] if table else None,
        "finishers": table["finishers"] if table else None,
    }
    if profile.age is None or profile.sex is None:
        return {"profile": profile, "rows": [], "overall": None, "sources": sources}
    rows = compare(load_efforts(db, user_id), profile.age, profile.sex, date.today())
    overall = _overall(db, user_id, profile.age, profile.sex, rows)
    return {
        "profile": profile,
        "overall": overall,
        "rows": [
            {
                "name": r.name,
                "distance_m": r.distance_m,
                "time_s": r.time_s,
                "anchor": r.anchor,
                "extrapolated": r.extrapolated,
                "age_grade": r.age_grade,
                "band": r.band,
                "faster_than_pct": r.percentile.faster_than_pct if r.percentile else None,
                "group": r.percentile.group if r.percentile else None,
                "rank": r.rank.name if r.rank else None,
                "next_rank": r.rank.next_name if r.rank else None,
                "next_rank_time_s": r.next_rank_time_s,
            }
            for r in rows
        ],
        "sources": sources,
    }


@router.get("/runner-card")
def runner_card(user_id: CurrentUserId, db: DbSession) -> dict:
    """Your name, best rank and personal bests at 5k, 10k, half and marathon (only the
    distances you've actually run)."""
    stored = _profile(db, user_id)
    profile = _out(stored)
    name = profile.display_name
    if name is None:  # fall back to the name on a connected Strava account
        name = db.scalar(
            select(StravaConnection.athlete_name).where(StravaConnection.user_id == user_id)
        )
    rank = None
    if profile.age is not None and profile.sex is not None:
        rank = _overall(db, user_id, profile.age, profile.sex)
    return {
        "name": name,
        "rank": rank,
        "title": _title(db, user_id),
        "bests": [
            {
                "name": pb.name,
                "distance_m": pb.distance_m,
                "time_s": pb.time_s,
                "run_id": str(pb.run_id),
                "date": pb.started_at.date().isoformat(),
            }
            for pb in personal_bests(db, user_id)
        ],
    }


TITLE_WINDOW_DAYS = 180


def _title(db: Session, user_id) -> dict:
    """Your runner title from your recent runs with splits, or how many more it needs."""
    since = datetime.now(UTC) - timedelta(days=TITLE_WINDOW_DAYS)
    runs = db.scalars(
        select(Run)
        .where(Run.user_id == user_id, Run.started_at >= since, Run.source != "manual")
        .options(selectinload(Run.splits))
        .order_by(Run.started_at.desc())
        .limit(MAX_RUNS * 2)
    ).all()
    samples = [
        RunSplits(
            paces=tuple(s.pace_s_per_km for s in run.splits if not s.is_partial),
            distance_m=run.distance_m,
            split_type=run.split_type,
            elevation_gain_m=run.elevation_gain_m,
        )
        for run in runs
    ]
    samples = [s for s in samples if len(s.paces) >= MIN_SPLITS]
    bests = dict(
        db.execute(
            select(BestEffort.name, func.min(BestEffort.duration_s))
            .join(Run, Run.id == BestEffort.run_id)
            .where(Run.user_id == user_id, BestEffort.name.in_(["1k", "5k"]))
            .group_by(BestEffort.name)
        ).all()
    )
    title = assign_title(samples, bests.get("1k"), bests.get("5k"))
    if title is None:
        return {"locked": True, "runs_considered": len(samples), "needed": MIN_RUNS}
    return {
        "locked": False,
        "name": title.name,
        "reason": title.reason,
        "runs_considered": title.runs_considered,
    }


def _overall(db: Session, user_id, age: int, sex: str, rows=None) -> dict | None:
    """Your rank, from your best real time or prediction (see compare.best_rank)."""
    if rows is None:
        rows = compare(load_efforts(db, user_id), age, sex, date.today())
    bests = [(pb.name, pb.distance_m, pb.time_s) for pb in personal_bests(db, user_id)]
    best = best_rank(rows, bests, age, sex)
    if best is None:
        return None
    return {
        "rank": best.rank.name,
        "tier": best.rank.tier,
        "distance": best.distance,
        "age_grade": best.age_grade,
        "source": best.source,
        "next_rank": best.rank.next_name,
        "next_rank_age_grade": best.rank.next_floor,
        "next_rank_time_s": best.next_rank_time_s,
        "progress_pct": best.rank.progress(best.age_grade),
    }


def _profile(db: Session, user_id) -> Profile | None:
    return db.scalar(select(Profile).where(Profile.user_id == user_id))


def _out(profile: Profile | None) -> ProfileOut:
    if profile is None:
        return ProfileOut(display_name=None, birth_year=None, sex=None, age=None)
    age = date.today().year - profile.birth_year if profile.birth_year else None
    return ProfileOut(
        display_name=profile.display_name, birth_year=profile.birth_year, sex=profile.sex, age=age
    )
