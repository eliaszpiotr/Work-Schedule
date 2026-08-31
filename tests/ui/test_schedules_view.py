from datetime import date, time

import pytest
from PySide6.QtCore import QDate, QLocale, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QLabel, QTableView
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
from work_scheduler.ui.schedules.people_picker import AVATAR as PICKER_AVATAR
from work_scheduler.ui.schedules.people_picker import (
    NAME_ROLE,
    TRADE_ROLE,
    PersonDelegate,
    is_checked,
)
from work_scheduler.ui.schedules.schedule_dialog import ScheduleDialog, suggested_name
from work_scheduler.ui.schedules.schedules_view import SchedulesView
from work_scheduler.ui.theme import LIGHT, METRICS

CARDS_PAGE, EMPTY_PAGE = 0, 1
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

    def test_the_people_list_ends_on_a_complete_row(self, dialog: ScheduleDialog) -> None:
        assert dialog._people.height() == 5 * METRICS.picker_row_height + 2

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

    def test_the_complete_summary_has_enough_height_to_wrap(self, dialog: ScheduleDialog) -> None:
        dialog._start.setDate(date(2026, 8, 1))
        dialog._end.setDate(date(2026, 8, 31))
        dialog.select_all()

        width = METRICS.dialog_width - 2 * METRICS.space_6
        assert dialog._summary.minimumHeight() >= dialog._summary.heightForWidth(width)

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

        assert view._stack.currentIndex() == CARDS_PAGE
        assert len(view._cards.cards()) == 1

    def test_a_card_reads_the_name_the_period_and_the_team_size(
        self, view: SchedulesView, schedules: ScheduleService, employees: EmployeeService
    ) -> None:
        add_schedule(schedules, employees, "Sierpień")
        view.reload()
        card = view._cards.cards()[0]

        written = " ".join(label.text() for label in card.findChildren(QLabel))
        assert "Sierpień" in written
        assert "10.08.2026 – 23.08.2026" in written
        assert "2 osoby" in written
        assert "Roboczy" in written

    def test_the_status_filter_narrows_the_list(
        self, view: SchedulesView, schedules: ScheduleService, employees: EmployeeService
    ) -> None:
        add_schedule(schedules, employees, "Sierpień")
        view.reload()

        view._filter.select(ScheduleStatus.FINAL)
        view.reload()

        assert view._cards.cards() == []

    def test_the_filter_offers_no_state_the_application_cannot_reach(
        self, view: SchedulesView
    ) -> None:
        """Nothing ever archives a schedule, so an archive filter is a dead end."""
        assert ScheduleStatus.ARCHIVED not in view._filter._values

    def test_opening_a_schedule_announces_which_one(
        self, view: SchedulesView, schedules: ScheduleService, employees: EmployeeService
    ) -> None:
        schedule_id = add_schedule(schedules, employees, "Sierpień")
        view.reload()
        opened: list[int] = []
        view.schedule_opened.connect(opened.append)

        view.pick(schedule_id)
        view.open_selected()

        assert opened == [schedule_id]

    def test_a_card_opens_itself_on_a_double_click(
        self, view: SchedulesView, schedules: ScheduleService, employees: EmployeeService
    ) -> None:
        schedule_id = add_schedule(schedules, employees, "Sierpień")
        view.reload()
        opened: list[int] = []
        view.schedule_opened.connect(opened.append)

        view._cards.cards()[0].opened.emit(schedule_id)

        assert opened == [schedule_id]


class TestPicking:
    """The card list has no selection model of its own, so the view keeps the pick."""

    def test_nothing_is_picked_to_begin_with(
        self, view: SchedulesView, schedules: ScheduleService, employees: EmployeeService
    ) -> None:
        add_schedule(schedules, employees, "Sierpień")
        view.reload()

        assert view.selected_schedule() is None

    def test_picking_a_card_marks_it(
        self, view: SchedulesView, schedules: ScheduleService, employees: EmployeeService
    ) -> None:
        add_schedule(schedules, employees, "Lipiec")
        second = add_schedule(schedules, employees, "Sierpień")
        view.reload()

        view.pick(second)
        picked = [card.property("selected") for card in view._cards.cards()]

        assert view.selected_schedule().id == second
        assert picked.count("true") == 1

    def test_a_pick_does_not_survive_the_schedule_going_away(
        self, view: SchedulesView, schedules: ScheduleService, employees: EmployeeService
    ) -> None:
        schedule_id = add_schedule(schedules, employees, "Sierpień")
        view.reload()
        view.pick(schedule_id)

        schedules.delete(schedule_id)
        view.reload()

        assert view.selected_schedule() is None


class TestDeleting:
    def test_a_schedule_can_be_deleted(
        self, view: SchedulesView, schedules: ScheduleService, employees: EmployeeService
    ) -> None:
        schedule_id = add_schedule(schedules, employees, "Sierpień")
        view.reload()
        view.pick(schedule_id)

        view.delete_selected(confirmed=True)

        assert view._cards.cards() == []
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
        view.pick(schedule_id)

        view.delete_selected(confirmed=True)

        assert schedules.list_schedules() == []

    def test_declining_the_question_keeps_it(
        self, view: SchedulesView, schedules: ScheduleService, employees: EmployeeService
    ) -> None:
        schedule_id = add_schedule(schedules, employees, "Sierpień")
        view.reload()
        view.pick(schedule_id)

        view.delete_selected(confirmed=False)

        assert len(view._cards.cards()) == 1

    def test_deleting_with_nothing_picked_does_nothing(
        self, view: SchedulesView, schedules: ScheduleService, employees: EmployeeService
    ) -> None:
        add_schedule(schedules, employees, "Sierpień")
        view.reload()

        view.delete_selected(confirmed=True)

        assert len(schedules.list_schedules()) == 1


class TestDeleteKey:
    def test_the_delete_key_is_wired_to_the_list(self, view: SchedulesView) -> None:
        """With the buttons gone, the keyboard has to be able to do it."""
        keys = [shortcut.key() for shortcut in view.findChildren(QShortcut)]

        assert QKeySequence(QKeySequence.StandardKey.Delete) in keys


class TestSuggestedName:
    def test_a_period_inside_one_month_is_named_after_it(self) -> None:
        assert suggested_name(date(2026, 8, 1), date(2026, 8, 31)) == "Sierpień 2026"

    def test_a_period_crossing_a_month_gives_the_dates_instead(self) -> None:
        """Calling a schedule that runs into September "Sierpień" would be a small lie."""
        assert suggested_name(date(2026, 8, 26), date(2026, 9, 5)) == "26.08 – 05.09.2026"

    def test_a_period_crossing_a_year_spells_both_out(self) -> None:
        assert suggested_name(date(2026, 12, 28), date(2027, 1, 4)) == "28.12.2026 – 04.01.2027"


class TestNameFollowsThePeriod:
    @pytest.fixture
    def dialog(self, application, employees: EmployeeService) -> ScheduleDialog:
        return ScheduleDialog(None, employees.list_employees(include_inactive=False), OPEN_ALL_WEEK)

    def test_moving_the_dates_renames_the_schedule(self, dialog: ScheduleDialog) -> None:
        dialog._start.setDate(QDate(2026, 11, 2))
        dialog._end.setDate(QDate(2026, 11, 30))

        assert dialog.name == "Listopad 2026"

    def test_a_name_somebody_typed_is_left_alone(self, dialog: ScheduleDialog) -> None:
        dialog._name.setText("Dyżury świąteczne")
        dialog._name.textEdited.emit("Dyżury świąteczne")

        dialog._start.setDate(QDate(2026, 11, 2))

        assert dialog.name == "Dyżury świąteczne"

    def test_clearing_the_name_hands_it_back_to_the_dates(self, dialog: ScheduleDialog) -> None:
        dialog._name.setText("Moje")
        dialog._name.textEdited.emit("Moje")
        dialog._name.setText("")
        dialog._name.textEdited.emit("")

        dialog._start.setDate(QDate(2026, 11, 2))
        dialog._end.setDate(QDate(2026, 11, 30))

        assert dialog.name == "Listopad 2026"


class TestPeoplePicker:
    """The wizard was the one screen where a person was a line of plain text."""

    @pytest.fixture
    def dialog(self, application, employees: EmployeeService) -> ScheduleDialog:
        return ScheduleDialog(None, employees.list_employees(include_inactive=False), OPEN_ALL_WEEK)

    def test_the_rows_are_painted_like_the_employees_screen(self, dialog: ScheduleDialog) -> None:
        assert isinstance(dialog._people.itemDelegate(), PersonDelegate)

    def test_a_row_carries_its_pieces_as_data(self, dialog: ScheduleDialog) -> None:
        item = dialog._people.item(0)

        assert item.data(NAME_ROLE)
        assert item.data(TRADE_ROLE) in ("magister", "technik")
        assert item.text() == ""

    def test_clicking_a_row_ticks_it(self, dialog: ScheduleDialog) -> None:
        item = dialog._people.item(0)
        assert not is_checked(dialog._people.model().index(0, 0))

        dialog._toggle_person(item)

        assert item.checkState() == Qt.CheckState.Checked
        assert dialog.employee_ids == [item.data(Qt.ItemDataRole.UserRole)]
        assert is_checked(dialog._people.model().index(0, 0))

    def test_clicking_it_again_unticks_it(self, dialog: ScheduleDialog) -> None:
        item = dialog._people.item(0)
        dialog._toggle_person(item)
        dialog._toggle_person(item)

        assert dialog.employee_ids == []

    def test_a_row_is_tall_enough_for_an_avatar(self) -> None:
        assert METRICS.picker_row_height > PICKER_AVATAR
