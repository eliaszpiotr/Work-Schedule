from datetime import date, time

import pytest
from PySide6.QtCore import QLocale, QPoint
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QTableView
from sqlalchemy import Engine

from work_scheduler.database.models import Profession, ScheduleStatus
from work_scheduler.database.session import create_session_factory
from work_scheduler.services import (
    DayHours,
    EmployeeService,
    OpeningHoursService,
    ScheduleService,
    ShiftService,
)
from work_scheduler.ui.schedules.schedule_dialog import ScheduleDialog
from work_scheduler.ui.schedules.schedules_view import SchedulesView
from work_scheduler.ui.theme import LIGHT

TABLE_PAGE, EMPTY_PAGE = 0, 1
OPEN_ALL_WEEK = [DayHours(weekday, time(8), time(20)) for weekday in range(7)]


@pytest.fixture
def employees(engine: Engine) -> EmployeeService:
    service = EmployeeService(create_session_factory(engine))
    service.create("Anna", "Kowalska", Profession.PHARMACIST)
    service.create("Marek", "Nowak", Profession.TECHNICIAN)
    return service


@pytest.fixture
def schedules(engine: Engine) -> ScheduleService:
    return ScheduleService(create_session_factory(engine))


@pytest.fixture
def hours(engine: Engine) -> OpeningHoursService:
    return OpeningHoursService(create_session_factory(engine))


@pytest.fixture
def shifts(engine: Engine) -> ShiftService:
    return ShiftService(create_session_factory(engine))


@pytest.fixture
def view(
    application,
    schedules: ScheduleService,
    employees: EmployeeService,
    hours: OpeningHoursService,
    shifts: ShiftService,
) -> SchedulesView:
    return SchedulesView(schedules, employees, hours, shifts, LIGHT)


def add_schedule(schedules: ScheduleService, employees: EmployeeService, name: str) -> int:
    ids = [person.id for person in employees.list_employees()]
    return schedules.create(name, date(2026, 8, 10), date(2026, 8, 23), ids, OPEN_ALL_WEEK).id


class TestDialog:
    @pytest.fixture
    def dialog(self, application, employees: EmployeeService) -> ScheduleDialog:
        return ScheduleDialog(None, employees.list_employees(include_inactive=False), OPEN_ALL_WEEK)

    def test_it_suggests_a_name(self, dialog: ScheduleDialog) -> None:
        assert dialog.name

    def test_it_offers_every_active_person(self, dialog: ScheduleDialog) -> None:
        assert dialog._people.count() == 2

    def test_nobody_is_chosen_until_you_tick_them(self, dialog: ScheduleDialog) -> None:
        assert dialog.employee_ids == []

    def test_ticked_people_come_back(self, dialog: ScheduleDialog) -> None:
        dialog.select_all()

        assert len(dialog.employee_ids) == 2

    def test_it_starts_from_the_opening_hours_it_was_given(self, dialog: ScheduleDialog) -> None:
        assert dialog.week == OPEN_ALL_WEEK

    def test_it_counts_the_grid_it_will_produce(self, dialog: ScheduleDialog) -> None:
        dialog._start.setDate(date(2026, 8, 12))
        dialog._end.setDate(date(2026, 8, 31))
        dialog.select_all()

        assert "20 dni" in dialog._summary.text()
        assert "2 os" in dialog._summary.text()

    def test_a_backwards_period_is_pointed_out(self, dialog: ScheduleDialog) -> None:
        dialog._start.setDate(date(2026, 8, 31))
        dialog._end.setDate(date(2026, 8, 12))

        assert not dialog._save.isEnabled()

    def test_the_calendar_speaks_polish(self, dialog: ScheduleDialog) -> None:
        calendar = dialog._start.calendarWidget()

        assert calendar.locale().language() is QLocale.Language.Polish

    def test_the_calendar_names_the_weekdays_in_polish(self, dialog: ScheduleDialog) -> None:
        """Qt puts the day names in row 0 of the calendar's model, not in a QHeaderView."""
        model = dialog._start.calendarWidget().findChild(QTableView).model()
        names = [model.index(0, column).data() for column in range(model.columnCount())]

        assert len(names) == 7
        assert names[0].startswith("pon")
        assert names[6].startswith("niedz")

    def test_the_calendar_has_no_week_number_column(self, dialog: ScheduleDialog) -> None:
        model = dialog._start.calendarWidget().findChild(QTableView).model()

        assert model.columnCount() == 7

    def test_the_window_shrinks_back_after_folding_the_hours_away(
        self, dialog: ScheduleDialog
    ) -> None:
        dialog.show()
        folded = dialog.height()

        dialog._customise.setChecked(True)
        unfolded = dialog.height()
        dialog._customise.setChecked(False)

        assert unfolded > folded
        assert dialog.height() == folded


class TestList:
    def test_it_shows_an_empty_state_without_schedules(self, view: SchedulesView) -> None:
        assert view._stack.currentIndex() == EMPTY_PAGE

    def test_it_lists_what_was_created(
        self, view: SchedulesView, schedules: ScheduleService, employees: EmployeeService
    ) -> None:
        add_schedule(schedules, employees, "Sierpień")
        view.reload()

        assert view._stack.currentIndex() == TABLE_PAGE
        assert view._model.rowCount() == 1

    def test_a_row_reads_the_period_and_the_team_size(
        self, view: SchedulesView, schedules: ScheduleService, employees: EmployeeService
    ) -> None:
        add_schedule(schedules, employees, "Sierpień")
        view.reload()

        row = [view._model.index(0, column).data() for column in range(4)]
        assert row == ["Sierpień", "10.08.2026 – 23.08.2026", "2", "Roboczy"]

    def test_the_status_filter_narrows_the_list(
        self, view: SchedulesView, schedules: ScheduleService, employees: EmployeeService
    ) -> None:
        add_schedule(schedules, employees, "Sierpień")
        view.reload()

        view._status.setCurrentIndex(view._status.findData(ScheduleStatus.ARCHIVED))

        assert view._model.rowCount() == 0

    def test_opening_a_schedule_announces_which_one(
        self, view: SchedulesView, schedules: ScheduleService, employees: EmployeeService
    ) -> None:
        schedule_id = add_schedule(schedules, employees, "Sierpień")
        view.reload()
        opened: list[int] = []
        view.schedule_opened.connect(opened.append)

        view._table.selectRow(0)
        view.open_selected()

        assert opened == [schedule_id]


class TestContextMenu:
    """Right-clicking does not move the selection in Qt, so a menu that reads the
    selection found nothing and never opened — which is why deleting looked broken."""

    def test_right_clicking_a_row_picks_it(
        self, view: SchedulesView, schedules: ScheduleService, employees: EmployeeService
    ) -> None:
        add_schedule(schedules, employees, "Lipiec")
        add_schedule(schedules, employees, "Sierpień")
        view.reload()

        view.pick_row_at(view._table.visualRect(view._model.index(1, 0)).center())

        assert view.selected_schedule().name == view._model.schedule_at(1).name

    def test_clicking_past_the_last_row_changes_nothing(
        self, view: SchedulesView, schedules: ScheduleService, employees: EmployeeService
    ) -> None:
        add_schedule(schedules, employees, "Sierpień")
        view.reload()
        view._table.selectRow(0)

        view.pick_row_at(QPoint(5, 10_000))

        assert view.selected_schedule() is not None


class TestDeleting:
    def test_a_schedule_can_be_deleted(
        self, view: SchedulesView, schedules: ScheduleService, employees: EmployeeService
    ) -> None:
        add_schedule(schedules, employees, "Sierpień")
        view.reload()
        view._table.selectRow(0)

        view.delete_selected(confirmed=True)

        assert view._model.rowCount() == 0
        assert schedules.list_schedules() == []

    def test_a_schedule_with_hours_in_it_can_still_be_deleted(
        self, view: SchedulesView, schedules: ScheduleService, employees: EmployeeService
    ) -> None:
        schedule_id = add_schedule(schedules, employees, "Sierpień")
        data = schedules.open_schedule(schedule_id)
        ShiftService(view._schedules._session_factory).set_shift(
            data.lanes[0].id, date(2026, 8, 10), time(8), time(16)
        )
        view.reload()
        view._table.selectRow(0)

        view.delete_selected(confirmed=True)

        assert schedules.list_schedules() == []

    def test_declining_the_question_keeps_it(
        self, view: SchedulesView, schedules: ScheduleService, employees: EmployeeService
    ) -> None:
        add_schedule(schedules, employees, "Sierpień")
        view.reload()
        view._table.selectRow(0)

        view.delete_selected(confirmed=False)

        assert view._model.rowCount() == 1


class TestDeleteKey:
    def test_the_delete_key_is_wired_to_the_table(self, view: SchedulesView) -> None:
        """With the buttons gone, the keyboard has to be able to do it."""
        keys = [shortcut.key() for shortcut in view._table.findChildren(QShortcut)]

        assert QKeySequence(QKeySequence.StandardKey.Delete) in keys
