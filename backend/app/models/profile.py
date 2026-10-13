import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Profile(Base):
    """Optional details used to compare you with runners of your age and sex."""

    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(unique=True)
    # Shown on your runner card.
    display_name: Mapped[str | None] = mapped_column(String(60))
    # Year of birth rather than age, so it stays right without editing.
    birth_year: Mapped[int | None]
    # "female" or "male": the age-grading standards exist only for these two.
    sex: Mapped[str | None] = mapped_column(String(10))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
