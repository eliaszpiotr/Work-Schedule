import pytest
from sqlalchemy import Engine

from work_scheduler.database.models import Profession
from work_scheduler.database.session import create_session_factory
from work_scheduler.services import EmployeeService
from work_scheduler.ui.employees.employees_view import EmployeesView
from work_scheduler.ui.theme import LIGHT

TABLE_PAGE, EMPTY_PAGE = 0, 1


@pytest.fixture
def service(engine: Engine) -> EmployeeService:
    return EmployeeService(create_session_factory(engine))


@pytest.fixture
def view(application, service: EmployeeService) -> EmployeesView:
    return EmployeesView(service, LIGHT)


def test_shows_an_empty_state_without_employees(view: EmployeesView) -> None:
    assert view._stack.currentIndex() == EMPTY_PAGE


def test_lists_employees_from_the_service(view: EmployeesView, service: EmployeeService) -> None:
    service.create("Anna", "Kowalska", Profession.PHARMACIST)
    service.create("Marek", "Nowak", Profession.TECHNICIAN)
    view.reload()

    assert view._stack.currentIndex() == TABLE_PAGE
    assert view._model.rowCount() == 2


def test_columns_show_readable_polish_labels(view: EmployeesView, service: EmployeeService) -> None:
    service.create("Anna", "Kowalska", Profession.PHARMACIST)
    view.reload()

    row = [view._model.index(0, column).data() for column in range(3)]
    assert row == ["Anna Kowalska", "Magister", "Aktywny"]


def test_search_narrows_the_visible_rows(view: EmployeesView, service: EmployeeService) -> None:
    service.create("Anna", "Kowalska", Profession.PHARMACIST)
    service.create("Marek", "Nowak", Profession.TECHNICIAN)
    view.reload()

    view._search.setText("nowak")

    assert view._proxy.rowCount() == 1
    assert view._model.rowCount() == 2


def test_search_also_matches_the_profession(view: EmployeesView, service: EmployeeService) -> None:
    service.create("Anna", "Kowalska", Profession.PHARMACIST)
    service.create("Marek", "Nowak", Profession.TECHNICIAN)
    view.reload()

    view._search.setText("technik")

    assert view._proxy.rowCount() == 1


def test_inactive_people_can_be_hidden(view: EmployeesView, service: EmployeeService) -> None:
    seasonal = service.create("Kasia", "Lato", Profession.TECHNICIAN)
    service.create("Anna", "Kowalska", Profession.PHARMACIST)
    service.set_active(seasonal.id, False)
    view.reload()

    assert view._model.rowCount() == 2

    view._show_inactive.setChecked(False)

    assert view._model.rowCount() == 1
