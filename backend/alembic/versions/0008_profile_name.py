"""Add a display name to profiles (for the runner card)

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-13
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("profiles") as batch:
        batch.add_column(sa.Column("display_name", sa.String(60)))


def downgrade() -> None:
    with op.batch_alter_table("profiles") as batch:
        batch.drop_column("display_name")
