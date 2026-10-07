"""Add splits, best efforts and per-run analytics columns

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-08
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("split_type", sa.String(10)))
    op.add_column("runs", sa.Column("pace_drift_s_per_km", sa.Float()))
    op.add_column("runs", sa.Column("fastest_split_no", sa.Integer()))
    op.add_column("runs", sa.Column("slowest_split_no", sa.Integer()))

    op.create_table(
        "splits",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "run_id", sa.Uuid(), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("split_no", sa.Integer(), nullable=False),
        sa.Column("split_length_m", sa.Float(), nullable=False),
        sa.Column("distance_m", sa.Float(), nullable=False),
        sa.Column("duration_s", sa.Float(), nullable=False),
        sa.Column("pace_s_per_km", sa.Float(), nullable=False),
        sa.Column("avg_hr", sa.Float()),
        sa.Column("is_partial", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_splits_run_id", "splits", ["run_id"])

    op.create_table(
        "best_efforts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "run_id", sa.Uuid(), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.String(20), nullable=False),
        sa.Column("distance_m", sa.Float(), nullable=False),
        sa.Column("duration_s", sa.Float(), nullable=False),
        sa.Column("start_offset_m", sa.Float(), nullable=False),
    )
    op.create_index("ix_best_efforts_run_id", "best_efforts", ["run_id"])

    if op.get_bind().dialect.name == "postgresql":
        # Same reasoning as 0001: block Supabase's public REST API from these tables.
        op.execute("ALTER TABLE splits ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE best_efforts ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_index("ix_best_efforts_run_id", table_name="best_efforts")
    op.drop_table("best_efforts")
    op.drop_index("ix_splits_run_id", table_name="splits")
    op.drop_table("splits")
    for col in ("slowest_split_no", "fastest_split_no", "pace_drift_s_per_km", "split_type"):
        op.drop_column("runs", col)
