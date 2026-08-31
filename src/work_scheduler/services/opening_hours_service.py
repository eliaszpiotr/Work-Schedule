import logging
from dataclasses import dataclass
from datetime import time

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from work_scheduler.database.models import OpeningHours
from work_scheduler.database.session import session_scope
from work_scheduler.i18n import t, weekday_name
from work_scheduler.services.errors import ValidationError

logger = logging.getLogger(__name__)

DAYS_IN_WEEK = 7


@dataclass(frozen=True, slots=True)
class DayHours:
    """One weekday's opening times. Both sides empty means the pharmacy is closed."""

    weekday: int
    opens: time | None
    closes: time | None

    @property
    def closed(self) -> bool:
        return self.opens is None or self.closes is None

    @property
    def name(self) -> str:
        return weekday_name(self.weekday)


# Sunday closed, Saturday short: the usual shape of a family pharmacy's week.
DEFAULT_WEEK = (
    *(DayHours(weekday, time(8), time(20)) for weekday in range(5)),
    DayHours(5, time(9), time(14)),
    DayHours(6, None, None),
)


def validate_week(week: list[DayHours]) -> None:
    """Shared by the settings screen and the schedule wizard, which edit the same shape."""
    if sorted(day.weekday for day in week) != list(range(DAYS_IN_WEEK)):
        raise ValidationError(t("hours.error.every_day_once"))

    for day in week:
        if day.opens is None and day.closes is None:
            continue
        if day.opens is None or day.closes is None:
            raise ValidationError(t("hours.error.both_or_closed", day=day.name.capitalize()))
        if day.closes <= day.opens:
            raise ValidationError(t("hours.error.close_after_open", day=day.name.capitalize()))


class OpeningHoursService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def week(self) -> list[DayHours]:
        """Always seven days. Missing rows are created from the defaults on first use."""
        with session_scope(self._session_factory) as session:
            stored = {row.weekday: row for row in session.scalars(select(OpeningHours))}

            for default in DEFAULT_WEEK:
                if default.weekday not in stored:
                    stored[default.weekday] = OpeningHours(
                        weekday=default.weekday, opens=default.opens, closes=default.closes
                    )
                    session.add(stored[default.weekday])

            return [
                DayHours(weekday, stored[weekday].opens, stored[weekday].closes)
                for weekday in range(DAYS_IN_WEEK)
            ]

    def save(self, week: list[DayHours]) -> None:
        validate_week(week)

        with session_scope(self._session_factory) as session:
            stored = {row.weekday: row for row in session.scalars(select(OpeningHours))}

            for day in week:
                row = stored.get(day.weekday) or OpeningHours(weekday=day.weekday)
                row.opens, row.closes = day.opens, day.closes
                session.add(row)

            logger.info("Saved opening hours")
