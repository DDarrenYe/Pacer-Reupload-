import uuid
from datetime import UTC, datetime

from sqlalchemy import BigInteger, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class StravaConnection(Base):
    """A user's link to their Strava account. Tokens are stored encrypted."""

    __tablename__ = "strava_connections"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(unique=True)
    # One Pacer account per Strava athlete, so a webhook event maps to one user.
    athlete_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    athlete_name: Mapped[str | None] = mapped_column(String(200))
    access_token: Mapped[str] = mapped_column(Text)
    refresh_token: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[int] = mapped_column(BigInteger)  # Unix seconds, as Strava sends it
    scope: Mapped[str] = mapped_column(String(200))
    # Import activities that started after this (Unix seconds); moves forward each sync.
    sync_after: Mapped[int] = mapped_column(BigInteger)
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
