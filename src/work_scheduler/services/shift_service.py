import logging
from datetime import date, time

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from work_scheduler.database.models import Absence, ScheduleEmployee, Shift
from work_scheduler.database.repositories.shift_repository import ShiftRepository
from work_scheduler.database.session import session_scope
from work_scheduler.i18n import t
from work_scheduler.services.absence import ABSENCE_LABELS
from work_scheduler.services.errors import ValidationError
from work_scheduler.services.schedule_service import reopen_if_final
from work_scheduler.services.time_text import minutes_between

logger = logging.getLogger(__name__)

Cell = tuple[int, date]
Hours = tuple[time, time]


class ShiftService:
    """Reads and writes single cells of the grid. One cell, one transaction."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def grid(self, schedule_id: int) -> dict[Cell, Hours]:
        with session_scope(self._session_factory) as session:
            return {
                (shift.schedule_employee_id, shift.shift_date): (shift.start_time, shift.end_time)
                for shift in ShiftRepository(session).for_schedule(schedule_id)
            }

    def absences(self, schedule_id: int) -> dict[Cell, str]:
        with session_scope(self._session_factory) as session:
            statement = (
                select(Absence)
                .join(ScheduleEmployee)
                .where(ScheduleEmployee.schedule_id == schedule_id)
            )
            return {
                (entry.schedule_employee_id, entry.absence_date): entry.code
                for entry in session.scalars(statement)
            }

    @staticmethod
    def _absence(session: Session, lane_id: int, day: date) -> Absence | None:
        return session.scalars(
            select(Absence).where(
                Absence.schedule_employee_id == lane_id,
                Absence.absence_date == day,
            )
        ).one_or_none()

    @staticmethod
    def _validated_lane(repository: ShiftRepository, lane_id: int, day: date) -> ScheduleEmployee:
        lane = repository.lane(lane_id)
        if lane is None:
            raise ValidationError(t("shift.error.person_not_in_schedule"))
        if not lane.schedule.start_date <= day <= lane.schedule.end_date:
            raise ValidationError(t("schedule.error.day_outside_period"))
        return lane

    def totals(self, schedule_id: int) -> dict[int, int]:
        """Minutes worked per column. Minutes, so half hours survive the sum."""
        with session_scope(self._session_factory) as session:
            repository = ShiftRepository(session)
            totals = dict.fromkeys(repository.lane_ids(schedule_id), 0)

            for shift in repository.for_schedule(schedule_id):
                totals[shift.schedule_employee_id] += minutes_between(
                    shift.start_time, shift.end_time
                )
            return totals

    def set_shift(
        self, schedule_employee_id: int, shift_date: date, start: time, end: time
    ) -> bool:
        """Returns True when the write pulled a closed schedule back to draft."""
        if end <= start:
            raise ValidationError(t("shift.error.end_after_start"))

        with session_scope(self._session_factory) as session:
            repository = ShiftRepository(session)
            lane = self._validated_lane(repository, schedule_employee_id, shift_date)

            reopened = reopen_if_final(lane.schedule)
            absence = self._absence(session, schedule_employee_id, shift_date)
            if absence is not None:
                session.delete(absence)
            existing = repository.find(schedule_employee_id, shift_date)
            if existing is None:
                repository.add(
                    Shift(
                        schedule_employee_id=schedule_employee_id,
                        shift_date=shift_date,
                        start_time=start,
                        end_time=end,
                    )
                )
            else:
                existing.start_time, existing.end_time = start, end
            return reopened

    def set_absence(self, schedule_employee_id: int, day: date, code: str) -> bool:
        """Replace a shift or another absence in one transaction."""
        if code not in ABSENCE_LABELS:
            raise ValidationError(t("grid.unparsed", text=code))
        with session_scope(self._session_factory) as session:
            repository = ShiftRepository(session)
            lane = self._validated_lane(repository, schedule_employee_id, day)
            reopened = reopen_if_final(lane.schedule)
            shift = repository.find(schedule_employee_id, day)
            if shift is not None:
                repository.delete(shift)
            existing = self._absence(session, schedule_employee_id, day)
            if existing is None:
                session.add(
                    Absence(schedule_employee_id=schedule_employee_id, absence_date=day, code=code)
                )
            else:
                existing.code = code
            return reopened

    def clear_shift(self, schedule_employee_id: int, shift_date: date) -> bool:
        """Clearing an empty cell is not an error; the user simply pressed Delete twice."""
        with session_scope(self._session_factory) as session:
            repository = ShiftRepository(session)
            shift = repository.find(schedule_employee_id, shift_date)
            if shift is None:
                return False
            reopened = reopen_if_final(shift.schedule_employee.schedule)
            repository.delete(shift)
            return reopened

    def clear_cell(self, schedule_employee_id: int, day: date) -> bool:
        """Clear either kind of entry in one cell."""
        with session_scope(self._session_factory) as session:
            repository = ShiftRepository(session)
            shift = repository.find(schedule_employee_id, day)
            absence = self._absence(session, schedule_employee_id, day)
            if shift is None and absence is None:
                return False
            lane = shift.schedule_employee if shift is not None else absence.schedule_employee
            reopened = reopen_if_final(lane.schedule)
            if shift is not None:
                repository.delete(shift)
            if absence is not None:
                session.delete(absence)
            return reopened
