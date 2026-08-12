import logging

from sqlalchemy.orm import Session, sessionmaker

from work_scheduler.database.models import Employee, Profession
from work_scheduler.database.repositories import EmployeeRepository
from work_scheduler.database.session import session_scope
from work_scheduler.services.errors import ConflictError, ValidationError

logger = logging.getLogger(__name__)

MAX_NAME_LENGTH = 80


class EmployeeService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def list_employees(self, *, include_inactive: bool = True) -> list[Employee]:
        with session_scope(self._session_factory) as session:
            return EmployeeRepository(session).list(include_inactive=include_inactive)

    def count(self) -> int:
        with session_scope(self._session_factory) as session:
            return EmployeeRepository(session).count()

    def create(self, first_name: str, last_name: str, profession: Profession) -> Employee:
        first_name, last_name = self._clean_names(first_name, last_name)

        with session_scope(self._session_factory) as session:
            employee = EmployeeRepository(session).add(
                Employee(first_name=first_name, last_name=last_name, profession=profession)
            )
            logger.info("Added employee %s", employee.id)
            return employee

    def update(
        self,
        employee_id: int,
        first_name: str,
        last_name: str,
        profession: Profession,
        *,
        active: bool,
    ) -> Employee:
        first_name, last_name = self._clean_names(first_name, last_name)

        with session_scope(self._session_factory) as session:
            employee = self._require(session, employee_id)
            employee.first_name = first_name
            employee.last_name = last_name
            employee.profession = profession
            employee.active = active
            return employee

    def set_active(self, employee_id: int, active: bool) -> Employee:
        with session_scope(self._session_factory) as session:
            employee = self._require(session, employee_id)
            employee.active = active
            logger.info("Employee %s active=%s", employee_id, active)
            return employee

    def delete(self, employee_id: int) -> None:
        """Only ever possible for someone who was never put in a schedule."""
        with session_scope(self._session_factory) as session:
            repository = EmployeeRepository(session)
            employee = self._require(session, employee_id)

            if repository.is_used_in_any_schedule(employee_id):
                raise ConflictError(
                    "Ten pracownik występuje w grafiku, więc nie można go usunąć.\n"
                    "Oznacz go jako nieaktywnego — zniknie z nowych grafików, "
                    "a historia zostanie zachowana."
                )

            repository.delete(employee)
            logger.info("Deleted employee %s", employee_id)

    @staticmethod
    def _require(session: Session, employee_id: int) -> Employee:
        employee = EmployeeRepository(session).get(employee_id)
        if employee is None:
            raise ValidationError("Nie znaleziono tego pracownika.")
        return employee

    @staticmethod
    def _clean_names(first_name: str, last_name: str) -> tuple[str, str]:
        first_name, last_name = first_name.strip(), last_name.strip()

        if not first_name:
            raise ValidationError("Podaj imię.")
        if not last_name:
            raise ValidationError("Podaj nazwisko.")
        if len(first_name) > MAX_NAME_LENGTH or len(last_name) > MAX_NAME_LENGTH:
            raise ValidationError(f"Imię i nazwisko mogą mieć najwyżej {MAX_NAME_LENGTH} znaków.")

        return first_name, last_name
