from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from work_scheduler.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from work_scheduler.database.models.schedule_employee import ScheduleEmployee


class Absence(Base, TimestampMixin):
    """One non-working label in a schedule cell."""

    __tablename__ = "absences"
    __table_args__ = (
        UniqueConstraint("schedule_employee_id", "absence_date", name="uq_absences_one_per_day"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    schedule_employee_id: Mapped[int] = mapped_column(
        ForeignKey("schedule_employees.id", ondelete="CASCADE"), index=True
    )
    absence_date: Mapped[date] = mapped_column(Date, index=True)
    code: Mapped[str] = mapped_column(String(3))

    schedule_employee: Mapped["ScheduleEmployee"] = relationship(back_populates="absences")
