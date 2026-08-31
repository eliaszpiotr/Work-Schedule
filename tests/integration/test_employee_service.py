from datetime import date

import pytest
from sqlalchemy import Engine

from work_scheduler.database.models import Profession, Schedule, ScheduleEmployee
from work_scheduler.database.session import create_session_factory, session_scope
from work_scheduler.services import ConflictError, EmployeeService, ValidationError


@pytest.fixture
def service(engine: Engine) -> EmployeeService:
    return EmployeeService(create_session_factory(engine))


class TestCreate:
    def test_adds_an_employee(self, service: EmployeeService) -> None:
        employee = service.create("Anna", "Kowalska", Profession.PHARMACIST)

        assert employee.id is not None
        assert employee.active is True
        assert service.count() == 1

    def test_trims_surrounding_spaces(self, service: EmployeeService) -> None:
        employee = service.create("  Anna  ", " Kowalska ", Profession.PHARMACIST)

        assert employee.full_name == "Anna Kowalska"

    @pytest.mark.parametrize(
        ("first_name", "last_name"),
        [("", "Kowalska"), ("Anna", ""), ("   ", "Kowalska")],
        ids=["no-first-name", "no-last-name", "blank-first-name"],
    )
    def test_refuses_empty_names(
        self, service: EmployeeService, first_name: str, last_name: str
    ) -> None:
        with pytest.raises(ValidationError):
            service.create(first_name, last_name, Profession.TECHNICIAN)

    def test_refuses_absurdly_long_names(self, service: EmployeeService) -> None:
        with pytest.raises(ValidationError):
            service.create("A" * 200, "Kowalska", Profession.TECHNICIAN)


class TestListing:
    def test_sorted_by_surname_ignoring_case(self, service: EmployeeService) -> None:
        service.create("Marek", "nowak", Profession.TECHNICIAN)
        service.create("Anna", "Kowalska", Profession.PHARMACIST)
        service.create("Piotr", "Adamski", Profession.TECHNICIAN)

        assert [e.last_name for e in service.list_employees()] == [
            "Adamski",
            "Kowalska",
            "nowak",
        ]

    def test_can_hide_inactive_people(self, service: EmployeeService) -> None:
        seasonal = service.create("Kasia", "Lato", Profession.TECHNICIAN)
        service.create("Anna", "Kowalska", Profession.PHARMACIST)
        service.set_active(seasonal.id, False)

        assert len(service.list_employees()) == 2
        assert len(service.list_employees(include_inactive=False)) == 1


class TestUpdate:
    def test_changes_the_stored_values(self, service: EmployeeService) -> None:
        employee = service.create("Anna", "Kowalska", Profession.TECHNICIAN)

        service.update(employee.id, "Anna", "Nowak-Kowalska", Profession.PHARMACIST, active=False)

        stored = service.list_employees()[0]
        assert stored.last_name == "Nowak-Kowalska"
        assert stored.profession is Profession.PHARMACIST
        assert stored.active is False

    def test_reports_a_missing_employee(self, service: EmployeeService) -> None:
        with pytest.raises(ValidationError):
            service.set_active(999, False)


class TestDelete:
    def test_removes_someone_never_scheduled(self, service: EmployeeService) -> None:
        employee = service.create("Anna", "Kowalska", Profession.PHARMACIST)

        service.delete(employee.id)

        assert service.count() == 0

    def test_refuses_when_the_person_is_in_a_schedule(
        self, service: EmployeeService, engine: Engine
    ) -> None:
        employee = service.create("Anna", "Kowalska", Profession.PHARMACIST)
        factory = create_session_factory(engine)
        with session_scope(factory) as session:
            schedule = Schedule(
                name="sierpień", start_date=date(2026, 8, 10), end_date=date(2026, 8, 23)
            )
            session.add(ScheduleEmployee(schedule=schedule, employee_id=employee.id))

        with pytest.raises(ConflictError, match="nieaktywnego"):
            service.delete(employee.id)

        assert service.count() == 1
