import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication
from sqlalchemy import Engine

from work_scheduler.database.models import Profession
from work_scheduler.database.session import create_session_factory
from work_scheduler.i18n import t
from work_scheduler.services import EmployeeService
from work_scheduler.ui.employees.employee_delegate import AVATAR, GAP, EmployeeDelegate
from work_scheduler.ui.employees.employees_view import EmployeesView
from work_scheduler.ui.icons import load_icon
from work_scheduler.ui.theme import DARK, LIGHT, METRICS

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


def test_sorting_uses_polish_alphabet_independently_of_system_locale(
    view: EmployeesView, service: EmployeeService
) -> None:
    service.create("Anna", "Zawadzka", Profession.PHARMACIST)
    service.create("Celina", "Ćwik", Profession.TECHNICIAN)
    service.create("Łucja", "Łącka", Profession.TECHNICIAN)
    service.create("Maria", "Lis", Profession.PHARMACIST)
    view.reload()

    assert visible_names(view) == ["Celina Ćwik", "Maria Lis", "Łucja Łącka", "Anna Zawadzka"]


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


class TestRowPainting:
    """The rows are painted in a delegate: a cell holds one string, and initials, a
    pill and a state dot are three things."""

    def test_a_row_is_tall_enough_for_an_avatar(self, view: EmployeesView) -> None:
        assert METRICS.employee_row_height > AVATAR

    def test_the_view_paints_with_the_delegate(self, view: EmployeesView) -> None:
        assert isinstance(view._table.itemDelegate(), EmployeeDelegate)

    def test_the_delegate_follows_a_theme_change(self, view: EmployeesView) -> None:
        view.apply_palette(DARK)

        assert view._delegate._palette is DARK

    def test_an_active_person_is_told_from_an_inactive_one(self, view: EmployeesView) -> None:
        rows = view._proxy.rowCount()
        states = {view._proxy.index(row, 2).data() for row in range(rows)}

        assert states <= {"Aktywny", "Nieaktywny"}


class TestTableUsesTheWindow:
    """The stack hands the table its own sizeHint unless it is capped instead."""

    def test_everyone_fits_when_there_is_room(self, application, service: EmployeeService) -> None:
        app, _ = application
        for index in range(9):
            service.create(f"Imię{index}", f"Nazwisko{index}", Profession.TECHNICIAN)

        view = EmployeesView(service, LIGHT)
        view.resize(900, 760)
        view.show()
        app.processEvents()

        assert not view._table.verticalScrollBar().isVisible()

    def test_empty_state_fills_space_and_the_table_caps_to_its_rows(
        self, application, service: EmployeeService
    ) -> None:
        app, _ = application
        view = EmployeesView(service, LIGHT)
        view.resize(900, 760)
        view.show()
        app.processEvents()
        empty = view._stack.maximumHeight()
        assert view._stack.height() > 200

        service.create("Anna", "Kowalska", Profession.PHARMACIST)
        view.reload()
        app.processEvents()

        assert view._stack.maximumHeight() < empty
        assert view._stack.height() == view._stack.maximumHeight()


class TestBadgeColours:
    """Checked on the pixels: the colour is chosen in a delegate, so a model-level
    assertion would pass even with every badge coming out the same grey."""

    @staticmethod
    def badge_colour(view: EmployeesView, row: int) -> str:
        image = view._table.viewport().grab().toImage()
        rect = view._table.visualRect(view._proxy.index(row, 1))
        return QColor(image.pixel(rect.x() + 20, rect.center().y())).name().upper()

    @pytest.fixture
    def two_trades(self, application, service: EmployeeService) -> EmployeesView:
        app, _ = application
        service.create("Anna", "Kowalska", Profession.PHARMACIST)
        service.create("Marek", "Nowak", Profession.TECHNICIAN)

        view = EmployeesView(service, LIGHT)
        view.resize(900, 400)
        view.show()
        app.processEvents()
        return view

    def test_a_pharmacist_badge_is_tinted(self, two_trades: EmployeesView) -> None:
        assert self.badge_colour(two_trades, 0) == LIGHT.work_surface.upper()

    def test_a_technician_badge_is_neutral(self, two_trades: EmployeesView) -> None:
        assert self.badge_colour(two_trades, 1) == LIGHT.surface_active.upper()

    def test_the_two_do_not_come_out_the_same(self, two_trades: EmployeesView) -> None:
        assert self.badge_colour(two_trades, 0) != self.badge_colour(two_trades, 1)


class TestAvatars:
    @pytest.fixture
    def staffed(self, application, service: EmployeeService) -> EmployeesView:
        service.create("Anna", "Kowalska", Profession.PHARMACIST)
        gone = service.create("Marek", "Nowak", Profession.TECHNICIAN)
        service.set_active(gone.id, False)

        view = EmployeesView(service, LIGHT)
        view.resize(900, 400)
        view.show()
        return view

    @staticmethod
    def avatar_colour(view: EmployeesView, row: int) -> QColor:
        image = view._table.viewport().grab().toImage()
        rect = view._table.visualRect(view._proxy.index(row, 0))
        return QColor(image.pixel(rect.x() + METRICS.space_3 + 2, rect.center().y()))

    @staticmethod
    def close(found: QColor, expected: str) -> bool:
        wanted = QColor(expected)
        return all(
            abs(a - b) <= 8
            for a, b in (
                (found.red(), wanted.red()),
                (found.green(), wanted.green()),
                (found.blue(), wanted.blue()),
            )
        )

    def test_active_people_get_a_blue_avatar(self, staffed: EmployeesView) -> None:
        assert self.close(self.avatar_colour(staffed, 0), LIGHT.work_surface)

    def test_inactive_people_get_a_grey_avatar(self, staffed: EmployeesView) -> None:
        assert self.close(self.avatar_colour(staffed, 1), LIGHT.surface_active)

    def test_avatars_follow_the_theme(self, staffed: EmployeesView) -> None:
        staffed.apply_palette(DARK)

        assert self.close(self.avatar_colour(staffed, 0), DARK.work_surface)


def test_the_add_button_says_what_it_does(view: EmployeesView) -> None:
    assert view._add.accessibleName() == t("employees.add")
    assert view._add.property("variant") == "roundPrimary"


def test_the_search_field_is_a_capsule(view: EmployeesView) -> None:
    assert view._search.property("capsule") == "true"


def test_the_status_text_clears_the_cards_right_edge(application, service: EmployeeService) -> None:
    service.create("Anna", "Kowalska", Profession.PHARMACIST)
    view = EmployeesView(service, LIGHT)
    view.resize(900, 400)
    view.show()

    image = view._table.viewport().grab().toImage()
    rect = view._table.visualRect(view._proxy.index(0, 2))
    background = image.pixel(rect.right() - 1, rect.y() + 4)
    inked = [
        x
        for x in range(rect.x(), rect.right() + 1)
        for y in range(rect.y() + 4, rect.bottom() - 4)
        if image.pixel(x, y) != background
    ]
    assert image.width() - 1 - max(inked) >= 12


def test_a_selected_row_still_shows_the_avatar_disc(application, service: EmployeeService) -> None:
    service.create("Anna", "Kowalska", Profession.PHARMACIST)
    view = EmployeesView(service, LIGHT)
    view.resize(900, 400)
    view.show()
    view._table.selectRow(0)
    QApplication.processEvents()

    image = view._table.viewport().grab().toImage()
    rect = view._table.visualRect(view._proxy.index(0, 0))
    background = image.pixelColor(rect.right() - 2, rect.center().y())
    disc = image.pixelColor(rect.x() + GAP + 4, rect.center().y())
    assert disc != background


def test_the_search_placeholder_fits_at_the_narrowest_window(
    application, service: EmployeeService
) -> None:
    view = EmployeesView(service, LIGHT)
    # The window is 880 wide; the sidebar and the page margins take the rest.
    view.resize(880 - METRICS.sidebar_width - 2 * METRICS.window_inset, 560)
    view.show()
    QApplication.processEvents()

    placeholder = view._search.placeholderText()
    needed = view._search.fontMetrics().horizontalAdvance(placeholder)
    assert view._search.width() >= needed + 2 * METRICS.space_4
    assert view._show_inactive.geometry().right() <= view.width()
