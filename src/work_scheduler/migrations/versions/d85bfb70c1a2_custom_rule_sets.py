"""Reusable rule sets and schedule snapshots.

Revision ID: d85bfb70c1a2
Revises: b4d715a1c582
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d85bfb70c1a2"
down_revision: str | Sequence[str] | None = "b4d715a1c582"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rule_sets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("rules", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    # SQLite can add these columns in place. Rebuilding schedules would DROP the
    # parent table and cascade-delete its employees, shifts and opening hours.
    op.add_column("schedules", sa.Column("rule_set_name", sa.String(length=120)))
    op.add_column(
        "schedules",
        sa.Column("rules", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )


def downgrade() -> None:
    op.drop_column("schedules", "rules")
    op.drop_column("schedules", "rule_set_name")
    op.drop_table("rule_sets")
