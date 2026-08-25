from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from work_scheduler.database.models import ScheduleEmployee, Shift


class ShiftRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def for_schedule(self, schedule_id: int) -> list[Shift]:
        statement = (
            select(Shift).join(ScheduleEmployee).where(ScheduleEmployee.schedule_id == schedule_id)
        )
        return list(self._session.scalars(statement))

    def find(self, schedule_employee_id: int, shift_date: date) -> Shift | None:
        statement = select(Shift).where(
            Shift.schedule_employee_id == schedule_employee_id,
            Shift.shift_date == shift_date,
        )
        return self._session.scalars(statement).one_or_none()

    def lane(self, schedule_employee_id: int) -> ScheduleEmployee | None:
        return self._session.get(ScheduleEmployee, schedule_employee_id)

    def lane_ids(self, schedule_id: int) -> list[int]:
        statement = (
            select(ScheduleEmployee.id)
            .where(ScheduleEmployee.schedule_id == schedule_id)
            .order_by(ScheduleEmployee.display_order)
        )
        return list(self._session.scalars(statement))

    def add(self, shift: Shift) -> None:
        self._session.add(shift)

    def delete(self, shift: Shift) -> None:
        self._session.delete(shift)
