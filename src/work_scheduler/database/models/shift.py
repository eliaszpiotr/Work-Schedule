from datetime import date, time
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from work_scheduler.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from work_scheduler.database.models.schedule_employee import ScheduleEmployee


class Shift(Base, TimestampMixin):
    """A block of working time. Cannot cross midnight; see the design document."""

    __tablename__ = "shifts"
    __table_args__ = (
        CheckConstraint("end_time > start_time", name="ck_shifts_times_ordered"),
        # One shift per person per day. An index rather than a constraint, because SQLite
        # cannot add a table constraint without rewriting the table.
        Index("uq_shifts_one_per_day", "schedule_employee_id", "shift_date", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    schedule_employee_id: Mapped[int] = mapped_column(
        ForeignKey("schedule_employees.id", ondelete="CASCADE"), index=True
    )
    shift_date: Mapped[date] = mapped_column(Date, index=True)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)

    schedule_employee: Mapped["ScheduleEmployee"] = relationship(back_populates="shifts")
