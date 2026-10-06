"""Create runs table

Revision ID: 0001
Revises:
Create Date: 2026-10-07
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(200)),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(10), nullable=False),
        sa.Column("surface", sa.String(10), nullable=False),
        sa.Column("distance_m", sa.Float(), nullable=False),
        sa.Column("elapsed_s", sa.Float(), nullable=False),
        sa.Column("moving_time_s", sa.Float(), nullable=False),
        sa.Column("avg_pace_s_per_km", sa.Float(), nullable=False),
        sa.Column("elevation_gain_m", sa.Float()),
        sa.Column("avg_hr", sa.Float()),
        sa.Column("is_race", sa.Boolean(), nullable=False),
        sa.Column("raw_file_key", sa.String(300), nullable=False),
        sa.Column("file_hash", sa.String(64), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "file_hash", name="uq_runs_user_file_hash"),
    )
    op.create_index("ix_runs_user_id", "runs", ["user_id"])

    if op.get_bind().dialect.name == "postgresql":
        # Supabase serves every table in the public schema through its REST API, which
        # the browser can call with the public anon key. Row level security with no
        # policies blocks that route entirely. This API connects as the database owner,
        # which bypasses RLS, and does its own per-user filtering.
        op.execute("ALTER TABLE runs ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_index("ix_runs_user_id", table_name="runs")
    op.drop_table("runs")
