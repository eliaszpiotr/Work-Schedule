import logging
from dataclasses import dataclass
from datetime import date, time, timedelta

from sqlalchemy.orm import Session, sessionmaker

from work_scheduler.database.base import utcnow
from work_scheduler.database.models import (
    Profession,
    Schedule,
    ScheduleDayOverride,
    ScheduleEmployee,
    ScheduleOpeningHours,
    ScheduleStatus,
)
from work_scheduler.database.repositories import ScheduleRepository
from work_scheduler.database.session import session_scope
from work_scheduler.i18n import Language, t, weekday_short
from work_scheduler.services.errors import ValidationError
from work_scheduler.services.holidays import holiday_name
from work_scheduler.services.opening_hours_service import DayHours, validate_week

logger = logging.getLogger(__name__)

MAX_NAME_LENGTH = 120
# A year and a day. Guards against a typo in the year turning the grid into 30 000 rows.
MAX_PERIOD_DAYS = 366


def reopen_if_final(schedule: Schedule) -> bool:
    """A closed schedule that gets edited stops being closed.

    Nothing is blocked — the point is that "gotowy" keeps meaning "somebody checked
    this", so a sheet already on the wall cannot quietly stop matching the database.
    """
    if schedule.status is not ScheduleStatus.FINAL:
        return False
    schedule.status = ScheduleStatus.DRAFT
    schedule.finalized_at = None
    logger.info("Schedule %s went back to draft after an edit", schedule.id)
    return True


def days_between(start: date, end: date) -> list[date]:
    """Every day of the period, in order. The grid has exactly this many rows."""
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


@dataclass(frozen=True, slots=True)
class Lane:
    """One column of the grid: a person taking part in this schedule."""

    id: int
    employee_id: int
    name: str
    profession: Profession


@dataclass(frozen=True, slots=True)
class ScheduleSummary:
    id: int
    name: str
    start_date: date
    end_date: date
    status: ScheduleStatus
    employee_count: int

    @property
    def period(self) -> str:
        return f"{self.start_date:%d.%m.%Y} – {self.end_date:%d.%m.%Y}"

    @property
    def day_count(self) -> int:
        return (self.end_date - self.start_date).days + 1


@dataclass(frozen=True, slots=True)
class DayInfo:
    """One row of the grid: when the pharmacy is open that day, and why."""

    day: date
    opens: time | None
    closes: time | None
    holiday: str | None
    overridden: bool

    @property
    def closed(self) -> bool:
        return self.opens is None or self.closes is None

    @property
    def label(self) -> str:
        return f"{weekday_short(self.day.weekday())} {self.day:%d.%m}"

    @property
    def weekend(self) -> bool:
        return self.day.weekday() >= 5


@dataclass(frozen=True, slots=True)
class ScheduleData:
    """Everything the grid needs, as plain values: no ORM objects escape the service."""

    id: int
    name: str
    start_date: date
    end_date: date
    status: ScheduleStatus
    lanes: list[Lane]
    week: list[DayHours]
    overrides: dict[date, tuple[time | None, time | None]]

    def days(self) -> list[date]:
        return days_between(self.start_date, self.end_date)

    def day_info(self, day: date, language: Language | None = None) -> DayInfo:
        """An exception for this date wins; otherwise a holiday closes it; otherwise
        the day follows the weekly pattern.

        ``language`` exists for the printed sheet, which may be in a different language
        than the interface that asked for it.
        """
        holiday = holiday_name(day, language)

        if day in self.overrides:
            opens, closes = self.overrides[day]
            return DayInfo(day, opens, closes, holiday, overridden=True)

        if holiday is not None:
            return DayInfo(day, None, None, holiday, overridden=False)

        weekly = self.week[day.weekday()]
        return DayInfo(day, weekly.opens, weekly.closes, None, overridden=False)

    def timeline(self, language: Language | None = None) -> list[DayInfo]:
        return [self.day_info(day, language) for day in self.days()]

    def holiday_count(self) -> int:
        return sum(1 for info in self.timeline() if info.holiday)


class ScheduleService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def list_schedules(self, *, status: ScheduleStatus | None = None) -> list[ScheduleSummary]:
        with session_scope(self._session_factory) as session:
            return [
                ScheduleSummary(
                    id=schedule.id,
                    name=schedule.name,
                    start_date=schedule.start_date,
                    end_date=schedule.end_date,
                    status=schedule.status,
                    employee_count=count,
                )
                for schedule, count in ScheduleRepository(session).list(status=status)
            ]

    def create(
        self,
        name: str,
        start_date: date,
        end_date: date,
        employee_ids: list[int],
        week: list[DayHours],
    ) -> ScheduleSummary:
        name = self._clean_name(name)
        self._check_period(start_date, end_date)
        validate_week(week)

        with session_scope(self._session_factory) as session:
            repository = ScheduleRepository(session)
            self._check_employees(repository, employee_ids)

            schedule = Schedule(name=name, start_date=start_date, end_date=end_date)
            # The order the user picked becomes the order of the columns.
            schedule.employees = [
                ScheduleEmployee(employee_id=employee_id, display_order=order)
                for order, employee_id in enumerate(employee_ids)
            ]
            # A copy, not a reference: changing the settings later must not rewrite history.
            schedule.opening_hours = [
                ScheduleOpeningHours(weekday=day.weekday, opens=day.opens, closes=day.closes)
                for day in sorted(week, key=lambda day: day.weekday)
            ]
            repository.add(schedule)

            logger.info("Created schedule %s with %s people", schedule.id, len(employee_ids))
            return ScheduleSummary(
                id=schedule.id,
                name=schedule.name,
                start_date=schedule.start_date,
                end_date=schedule.end_date,
                status=schedule.status,
                employee_count=len(employee_ids),
            )

    def open_schedule(self, schedule_id: int) -> ScheduleData:
        with session_scope(self._session_factory) as session:
            schedule = ScheduleRepository(session).load(schedule_id)
            if schedule is None:
                raise ValidationError(t("schedule.error.not_found"))

            return ScheduleData(
                id=schedule.id,
                name=schedule.name,
                start_date=schedule.start_date,
                end_date=schedule.end_date,
                status=schedule.status,
                lanes=[
                    Lane(
                        id=lane.id,
                        employee_id=lane.employee_id,
                        # Surname first: the columns are read and sorted by surname.
                        name=f"{lane.employee.last_name} {lane.employee.first_name}",
                        profession=lane.employee.profession,
                    )
                    for lane in schedule.employees
                ],
                week=[
                    DayHours(hours.weekday, hours.opens, hours.closes)
                    for hours in schedule.opening_hours
                ],
                overrides={
                    override.day: (override.opens, override.closes)
                    for override in schedule.day_overrides
                },
            )

    def override_day(
        self, schedule_id: int, day: date, opens: time | None, closes: time | None
    ) -> None:
        """Make one date depart from the weekly pattern: work a holiday, or close a
        working day. Empty hours mean closed."""
        if (opens is None) != (closes is None):
            raise ValidationError(t("schedule.error.both_hours_or_closed"))
        if opens is not None and closes is not None and closes <= opens:
            raise ValidationError(t("schedule.error.close_after_open"))

        with session_scope(self._session_factory) as session:
            schedule = self._require(session, schedule_id)
            if not schedule.start_date <= day <= schedule.end_date:
                raise ValidationError(t("schedule.error.day_outside_period"))

            reopen_if_final(schedule)
            existing = next((row for row in schedule.day_overrides if row.day == day), None)
            if existing is None:
                schedule.day_overrides.append(
                    ScheduleDayOverride(day=day, opens=opens, closes=closes)
                )
            else:
                existing.opens, existing.closes = opens, closes
            logger.info("Schedule %s: day %s overridden", schedule_id, day)

    def clear_override(self, schedule_id: int, day: date) -> None:
        """Back to the default: the weekly pattern, or closed if the date is a holiday."""
        with session_scope(self._session_factory) as session:
            schedule = self._require(session, schedule_id)
            reopen_if_final(schedule)
            for row in list(schedule.day_overrides):
                if row.day == day:
                    schedule.day_overrides.remove(row)

    def update_employees(self, schedule_id: int, employee_ids: list[int]) -> bool:
        """Replace the team without disturbing retained columns or their shifts.

        Removing a person removes that schedule column and its shifts through the
        existing delete-orphan relationship. The UI confirms that destructive case;
        this service keeps the entire replacement atomic.
        """
        with session_scope(self._session_factory) as session:
            repository = ScheduleRepository(session)
            self._check_employees(repository, employee_ids)
            schedule = self._require(session, schedule_id)
            current_ids = [lane.employee_id for lane in schedule.employees]
            if current_ids == employee_ids:
                return False

            reopened = reopen_if_final(schedule)
            existing = {lane.employee_id: lane for lane in schedule.employees}
            updated: list[ScheduleEmployee] = []
            for order, employee_id in enumerate(employee_ids):
                lane = existing.get(employee_id) or ScheduleEmployee(employee_id=employee_id)
                lane.display_order = order
                updated.append(lane)
            schedule.employees = updated
            logger.info("Schedule %s: team changed to %s people", schedule_id, len(employee_ids))
            return reopened

    def finalize(self, schedule_id: int) -> None:
        """Mark the schedule checked and ready to print. Editing it undoes this."""
        with session_scope(self._session_factory) as session:
            schedule = self._require(session, schedule_id)
            schedule.status = ScheduleStatus.FINAL
            # UTC, like every other timestamp in the database. Mixing the two would
            # make the one field that records when somebody checked a schedule
            # disagree with created_at and updated_at beside it.
            schedule.finalized_at = utcnow()
            logger.info("Schedule %s closed", schedule_id)

    def reopen(self, schedule_id: int) -> None:
        with session_scope(self._session_factory) as session:
            schedule = self._require(session, schedule_id)
            schedule.status = ScheduleStatus.DRAFT
            schedule.finalized_at = None
            logger.info("Schedule %s reopened", schedule_id)

    def rename(self, schedule_id: int, name: str) -> None:
        name = self._clean_name(name)
        with session_scope(self._session_factory) as session:
            self._require(session, schedule_id).name = name

    def delete(self, schedule_id: int) -> None:
        with session_scope(self._session_factory) as session:
            repository = ScheduleRepository(session)
            repository.delete(self._require(session, schedule_id))
            logger.info("Deleted schedule %s", schedule_id)

    @staticmethod
    def _require(session: Session, schedule_id: int) -> Schedule:
        schedule = ScheduleRepository(session).get(schedule_id)
        if schedule is None:
            raise ValidationError(t("schedule.error.not_found"))
        return schedule

    @staticmethod
    def _clean_name(name: str) -> str:
        name = name.strip()
        if not name:
            raise ValidationError(t("schedule.error.name_required"))
        if len(name) > MAX_NAME_LENGTH:
            raise ValidationError(t("schedule.error.name_too_long", max=MAX_NAME_LENGTH))
        return name

    @staticmethod
    def _check_period(start_date: date, end_date: date) -> None:
        if end_date < start_date:
            raise ValidationError(t("schedule.error.end_before_start"))
        if (end_date - start_date).days + 1 > MAX_PERIOD_DAYS:
            raise ValidationError(t("schedule.error.period_too_long", max=MAX_PERIOD_DAYS))

    @staticmethod
    def _check_employees(repository: ScheduleRepository, employee_ids: list[int]) -> None:
        if not employee_ids:
            raise ValidationError(t("schedule.error.no_people"))
        if len(set(employee_ids)) != len(employee_ids):
            raise ValidationError(t("schedule.error.duplicate_person"))
        if repository.existing_employee_ids(employee_ids) != set(employee_ids):
            raise ValidationError(t("schedule.error.person_missing"))
