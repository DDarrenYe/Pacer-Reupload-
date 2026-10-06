import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Run(Base):
    __tablename__ = "runs"
    __table_args__ = (UniqueConstraint("user_id", "file_hash", name="uq_runs_user_file_hash"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Supabase auth.users id. No foreign key: that table lives in Supabase's own schema.
    user_id: Mapped[uuid.UUID] = mapped_column(index=True)
    name: Mapped[str | None] = mapped_column(String(200))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(10))
    surface: Mapped[str] = mapped_column(String(10))
    distance_m: Mapped[float] = mapped_column(Float)
    elapsed_s: Mapped[float] = mapped_column(Float)
    moving_time_s: Mapped[float] = mapped_column(Float)
    avg_pace_s_per_km: Mapped[float] = mapped_column(Float)
    elevation_gain_m: Mapped[float | None] = mapped_column(Float)
    avg_hr: Mapped[float | None] = mapped_column(Float)
    is_race: Mapped[bool] = mapped_column(default=False)
    raw_file_key: Mapped[str] = mapped_column(String(300))
    file_hash: Mapped[str] = mapped_column(String(64))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
