from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from work_scheduler.database.base import Base

if TYPE_CHECKING:
    from work_scheduler.database.models.employee import Employee
    from work_scheduler.database.models.schedule import Schedule
    from work_scheduler.database.models.shift import Shift


class ScheduleEmployee(Base):
    """One employee taking part in one schedule: a lane in the calendar."""

    __tablename__ = "schedule_employees"
    __table_args__ = (
        UniqueConstraint("schedule_id", "employee_id", name="uq_schedule_employees_pair"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    schedule_id: Mapped[int] = mapped_column(
        ForeignKey("schedules.id", ondelete="CASCADE"), index=True
    )
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="RESTRICT"), index=True
    )
    display_order: Mapped[int] = mapped_column(Integer, default=0)

    schedule: Mapped["Schedule"] = relationship(back_populates="employees")
    employee: Mapped["Employee"] = relationship(back_populates="schedule_entries")
    shifts: Mapped[list["Shift"]] = relationship(
        back_populates="schedule_employee",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Shift.shift_date",
    )
