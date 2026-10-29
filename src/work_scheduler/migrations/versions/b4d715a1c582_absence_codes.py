"""Store non-working codes in schedule cells.

Revision ID: b4d715a1c582
Revises: 9a09ec6b9dec
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b4d715a1c582"
down_revision: str | Sequence[str] | None = "9a09ec6b9dec"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "absences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("schedule_employee_id", sa.Integer(), nullable=False),
        sa.Column("absence_date", sa.Date(), nullable=False),
        sa.Column("code", sa.String(length=3), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["schedule_employee_id"], ["schedule_employees.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("schedule_employee_id", "absence_date", name="uq_absences_one_per_day"),
    )
    op.create_index("ix_absences_schedule_employee_id", "absences", ["schedule_employee_id"])
    op.create_index("ix_absences_absence_date", "absences", ["absence_date"])


def downgrade() -> None:
    op.drop_index("ix_absences_absence_date", table_name="absences")
    op.drop_index("ix_absences_schedule_employee_id", table_name="absences")
    op.drop_table("absences")
