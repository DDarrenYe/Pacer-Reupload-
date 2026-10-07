"""Allow runs without a file (manual entries)

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-08
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The unique (user_id, file_hash) constraint still stops duplicate uploads; NULL
    # hashes from manual runs don't clash with each other.
    op.alter_column("runs", "raw_file_key", existing_type=sa.String(300), nullable=True)
    op.alter_column("runs", "file_hash", existing_type=sa.String(64), nullable=True)


def downgrade() -> None:
    op.execute("DELETE FROM runs WHERE raw_file_key IS NULL")
    op.alter_column("runs", "file_hash", existing_type=sa.String(64), nullable=False)
    op.alter_column("runs", "raw_file_key", existing_type=sa.String(300), nullable=False)
