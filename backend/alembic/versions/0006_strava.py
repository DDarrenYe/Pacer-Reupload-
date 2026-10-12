"""Add Strava connections and link runs to Strava activities

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-12
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "strava_connections",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False, unique=True),
        sa.Column("athlete_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("athlete_name", sa.String(200)),
        sa.Column("access_token", sa.Text(), nullable=False),
        sa.Column("refresh_token", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.BigInteger(), nullable=False),
        sa.Column("scope", sa.String(200), nullable=False),
        sa.Column("sync_after", sa.BigInteger(), nullable=False),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
    )
    with op.batch_alter_table("runs") as batch:
        batch.add_column(sa.Column("strava_activity_id", sa.BigInteger()))
        batch.create_unique_constraint(
            "uq_runs_user_strava_activity", ["user_id", "strava_activity_id"]
        )
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE strava_connections ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    with op.batch_alter_table("runs") as batch:
        batch.drop_constraint("uq_runs_user_strava_activity", type_="unique")
        batch.drop_column("strava_activity_id")
    op.drop_table("strava_connections")
