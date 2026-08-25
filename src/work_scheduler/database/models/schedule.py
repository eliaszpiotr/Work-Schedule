from datetime import date, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from work_scheduler.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from work_scheduler.database.models.opening_hours import (
        ScheduleDayOverride,
        ScheduleOpeningHours,
    )
    from work_scheduler.database.models.schedule_employee import ScheduleEmployee


class ScheduleStatus(StrEnum):
    DRAFT = "DRAFT"
    FINAL = "FINAL"
    ARCHIVED = "ARCHIVED"


class Schedule(Base, TimestampMixin):
    __tablename__ = "schedules"
    __table_args__ = (CheckConstraint("end_date >= start_date", name="ck_schedules_dates_ordered"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    status: Mapped[ScheduleStatus] = mapped_column(
        Enum(ScheduleStatus, name="schedule_status", create_constraint=True, validate_strings=True),
        default=ScheduleStatus.DRAFT,
    )
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)

    employees: Mapped[list["ScheduleEmployee"]] = relationship(
        back_populates="schedule",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ScheduleEmployee.display_order",
    )
    opening_hours: Mapped[list["ScheduleOpeningHours"]] = relationship(
        back_populates="schedule",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ScheduleOpeningHours.weekday",
    )
    day_overrides: Mapped[list["ScheduleDayOverride"]] = relationship(
        back_populates="schedule",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ScheduleDayOverride.day",
    )
