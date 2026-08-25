import pytest
from sqlalchemy import Engine

from work_scheduler.database.models import Profession
from work_scheduler.database.session import create_session_factory
from work_scheduler.services import EmployeeService
from work_scheduler.ui.employees.employees_view import EmployeesView
from work_scheduler.ui.icons import load_icon
from work_scheduler.ui.theme import DARK, LIGHT

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


def visible_names(view: EmployeesView) -> list[str]:
    return [view._proxy.index(row, 0).data() for row in range(view._proxy.rowCount())]


def test_sorts_by_last_name_not_by_first_name(
    view: EmployeesView, service: EmployeeService
) -> None:
    service.create("Zofia", "Adamska", Profession.PHARMACIST)
    service.create("Ewa", "Bąk", Profession.TECHNICIAN)
    view.reload()

    assert visible_names(view) == ["Zofia Adamska", "Ewa Bąk"]


def test_sorting_ignores_letter_case(view: EmployeesView, service: EmployeeService) -> None:
    service.create("anna", "kowalska", Profession.PHARMACIST)
    service.create("Marek", "Nowak", Profession.TECHNICIAN)
    view.reload()

    assert visible_names(view) == ["anna kowalska", "Marek Nowak"]


def test_people_sharing_a_last_name_are_ordered_by_first_name(
    view: EmployeesView, service: EmployeeService
) -> None:
    service.create("Zofia", "Nowak", Profession.TECHNICIAN)
    service.create("Adam", "Nowak", Profession.PHARMACIST)
    view.reload()

    assert visible_names(view) == ["Adam Nowak", "Zofia Nowak"]


def test_the_add_button_icon_follows_a_palette_change(view: EmployeesView) -> None:
    view.apply_palette(DARK)

    assert view._add.icon().cacheKey() == load_icon("plus", DARK.on_accent, 16).cacheKey()


def test_inactive_people_can_be_hidden(view: EmployeesView, service: EmployeeService) -> None:
    seasonal = service.create("Kasia", "Lato", Profession.TECHNICIAN)
    service.create("Anna", "Kowalska", Profession.PHARMACIST)
    service.set_active(seasonal.id, False)
    view.reload()

    assert view._model.rowCount() == 2

    view._show_inactive.setChecked(False)

    assert view._model.rowCount() == 1


def test_right_clicking_a_row_picks_it(view: EmployeesView, service: EmployeeService) -> None:
    """Without this the context menu read an empty selection and never opened."""
    service.create("Anna", "Kowalska", Profession.PHARMACIST)
    service.create("Marek", "Nowak", Profession.TECHNICIAN)
    view.reload()

    view.pick_row_at(view._table.visualRect(view._proxy.index(1, 0)).center())

    assert view.selected_employee().last_name == "Nowak"
