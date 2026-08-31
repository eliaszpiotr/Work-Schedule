from datetime import date, time
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from work_scheduler.database.base import Base

if TYPE_CHECKING:
    from work_scheduler.database.models.schedule import Schedule


def _both_or_neither(name: str) -> CheckConstraint:
    """Empty hours mean the day is closed, so a half-filled pair must not exist.

    Both IS NOT NULL tests are needed: with one side missing, "closes > opens" is NULL,
    and a CHECK that evaluates to NULL passes.
    """
    return CheckConstraint(
        "(opens IS NULL AND closes IS NULL)"
        " OR (opens IS NOT NULL AND closes IS NOT NULL AND closes > opens)",
        name=name,
    )


class HoursMixin:
    opens: Mapped[time | None] = mapped_column(Time, default=None)
    closes: Mapped[time | None] = mapped_column(Time, default=None)

    @property
    def closed(self) -> bool:
        return self.opens is None or self.closes is None


class OpeningHoursMixin(HoursMixin):
    weekday: Mapped[int] = mapped_column(Integer)


class OpeningHours(Base, OpeningHoursMixin):
    """When the pharmacy is open. Seven rows, used as the default for new schedules."""

    __tablename__ = "opening_hours"
    __table_args__ = (
        UniqueConstraint("weekday", name="uq_opening_hours_weekday"),
        _both_or_neither("ck_opening_hours_pair"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)


class ScheduleOpeningHours(Base, OpeningHoursMixin):
    """A schedule's own copy, frozen when it was created so archives never shift."""

    __tablename__ = "schedule_opening_hours"
    __table_args__ = (
        UniqueConstraint("schedule_id", "weekday", name="uq_schedule_opening_hours_day"),
        _both_or_neither("ck_schedule_opening_hours_pair"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    schedule_id: Mapped[int] = mapped_column(
        ForeignKey("schedules.id", ondelete="CASCADE"), index=True
    )

    schedule: Mapped["Schedule"] = relationship(back_populates="opening_hours")


class ScheduleDayOverride(Base, HoursMixin):
    """One calendar date that departs from the weekly pattern.

    Carries both directions: a holiday the pharmacy decides to work, and an ordinary day
    it decides to close. Holidays themselves are computed, never stored — only the
    exceptions to them are worth keeping.
    """

    __tablename__ = "schedule_day_overrides"
    __table_args__ = (
        UniqueConstraint("schedule_id", "day", name="uq_schedule_day_overrides_day"),
        _both_or_neither("ck_schedule_day_overrides_pair"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    schedule_id: Mapped[int] = mapped_column(
        ForeignKey("schedules.id", ondelete="CASCADE"), index=True
    )
    day: Mapped[date] = mapped_column(Date)

    schedule: Mapped["Schedule"] = relationship(back_populates="day_overrides")
