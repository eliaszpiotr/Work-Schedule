import logging
from datetime import date, time

from sqlalchemy.orm import Session, sessionmaker

from work_scheduler.database.models import Shift
from work_scheduler.database.repositories.shift_repository import ShiftRepository
from work_scheduler.database.session import session_scope
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
            raise ValidationError("Godzina końca musi być późniejsza niż godzina początku.")

        with session_scope(self._session_factory) as session:
            repository = ShiftRepository(session)
            lane = repository.lane(schedule_employee_id)
            if lane is None:
                raise ValidationError("Nie znaleziono tej osoby w grafiku.")
            if not lane.schedule.start_date <= shift_date <= lane.schedule.end_date:
                raise ValidationError("Ten dzień jest poza okresem grafiku.")

            reopened = reopen_if_final(lane.schedule)
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
