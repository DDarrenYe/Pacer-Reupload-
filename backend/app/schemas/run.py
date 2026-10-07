import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RunSummary(BaseModel):
    source: Literal["gpx", "csv"]
    start_time: datetime | None
    distance_m: float
    elapsed_s: float
    moving_time_s: float
    avg_pace_s_per_km: float
    elevation_gain_m: float | None
    avg_hr: float | None = None
    point_count: int


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str | None
    started_at: datetime
    source: Literal["gpx", "csv", "manual"]
    surface: Literal["road", "track", "treadmill"]
    distance_m: float
    elapsed_s: float
    moving_time_s: float
    avg_pace_s_per_km: float
    elevation_gain_m: float | None
    avg_hr: float | None
    is_race: bool
    notes: str | None
    created_at: datetime
    split_type: Literal["negative", "even", "positive"] | None
    pace_drift_s_per_km: float | None
    fastest_split_no: int | None
    slowest_split_no: int | None


class SplitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    split_no: int
    split_length_m: float
    distance_m: float
    duration_s: float
    pace_s_per_km: float
    avg_hr: float | None
    is_partial: bool


class BestEffortOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    distance_m: float
    duration_s: float
    start_offset_m: float


class RunDetail(RunOut):
    splits: list[SplitOut]
    best_efforts: list[BestEffortOut]


class LoadDayOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date
    load_min: float
    acute_7d: float
    chronic_28d: float
    acwr: float | None
    flag: Literal["spike", "normal", "low"] | None


class PredictionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    distance_m: float
    riegel_s: float | None
    personal_s: float | None
    pooled_s: float | None
    anchor_name: str | None
    anchor_time_s: float | None
    extrapolated: bool


class RunnerPredictionsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    predictions: list[PredictionOut]
    personal_exponent: float | None
    pooled_exponent: float | None
    weekly_km: float
    envelope_size: int


class MethodScoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    method: str
    n: int
    mae_s: float | None
    mape_pct: float | None


class CoefficientOut(BaseModel):
    term: str
    estimate: float
    ci_low: float
    ci_high: float


class EvaluationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    enough_data: bool
    n_pairs: int
    n_train: int
    n_test: int
    scores: list[MethodScoreOut]
    coefficients: list[CoefficientOut]
    formula: str | None


class WeekOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    week_start: date
    runs: int
    distance_km: float
    avg_pace_s_per_km: float | None
    predicted_5k_s: float | None


# Typos like 50 km in 20 minutes are caught by these pace limits (per km).
FASTEST_PACE_S = 90  # 1:30 /km, faster than the 1500 m world record
SLOWEST_PACE_S = 30 * 60  # 30:00 /km, a slow walk


class ManualRunIn(BaseModel):
    """A run entered by hand, e.g. on a treadmill without a watch."""

    distance_km: float = Field(gt=0, le=500)
    duration_s: float = Field(gt=0, le=48 * 3600)
    started_at: datetime
    surface: Literal["road", "track", "treadmill"] = "treadmill"
    name: str | None = Field(default=None, max_length=200)
    is_race: bool = False
    avg_hr: float | None = Field(default=None, ge=30, le=250)
    notes: str | None = None

    @model_validator(mode="after")
    def _plausible_pace(self) -> "ManualRunIn":
        pace = self.duration_s / self.distance_km
        if not FASTEST_PACE_S <= pace <= SLOWEST_PACE_S:
            raise ValueError(
                "That works out to an unrealistic pace. Check the distance (km) and time."
            )
        return self
