import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.run import FASTEST_PACE_S, SLOWEST_PACE_S


class GoalIn(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    distance_km: float = Field(ge=1, le=100)
    target_time_s: float = Field(gt=0)
    race_date: date

    @model_validator(mode="after")
    def _plausible(self) -> "GoalIn":
        pace = self.target_time_s / self.distance_km
        if not FASTEST_PACE_S <= pace <= SLOWEST_PACE_S:
            raise ValueError("That target works out to an unrealistic pace. Check the time.")
        return self


class WeekPointOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    week_end: date
    predicted_s: float | None


class EquivalentOut(BaseModel):
    name: str
    distance_m: float
    time_s: float


class AnalysisOut(BaseModel):
    status: str
    days_left: int
    target_pace_s_per_km: float
    now_s: float | None
    personal_now_s: float | None
    anchor: str | None
    projected_s: float | None
    projection_note: str | None
    projection_basis: str | None
    needed_pct_per_week: float | None
    weekly: list[WeekPointOut]
    equivalents: list[EquivalentOut]
    recommendations: list[str]
    result_s: float | None
    result_hit: bool | None


class GoalOut(BaseModel):
    id: uuid.UUID
    name: str
    distance_m: float
    target_time_s: float
    race_date: date
    created_at: datetime
    analysis: AnalysisOut
