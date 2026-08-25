from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from work_scheduler.database.models import (
    Employee,
    Schedule,
    ScheduleEmployee,
    ScheduleStatus,
)


class ScheduleRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list(self, *, status: ScheduleStatus | None = None) -> list[tuple[Schedule, int]]:
        """Each schedule with the size of its team, counted in SQL rather than per row."""
        statement = (
            select(Schedule, func.count(ScheduleEmployee.id))
            .outerjoin(ScheduleEmployee)
            .group_by(Schedule.id)
            .order_by(Schedule.start_date.desc(), Schedule.id.desc())
        )
        if status is not None:
            statement = statement.where(Schedule.status == status)

        return [(schedule, count) for schedule, count in self._session.execute(statement)]

    def get(self, schedule_id: int) -> Schedule | None:
        return self._session.get(Schedule, schedule_id)

    def load(self, schedule_id: int) -> Schedule | None:
        """With the team and hours already fetched, so the caller can close the session."""
        statement = (
            select(Schedule)
            .where(Schedule.id == schedule_id)
            .options(
                selectinload(Schedule.employees).joinedload(ScheduleEmployee.employee),
                selectinload(Schedule.opening_hours),
                selectinload(Schedule.day_overrides),
            )
        )
        return self._session.scalars(statement).unique().one_or_none()

    def add(self, schedule: Schedule) -> Schedule:
        self._session.add(schedule)
        self._session.flush()
        return schedule

    def delete(self, schedule: Schedule) -> None:
        self._session.delete(schedule)

    # Sequence, not list: the class defines a method called "list", which shadows the
    # builtin for every annotation written after it.
    def existing_employee_ids(self, employee_ids: Sequence[int]) -> set[int]:
        statement = select(Employee.id).where(Employee.id.in_(employee_ids))
        return set(self._session.scalars(statement))
