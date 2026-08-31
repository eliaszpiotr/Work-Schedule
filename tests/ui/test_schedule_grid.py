from datetime import date, time

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QDialog, QLabel
from sqlalchemy import Engine

from work_scheduler.database.models import Profession
from work_scheduler.database.session import create_session_factory
from work_scheduler.services import (
    DayHours,
    EmployeeService,
    ScheduleData,
    ScheduleService,
    ShiftService,
)
from work_scheduler.services.time_text import format_hours
from work_scheduler.ui.schedules import schedule_grid
from work_scheduler.ui.schedules.schedule_grid import (
    LaneHeader,
    ScheduleGridModel,
    ScheduleGridView,
    trade_name,
)
from work_scheduler.ui.theme import DARK, LIGHT, METRICS

# 12–16 August 2026 is Wednesday to Sunday: five days, one of them a closed Sunday.
PERIOD = (date(2026, 8, 12), date(2026, 8, 16))
WEEK = [
    *(DayHours(weekday, time(8), time(20)) for weekday in range(5)),
    DayHours(5, time(9), time(14)),
    DayHours(6, None, None),
]
SUNDAY_ROW = 4


@pytest.fixture
def shifts(engine: Engine) -> ShiftService:
    return ShiftService(create_session_factory(engine))


@pytest.fixture
def schedules(engine: Engine) -> ScheduleService:
    return ScheduleService(create_session_factory(engine))


@pytest.fixture
def schedule(engine: Engine, schedules: ScheduleService) -> ScheduleData:
    employees = EmployeeService(create_session_factory(engine))
    anna = employees.create("Anna", "Kowalska", Profession.PHARMACIST)
    marek = employees.create("Marek", "Nowak", Profession.TECHNICIAN)

    created = schedules.create("Sierpień", *PERIOD, [anna.id, marek.id], WEEK)
    return schedules.open_schedule(created.id)


@pytest.fixture
def model(application, schedule: ScheduleData, shifts: ShiftService) -> ScheduleGridModel:
    return ScheduleGridModel(schedule, shifts, LIGHT)


@pytest.fixture
def view(
    application,
    engine: Engine,
    schedule: ScheduleData,
    schedules: ScheduleService,
    shifts: ShiftService,
) -> ScheduleGridView:
    grid = ScheduleGridView(
        schedule,
        schedules,
        shifts,
        LIGHT,
        employees=EmployeeService(create_session_factory(engine)),
    )
    # Big enough that every row of the period is really laid out, not just the first few.
    # The toolbar, the legend and the totals take their share before the rows do.
    grid.resize(700, 620)
    return grid


class TestShape:
    def test_only_days_belong_to_the_scrollable_model(self, model: ScheduleGridModel) -> None:
        assert model.rowCount() == 5

    def test_a_longer_period_makes_more_rows(
        self, application, engine: Engine, shifts: ShiftService
    ) -> None:
        factory = create_session_factory(engine)
        employee = EmployeeService(factory).create("Anna", "Kowalska", Profession.PHARMACIST)
        service = ScheduleService(factory)
        created = service.create(
            "Dłuższy", date(2026, 8, 12), date(2026, 8, 31), [employee.id], WEEK
        )

        model = ScheduleGridModel(service.open_schedule(created.id), shifts, LIGHT)

        assert model.rowCount() == 20

    def test_there_is_one_column_per_person(self, model: ScheduleGridModel) -> None:
        assert model.columnCount() == 2

    def test_the_columns_are_named_after_the_people(self, model: ScheduleGridModel) -> None:
        names = [model.headerData(column, Qt.Orientation.Horizontal) for column in range(2)]

        assert names == ["Kowalska Anna", "Nowak Marek"]

    def test_the_rows_are_named_after_the_days(self, model: ScheduleGridModel) -> None:
        assert model.headerData(0, Qt.Orientation.Vertical) == "śr 12.08"
        assert model.headerData(SUNDAY_ROW, Qt.Orientation.Vertical) == "nd 16.08"


class TestEditing:
    def test_typing_a_range_stores_a_shift(
        self, model: ScheduleGridModel, schedule: ScheduleData, shifts: ShiftService
    ) -> None:
        model.setData(model.index(0, 0), "10-15")

        lane = schedule.lanes[0].id
        assert shifts.grid(schedule.id)[lane, date(2026, 8, 12)] == (time(10), time(15))

    def test_the_cell_then_reads_back_the_hours(self, model: ScheduleGridModel) -> None:
        model.setData(model.index(0, 0), "10-15")

        assert model.index(0, 0).data() == "10:00–15:00"

    def test_an_empty_cell_shows_nothing(self, model: ScheduleGridModel) -> None:
        assert model.index(0, 0).data() == ""

    def test_clearing_a_cell_removes_the_shift(
        self, model: ScheduleGridModel, schedule: ScheduleData, shifts: ShiftService
    ) -> None:
        model.setData(model.index(0, 0), "10-15")
        model.setData(model.index(0, 0), "")

        assert shifts.grid(schedule.id) == {}

    def test_text_that_cannot_be_read_changes_nothing(
        self, model: ScheduleGridModel, schedule: ScheduleData, shifts: ShiftService
    ) -> None:
        accepted = model.setData(model.index(0, 0), "kiedyś rano")

        assert accepted is False
        assert shifts.grid(schedule.id) == {}

    def test_text_that_cannot_be_read_is_reported(self, model: ScheduleGridModel) -> None:
        complaints: list[str] = []
        model.rejected.connect(complaints.append)

        model.setData(model.index(0, 0), "kiedyś rano")

        assert len(complaints) == 1


class TestClosedDays:
    def test_a_closed_day_cannot_be_filled_in(self, model: ScheduleGridModel) -> None:
        flags = model.flags(model.index(SUNDAY_ROW, 0))

        assert not flags & Qt.ItemFlag.ItemIsEditable

    def test_an_open_day_can_be_filled_in(self, model: ScheduleGridModel) -> None:
        flags = model.flags(model.index(0, 0))

        assert flags & Qt.ItemFlag.ItemIsEditable

    def test_writing_into_a_closed_day_is_refused(
        self, model: ScheduleGridModel, schedule: ScheduleData, shifts: ShiftService
    ) -> None:
        assert model.setData(model.index(SUNDAY_ROW, 0), "10-15") is False
        assert shifts.grid(schedule.id) == {}


class TestPainting:
    """The stylesheet makes Qt draw cells itself and drop the model's background role,
    so these check the pixels rather than the model."""

    @staticmethod
    def corner_colour(view: ScheduleGridView, row: int) -> str:
        image = view._table.viewport().grab().toImage()
        rect = view._table.visualRect(view._model.index(row, 0))
        return image.pixelColor(rect.topLeft() + QPoint(6, 6)).name()

    def test_an_ordinary_cell_is_left_plain(self, view: ScheduleGridView) -> None:
        # Covering the whole opening leaves the row with nothing to complain about.
        view._model.setData(view._model.index(0, 0), "8-20")

        assert self.corner_colour(view, 0) == LIGHT.background.lower()

    def test_a_closed_day_is_shaded(self, view: ScheduleGridView) -> None:
        assert self.corner_colour(view, SUNDAY_ROW) == LIGHT.surface_active.lower()

    def test_hours_outside_opening_time_are_highlighted(self, view: ScheduleGridView) -> None:
        view._model.setData(view._model.index(0, 0), "6-15")

        assert self.corner_colour(view, 0) == LIGHT.warning_surface.lower()


class TestTotals:
    def test_an_untouched_schedule_totals_nothing(self, model: ScheduleGridModel) -> None:
        assert model.totals() == [0, 0]

    def test_hours_add_up_down_the_column(self, model: ScheduleGridModel) -> None:
        model.setData(model.index(0, 0), "10-15")
        model.setData(model.index(1, 0), "8-16")

        assert model.totals() == [13 * 60, 0]

    def test_the_footer_shows_the_models_totals_as_hours(self, view: ScheduleGridView) -> None:
        view._model.setData(view._model.index(0, 0), "8:30-16:00")

        assert format_hours(view._model.totals()[0]) == "7,5 h"

    def test_the_footer_has_one_value_per_person(self, view: ScheduleGridView) -> None:
        assert [format_hours(minutes) for minutes in view._model.totals()] == ["—", "—"]

    def test_the_footer_is_not_an_editable_table(self, view: ScheduleGridView) -> None:
        assert view._totals_bar.focusPolicy() == Qt.FocusPolicy.NoFocus


class TestView:
    def test_it_names_the_schedule(self, view: ScheduleGridView) -> None:
        assert "Sierpień" in view._title.text()

    def test_going_back_is_announced(self, view: ScheduleGridView) -> None:
        left: list[bool] = []
        view.closed.connect(lambda: left.append(True))

        view._back.click()

        assert left == [True]


class TestEditingAnExistingSchedule:
    def test_a_person_can_be_added_from_the_grid(
        self,
        view: ScheduleGridView,
        engine: Engine,
        schedules: ScheduleService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        employees = EmployeeService(create_session_factory(engine))
        extra = employees.create("Ewa", "Bąk", Profession.TECHNICIAN)
        chosen = [lane.employee_id for lane in view._schedule.lanes] + [extra.id]

        class AcceptedTeam:
            employee_ids = chosen

            def __init__(self, *_args, **_kwargs) -> None:
                pass

            @staticmethod
            def exec() -> QDialog.DialogCode:
                return QDialog.DialogCode.Accepted

        monkeypatch.setattr(schedule_grid, "ScheduleTeamDialog", AcceptedTeam)

        view.edit_team()

        saved = schedules.open_schedule(view._schedule.id)
        assert [lane.employee_id for lane in saved.lanes] == chosen
        assert view._model.columnCount() == 3
        assert "3 osoby" in view._period.text()

    def test_removing_a_person_with_shifts_requires_confirmation(
        self,
        view: ScheduleGridView,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        removed = view._schedule.lanes[0]
        view._model.setData(view._model.index(0, 0), "9-15")
        chosen = [view._schedule.lanes[1].employee_id]

        class AcceptedTeam:
            employee_ids = chosen

            def __init__(self, *_args, **_kwargs) -> None:
                pass

            @staticmethod
            def exec() -> QDialog.DialogCode:
                return QDialog.DialogCode.Accepted

        monkeypatch.setattr(schedule_grid, "ScheduleTeamDialog", AcceptedTeam)
        monkeypatch.setattr(schedule_grid, "confirm_destructive", lambda *_args, **_kwargs: False)

        view.edit_team()

        assert removed.employee_id in [lane.employee_id for lane in view._schedule.lanes]

    def test_one_day_can_receive_exceptional_hours(
        self,
        view: ScheduleGridView,
        schedules: ScheduleService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        class AcceptedHours:
            hours = (time(10), time(16))

            def __init__(self, *_args, **_kwargs) -> None:
                pass

            @staticmethod
            def exec() -> QDialog.DialogCode:
                return QDialog.DialogCode.Accepted

        monkeypatch.setattr(schedule_grid, "DayHoursDialog", AcceptedHours)

        view.edit_day_hours(0)

        changed = schedules.open_schedule(view._schedule.id).day_info(PERIOD[0])
        assert (changed.opens, changed.closes, changed.overridden) == (time(10), time(16), True)


# 15 August 2026 (Wniebowzięcie NMP) is the Saturday inside the test period.
HOLIDAY_ROW = 3


class TestHolidayRows:
    def test_the_holiday_row_is_closed_although_saturday_is_open(
        self, model: ScheduleGridModel
    ) -> None:
        assert not model.flags(model.index(HOLIDAY_ROW, 0)) & Qt.ItemFlag.ItemIsEditable

    def test_the_row_header_keeps_only_the_date(self, model: ScheduleGridModel) -> None:
        label = model.headerData(HOLIDAY_ROW, Qt.Orientation.Vertical)

        assert label == "sb 15.08"

    def test_the_holiday_row_is_painted_blue(self, view: ScheduleGridView) -> None:
        assert TestPainting.corner_colour(view, HOLIDAY_ROW) == LIGHT.holiday_surface.lower()

    def test_an_ordinary_closed_sunday_stays_grey(self, view: ScheduleGridView) -> None:
        assert TestPainting.corner_colour(view, SUNDAY_ROW) == LIGHT.surface_active.lower()

    def test_declaring_the_holiday_a_working_day_unlocks_it(self, view: ScheduleGridView) -> None:
        view.set_day_working(HOLIDAY_ROW)

        model = view._model
        assert model.flags(model.index(HOLIDAY_ROW, 0)) & Qt.ItemFlag.ItemIsEditable
        assert model.setData(model.index(HOLIDAY_ROW, 0), "10-14") is True

    def test_an_ordinary_day_can_be_closed_by_hand(self, view: ScheduleGridView) -> None:
        view.set_day_closed(0)

        assert not view._model.flags(view._model.index(0, 0)) & Qt.ItemFlag.ItemIsEditable

    def test_the_default_can_be_restored(self, view: ScheduleGridView) -> None:
        view.set_day_closed(0)
        view.clear_day_override(0)

        assert view._model.flags(view._model.index(0, 0)) & Qt.ItemFlag.ItemIsEditable


class TestSelectionIsNotConfusedWithAClosedDay:
    """The selection used to be painted the same grey as a closed day, so a selected
    cell on a working day read as a day off."""

    def test_a_selected_cell_keeps_its_own_background(self, view: ScheduleGridView) -> None:
        view._table.setCurrentIndex(view._model.index(0, 0))

        assert TestPainting.corner_colour(view, 0) == LIGHT.background.lower()

    def test_a_selected_cell_is_marked_by_a_border_instead(self, view: ScheduleGridView) -> None:
        view._table.setCurrentIndex(view._model.index(0, 0))

        image = view._table.viewport().grab().toImage()
        rect = view._table.visualRect(view._model.index(0, 0))
        edge = image.pixelColor(rect.center().x(), rect.top() + 1).name()

        assert edge == LIGHT.accent.lower()


class TestNoTextClutter:
    def test_the_row_header_carries_only_the_date(self, view: ScheduleGridView) -> None:
        view._model.setData(view._model.index(0, 1), "8-20")

        assert view._model.headerData(0, Qt.Orientation.Vertical) == "śr 12.08"

    def test_the_missing_cover_does_not_show_hover_text(self, view: ScheduleGridView) -> None:
        view._model.setData(view._model.index(0, 1), "8-20")

        tip = view._model.headerData(0, Qt.Orientation.Vertical, Qt.ItemDataRole.ToolTipRole)
        assert tip is None

    def test_the_day_is_still_red(self, view: ScheduleGridView) -> None:
        view._model.setData(view._model.index(0, 1), "8-20")

        assert TestPainting.corner_colour(view, 0) == LIGHT.danger_surface.lower()

    def test_a_rejected_entry_is_reported_then_clears_itself(self, view: ScheduleGridView) -> None:
        view._model.setData(view._model.index(0, 0), "812")
        assert view._status.text()
        assert view._status.isVisibleTo(view)

        view._clear_status()

        assert not view._status.text()
        assert not view._status.isVisibleTo(view)


class TestConsistentTable:
    """The lines are drawn by the delegate, not left to the stylesheet, so a cell looks
    the same whatever state it is in."""

    @staticmethod
    def right_edge(view: ScheduleGridView, row: int, column: int) -> str:
        image = view._table.viewport().grab().toImage()
        rect = view._table.visualRect(view._model.index(row, column))
        return image.pixelColor(rect.right(), rect.center().y()).name()

    def every_internal_right_edge(self, view: ScheduleGridView, row: int) -> set[str]:
        return {
            self.right_edge(view, row, column) for column in range(view._model.columnCount() - 1)
        }

    def test_a_plain_row_is_ruled_the_same_across(self, view: ScheduleGridView) -> None:
        assert self.every_internal_right_edge(view, 0) == {LIGHT.border.lower()}

    def test_a_filled_row_is_ruled_exactly_like_a_plain_one(self, view: ScheduleGridView) -> None:
        view._model.setData(view._model.index(0, 0), "8-20")

        assert self.every_internal_right_edge(view, 0) == self.every_internal_right_edge(view, 1)

    def test_a_closed_row_is_ruled_the_same_too(self, view: ScheduleGridView) -> None:
        assert self.every_internal_right_edge(view, SUNDAY_ROW) == {LIGHT.border.lower()}

    def test_a_holiday_row_is_ruled_the_same_too(self, view: ScheduleGridView) -> None:
        assert self.every_internal_right_edge(view, HOLIDAY_ROW) == {LIGHT.border.lower()}

    def test_the_last_cell_does_not_double_the_outside_frame(self, view: ScheduleGridView) -> None:
        last = view._model.columnCount() - 1
        assert self.right_edge(view, 0, last) == LIGHT.background.lower()

    def test_the_table_has_one_complete_outer_frame(self, view: ScheduleGridView) -> None:
        view.show()
        image = view._card.grab().toImage()
        middle_x, middle_y = image.width() // 2, image.height() // 2

        assert image.pixelColor(middle_x, 0).name() == LIGHT.border_strong.lower()
        assert image.pixelColor(middle_x, image.height() - 1).name() == LIGHT.border_strong.lower()
        assert image.pixelColor(0, middle_y).name() == LIGHT.border_strong.lower()
        assert image.pixelColor(image.width() - 1, middle_y).name() == LIGHT.border_strong.lower()

    def test_the_footer_finishes_flush_with_the_shared_frame(self, view: ScheduleGridView) -> None:
        view.show()

        assert view._totals_bar.geometry().bottom() == view._card.contentsRect().bottom()

    def test_the_totals_rules_line_up_with_the_grid(self, view: ScheduleGridView) -> None:
        view.show()

        for column in range(view._model.columnCount()):
            grid = view._table.visualRect(view._model.index(0, column))
            grid_left = view._table.viewport().geometry().left() + grid.left()
            total = view._totals_bar.column_rect(column)
            expected = grid_left, grid_left + grid.width() - 1
            assert (round(total.left()), round(total.right())) == expected

    def test_the_totals_have_the_same_internal_rule(self, view: ScheduleGridView) -> None:
        view.show()
        image = view._totals_bar.grab().toImage()
        rect = view._totals_bar.column_rect(0)

        rule = image.pixelColor(round(rect.right()), round(rect.center().y())).name()
        assert rule == LIGHT.border.lower()

    def test_the_footer_stays_visible_while_days_scroll(self, view: ScheduleGridView) -> None:
        view.show()
        before = view._totals_bar.mapTo(view, view._totals_bar.rect().topLeft())

        view._table.scrollToBottom()

        assert view._totals_bar.mapTo(view, view._totals_bar.rect().topLeft()) == before


class TestNoCompleter:
    def test_typing_hours_offers_no_dropdown(self, view: ScheduleGridView) -> None:
        editor = view._table.itemDelegate().createEditor(
            view._table.viewport(), None, view._model.index(0, 0)
        )

        assert editor.completer() is None


class TestTableFitsItsRows:
    def test_a_short_schedule_does_not_stretch_to_the_bottom(self, view: ScheduleGridView) -> None:
        view.resize(900, 900)
        view.show()

        header = view._table.horizontalHeader().height()
        rows = view._model.rowCount() * METRICS.table_row_height
        assert view._table.height() <= header + rows + 4

    def test_a_fitting_schedule_does_not_show_a_stray_scrollbar(
        self, view: ScheduleGridView
    ) -> None:
        view.resize(900, 900)
        view.show()

        assert view._table.verticalScrollBar().maximum() == 0

    def test_a_long_schedule_still_uses_the_room_it_has(
        self, application, engine: Engine, schedules: ScheduleService, shifts: ShiftService
    ) -> None:
        employee = EmployeeService(create_session_factory(engine)).create(
            "Anna", "Kowalska", Profession.PHARMACIST
        )
        created = schedules.create(
            "Długi", date(2026, 8, 1), date(2026, 8, 31), [employee.id], WEEK
        )
        grid = ScheduleGridView(schedules.open_schedule(created.id), schedules, shifts, LIGHT)
        grid.resize(900, 640)
        grid.show()

        # A month cannot fit, so the table takes what is left after the toolbar, the
        # legend and the totals — not a token strip with the space wasted below it.
        assert grid._table.height() > grid.height() / 2


class TestLaneHeader:
    """A header section takes one string, so the trade under a name is painted."""

    def test_the_header_is_the_painted_one(self, view: ScheduleGridView) -> None:
        assert isinstance(view._table.horizontalHeader(), LaneHeader)

    def test_it_is_tall_enough_for_two_lines(self, view: ScheduleGridView) -> None:
        assert view._table.horizontalHeader().sizeHint().height() == METRICS.lane_header_height

    def test_every_trade_has_a_word_for_it(self) -> None:
        names = {profession: trade_name(profession) for profession in Profession}
        assert set(names) == set(Profession)
        assert all(name.islower() for name in names.values())

    def test_it_follows_a_theme_change(self, view: ScheduleGridView) -> None:
        view.apply_palette(DARK)

        assert view._lane_header._palette is DARK


class TestLegend:
    def test_the_colours_are_spelled_out(self, view: ScheduleGridView) -> None:
        """Nothing else on the screen says what red means."""
        written = " ".join(label.text() for label in view._legend_strip.findChildren(QLabel))

        for meaning in ("brak magistra", "poza otwarciem", "święto", "zamknięte"):
            assert meaning in written

    def test_the_way_to_type_hours_is_shown_too(self, view: ScheduleGridView) -> None:
        written = " ".join(label.text() for label in view._legend_strip.findChildren(QLabel))

        assert "10-15" in written
