import uuid
from datetime import datetime
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
