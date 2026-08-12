from sqlalchemy import func, select
from sqlalchemy.orm import Session

from work_scheduler.database.models import Employee, ScheduleEmployee


class EmployeeRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list(self, *, include_inactive: bool = True) -> list[Employee]:
        statement = select(Employee)
        if not include_inactive:
            statement = statement.where(Employee.active.is_(True))

        statement = statement.order_by(
            func.lower(Employee.last_name), func.lower(Employee.first_name)
        )
        return list(self._session.scalars(statement))

    def get(self, employee_id: int) -> Employee | None:
        return self._session.get(Employee, employee_id)

    def add(self, employee: Employee) -> Employee:
        self._session.add(employee)
        self._session.flush()
        return employee

    def delete(self, employee: Employee) -> None:
        self._session.delete(employee)

    def count(self) -> int:
        return self._session.scalar(select(func.count()).select_from(Employee)) or 0

    def is_used_in_any_schedule(self, employee_id: int) -> bool:
        statement = select(ScheduleEmployee.id).where(ScheduleEmployee.employee_id == employee_id)
        return self._session.scalars(statement).first() is not None
