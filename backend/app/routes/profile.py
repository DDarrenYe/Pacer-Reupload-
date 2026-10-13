from datetime import date
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.compare import compare, percentile_table
from app.analytics.data import load_efforts
from app.auth import CurrentUserId, WritableUserId
from app.db import DbSession
from app.models import Profile

router = APIRouter(tags=["profile"])

MIN_BIRTH_YEAR = 1920
MIN_AGE = 5


class ProfileIn(BaseModel):
    birth_year: int | None = Field(default=None)
    sex: Literal["female", "male"] | None = None

    @field_validator("birth_year")
    @classmethod
    def _plausible(cls, year: int | None) -> int | None:
        latest = date.today().year - MIN_AGE
        if year is not None and not MIN_BIRTH_YEAR <= year <= latest:
            raise ValueError(f"Year of birth should be between {MIN_BIRTH_YEAR} and {latest}.")
        return year


class ProfileOut(BaseModel):
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
        return {"profile": profile, "rows": [], "sources": sources}
    rows = compare(load_efforts(db, user_id), profile.age, profile.sex, date.today())
    return {
        "profile": profile,
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
            }
            for r in rows
        ],
        "sources": sources,
    }


def _profile(db: Session, user_id) -> Profile | None:
    return db.scalar(select(Profile).where(Profile.user_id == user_id))


def _out(profile: Profile | None) -> ProfileOut:
    if profile is None:
        return ProfileOut(birth_year=None, sex=None, age=None)
    age = date.today().year - profile.birth_year if profile.birth_year else None
    return ProfileOut(birth_year=profile.birth_year, sex=profile.sex, age=age)
