import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


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
    source: Literal["gpx", "csv"]
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
