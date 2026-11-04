import logging
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date, time, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, sessionmaker

from work_scheduler.database.base import utcnow
from work_scheduler.database.models import (
    Absence,
    Profession,
    RuleSet,
    Schedule,
    ScheduleDayOverride,
    ScheduleEmployee,
    ScheduleOpeningHours,
    ScheduleStatus,
    Shift,
)
from work_scheduler.database.repositories import ScheduleRepository
from work_scheduler.database.session import session_scope
from work_scheduler.i18n import Language, t, weekday_short
from work_scheduler.services.errors import ValidationError
from work_scheduler.services.holidays import holiday_name
from work_scheduler.services.opening_hours_service import DayHours, validate_week
from work_scheduler.services.rule_sets import RuleSetData, RuleSetService, validate_rules

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
    rules: list[dict] = field(default_factory=list)
    rule_set_name: str | None = None

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

    def available_rule_sets(self) -> list[RuleSetData]:
        return RuleSetService(self._session_factory).list_sets()

    def create(
        self,
        name: str,
        start_date: date,
        end_date: date,
        employee_ids: list[int],
        week: list[DayHours],
        rule_set_id: int | None = None,
    ) -> ScheduleSummary:
        name = self._clean_name(name)
        self._check_period(start_date, end_date)
        validate_week(week)

        with session_scope(self._session_factory) as session:
            repository = ScheduleRepository(session)
            self._check_employees(repository, employee_ids)

            source = session.get(RuleSet, rule_set_id) if rule_set_id is not None else None
            if rule_set_id is not None and source is None:
                raise ValidationError(t("rules.error.missing"))
            schedule = Schedule(
                name=name,
                start_date=start_date,
                end_date=end_date,
                rule_set_name=source.name if source else None,
                rules=validate_rules(source.rules) if source else [],
            )
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
                rules=deepcopy(schedule.rules or []),
                rule_set_name=schedule.rule_set_name,
            )

    def set_rule_set(self, schedule_id: int, rule_set_id: int | None) -> None:
        """Copy current template rules into a schedule without linking future edits."""
        with session_scope(self._session_factory) as session:
            schedule = self._require(session, schedule_id)
            source = session.get(RuleSet, rule_set_id) if rule_set_id is not None else None
            if rule_set_id is not None and source is None:
                raise ValidationError(t("rules.error.missing"))
            rules = validate_rules(source.rules) if source else []
            if schedule.rules == rules and schedule.rule_set_name == (
                source.name if source else None
            ):
                return
            reopen_if_final(schedule)
            schedule.rules = rules
            schedule.rule_set_name = source.name if source else None

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
        from work_scheduler.services.audit import audit
        from work_scheduler.services.shift_service import ShiftService

        checked = audit(
            self.open_schedule(schedule_id), ShiftService(self._session_factory).grid(schedule_id)
        )
        if any(finding.blocking_override is True for finding in checked.findings):
            raise ValidationError(t("rules.error.blocked"))
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

    def update_details(
        self,
        schedule_id: int,
        name: str,
        start_date: date,
        end_date: date,
        week: list[DayHours],
    ) -> bool:
        """Edit a schedule without silently discarding entries beyond a shorter period."""
        name = self._clean_name(name)
        self._check_period(start_date, end_date)
        validate_week(week)
        with session_scope(self._session_factory) as session:
            schedule = self._require(session, schedule_id)
            period_changed = (schedule.start_date, schedule.end_date) != (start_date, end_date)
            if period_changed:
                outside = self._first_outside_entry(session, schedule_id, start_date, end_date)
                if outside is not None:
                    raise ValidationError(
                        t("schedule.error.period_has_entries", date=f"{outside:%d.%m.%Y}")
                    )

            current_hours = {row.weekday: row for row in schedule.opening_hours}
            hours_changed = any(
                day.weekday not in current_hours
                or (current_hours[day.weekday].opens, current_hours[day.weekday].closes)
                != (day.opens, day.closes)
                for day in week
            )
            name_changed = schedule.name != name
            if not (name_changed or period_changed or hours_changed):
                return False

            if period_changed or hours_changed:
                reopen_if_final(schedule)
            schedule.name = name
            schedule.start_date = start_date
            schedule.end_date = end_date
            for day in week:
                row = current_hours.get(day.weekday)
                if row is None:
                    schedule.opening_hours.append(
                        ScheduleOpeningHours(
                            weekday=day.weekday, opens=day.opens, closes=day.closes
                        )
                    )
                else:
                    row.opens, row.closes = day.opens, day.closes
            logger.info("Schedule %s: details updated", schedule_id)
            return True

    @staticmethod
    def _first_outside_entry(
        session: Session, schedule_id: int, start_date: date, end_date: date
    ) -> date | None:
        def outside(column):  # noqa: ANN001, ANN202
            return or_(column < start_date, column > end_date)

        dates = [
            session.scalar(
                select(Shift.shift_date)
                .join(ScheduleEmployee)
                .where(ScheduleEmployee.schedule_id == schedule_id, outside(Shift.shift_date))
                .order_by(Shift.shift_date)
                .limit(1)
            ),
            session.scalar(
                select(Absence.absence_date)
                .join(ScheduleEmployee)
                .where(ScheduleEmployee.schedule_id == schedule_id, outside(Absence.absence_date))
                .order_by(Absence.absence_date)
                .limit(1)
            ),
            session.scalar(
                select(ScheduleDayOverride.day)
                .where(
                    ScheduleDayOverride.schedule_id == schedule_id,
                    outside(ScheduleDayOverride.day),
                )
                .order_by(ScheduleDayOverride.day)
                .limit(1)
            ),
        ]
        return min((day for day in dates if day is not None), default=None)

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
