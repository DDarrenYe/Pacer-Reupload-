from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class RunSummary(BaseModel):
    source: Literal["gpx", "csv"]
    start_time: datetime | None
    distance_m: float
    elapsed_s: float
    moving_time_s: float
    avg_pace_s_per_km: float
    elevation_gain_m: float | None
    point_count: int
