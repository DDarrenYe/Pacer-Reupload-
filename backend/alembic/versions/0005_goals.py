"""Add goals table

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-08
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "goals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("distance_m", sa.Float(), nullable=False),
        sa.Column("target_time_s", sa.Float(), nullable=False),
        sa.Column("race_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_goals_user_id", "goals", ["user_id"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE goals ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_index("ix_goals_user_id", table_name="goals")
    op.drop_table("goals")
