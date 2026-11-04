from datetime import date, time

import pytest
from PySide6.QtCore import QPoint, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics
from PySide6.QtWidgets import QApplication, QDialog, QFrame, QLabel, QLineEdit, QPushButton
from sqlalchemy import Engine

from work_scheduler.database.models import Profession
from work_scheduler.database.session import create_session_factory
from work_scheduler.i18n import Language, current_language, set_language
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
    CELL_KIND_ROLE,
    LaneHeader,
    ScheduleGridModel,
    ScheduleGridView,
    ShiftDelegate,
    absence_help_text,
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
    @pytest.mark.parametrize(
        ("typed", "expected"),
        [
            ("ZCh", "ZCh"),
            ("urlop", "U"),
            ("Wolne za nadgodziny", "WN"),
            ("Opieka nad dzieckiem", "OD"),
            ("sick leave", "ZCh"),
            ("vacation", "U"),
            ("overtime time off", "WN"),
            ("child care leave", "OD"),
            ("SL", "ZCh"),
            ("sl", "ZCh"),
            ("V", "U"),
            ("v", "U"),
            ("TO", "WN"),
            ("to", "WN"),
            ("CC", "OD"),
            ("cc", "OD"),
            ("TOIL", "WN"),
            ("CCL", "OD"),
        ],
    )
    def test_absence_codes_and_names_are_accepted(
        self,
        model: ScheduleGridModel,
        schedule: ScheduleData,
        shifts: ShiftService,
        typed: str,
        expected: str,
    ) -> None:
        index = model.index(0, 0)
        assert model.setData(index, typed)
        assert index.data() == expected
        assert shifts.absences(schedule.id)[schedule.lanes[0].id, date(2026, 8, 12)] == expected
        assert model.totals() == [0, 0]

    def test_absence_is_ignored_for_coverage(self, model: ScheduleGridModel) -> None:
        model.setData(model.index(0, 1), "8-20")
        model.setData(model.index(0, 0), "ZCh")
        assert date(2026, 8, 12) in {gap.day for gap in model.uncovered()}

    @pytest.mark.parametrize(
        ("polish", "english", "meaning"),
        [
            ("ZCh", "SL", "sick leave"),
            ("U", "V", "vacation"),
            ("WN", "TO", "time off in lieu"),
            ("OD", "CC", "child care leave"),
        ],
    )
    def test_existing_absence_uses_the_current_language_code(
        self,
        model: ScheduleGridModel,
        schedule: ScheduleData,
        shifts: ShiftService,
        polish: str,
        english: str,
        meaning: str,
    ) -> None:
        index = model.index(0, 0)
        model.setData(index, polish)
        before = current_language()
        try:
            set_language(Language.EN)
            assert index.data() == english
            assert index.data(Qt.ItemDataRole.EditRole) == english
            assert index.data(Qt.ItemDataRole.ToolTipRole) == f"{english} — {meaning}"
            model.setData(index, english)
            assert shifts.absences(schedule.id)[schedule.lanes[0].id, date(2026, 8, 12)] == polish
        finally:
            set_language(before)
        assert index.data() == polish

    def test_a_shift_is_a_work_pill(self, model: ScheduleGridModel) -> None:
        model.setData(model.index(0, 0), "10-15")

        assert model.index(0, 0).data(CELL_KIND_ROLE) == "work"

    def test_an_empty_cell_has_no_kind(self, model: ScheduleGridModel) -> None:
        assert model.index(0, 0).data(CELL_KIND_ROLE) is None

    def test_an_absence_keeps_its_stored_code_in_english(self, model: ScheduleGridModel) -> None:
        index = model.index(0, 0)
        model.setData(index, "ZCh")
        before = current_language()
        try:
            set_language(Language.EN)
            assert index.data(CELL_KIND_ROLE) == "ZCh"
            assert index.data() == "SL"
        finally:
            set_language(before)

    def test_a_day_without_a_pharmacist_is_orange(self, model: ScheduleGridModel) -> None:
        model.setData(model.index(0, 1), "8-20")

        colour = model.index(0, 0).data(Qt.ItemDataRole.BackgroundRole)
        assert colour == QColor(LIGHT.warning_surface)

    def test_hours_outside_opening_are_red(self, model: ScheduleGridModel) -> None:
        model.setData(model.index(0, 0), "6-15")

        colour = model.index(0, 0).data(Qt.ItemDataRole.BackgroundRole)
        assert colour == QColor(LIGHT.danger_surface)

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
        return image.pixelColor(rect.topLeft() + QPoint(2, 2)).name()

    def test_an_ordinary_cell_is_left_plain(self, view: ScheduleGridView) -> None:
        # Covering the whole opening leaves the row with nothing to complain about.
        view._model.setData(view._model.index(0, 0), "8-20")

        assert self.corner_colour(view, 0) == LIGHT.elevated.lower()

    def test_a_closed_day_is_shaded(self, view: ScheduleGridView) -> None:
        assert self.corner_colour(view, SUNDAY_ROW) == LIGHT.surface_active.lower()

    def test_hours_outside_opening_time_are_highlighted(self, view: ScheduleGridView) -> None:
        view._model.setData(view._model.index(0, 0), "6-15")

        assert self.corner_colour(view, 0) == LIGHT.danger_surface.lower()


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

    def test_the_holiday_row_is_painted_purple(self, view: ScheduleGridView) -> None:
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

        assert TestPainting.corner_colour(view, 0) == LIGHT.elevated.lower()

    def test_a_selected_cell_is_marked_by_a_border_instead(self, view: ScheduleGridView) -> None:
        view._table.setCurrentIndex(view._model.index(0, 0))

        image = view._table.viewport().grab().toImage()
        rect = view._table.visualRect(view._model.index(0, 0))
        edge = image.pixelColor(rect.center().x(), rect.top() + METRICS.pill_inset + 4).name()

        assert edge == LIGHT.accent.lower()


class TestNoTextClutter:
    def test_the_row_header_carries_only_the_date(self, view: ScheduleGridView) -> None:
        view._model.setData(view._model.index(0, 1), "8-20")

        assert view._model.headerData(0, Qt.Orientation.Vertical) == "śr 12.08"

    def test_the_missing_cover_does_not_show_hover_text(self, view: ScheduleGridView) -> None:
        view._model.setData(view._model.index(0, 1), "8-20")

        tip = view._model.headerData(0, Qt.Orientation.Vertical, Qt.ItemDataRole.ToolTipRole)
        assert tip is None

    def test_the_day_is_still_orange(self, view: ScheduleGridView) -> None:
        view._model.setData(view._model.index(0, 1), "8-20")

        assert TestPainting.corner_colour(view, 0) == LIGHT.warning_surface.lower()

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

    def test_there_are_no_vertical_rules_between_people(self, view: ScheduleGridView) -> None:
        assert self.every_internal_right_edge(view, 0) == {LIGHT.elevated.lower()}

    def test_a_filled_row_is_ruled_exactly_like_a_plain_one(self, view: ScheduleGridView) -> None:
        view._model.setData(view._model.index(0, 0), "8-20")

        assert self.every_internal_right_edge(view, 0) == self.every_internal_right_edge(view, 1)

    def test_a_closed_row_is_ruled_the_same_too(self, view: ScheduleGridView) -> None:
        assert self.every_internal_right_edge(view, SUNDAY_ROW) == {LIGHT.surface_active.lower()}

    def test_a_holiday_row_is_ruled_the_same_too(self, view: ScheduleGridView) -> None:
        assert self.every_internal_right_edge(view, HOLIDAY_ROW) == {LIGHT.holiday_surface.lower()}

    def test_the_last_cell_does_not_double_the_outside_frame(self, view: ScheduleGridView) -> None:
        last = view._model.columnCount() - 1
        assert self.right_edge(view, 0, last) == LIGHT.elevated.lower()

    def test_the_table_card_draws_no_outer_frame(self, view: ScheduleGridView) -> None:
        view.show()
        image = view._card.grab().toImage()
        middle_x, middle_y = image.width() // 2, image.height() // 2
        frame = LIGHT.border_strong.lower()

        assert image.pixelColor(middle_x, 0).name() != frame
        assert image.pixelColor(middle_x, image.height() - 1).name() != frame
        assert image.pixelColor(0, middle_y).name() != frame
        assert image.pixelColor(image.width() - 1, middle_y).name() != frame

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

    def test_the_totals_have_a_rule_on_top_only(self, view: ScheduleGridView) -> None:
        view.show()
        image = view._totals_bar.grab().toImage()
        rect = view._totals_bar.column_rect(0)

        assert image.pixelColor(round(rect.center().x()), 0).name() == LIGHT.border.lower()
        assert image.pixelColor(round(rect.right()), round(rect.center().y())).name() == (
            LIGHT.elevated.lower()
        )

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
    def test_question_mark_explains_every_code_on_hover(self, view: ScheduleGridView) -> None:
        view.show()
        assert view._absence_help.isVisible()
        assert view._absence_help.mapTo(view, QPoint(0, 0)).x() >= 0
        right_edge = view._absence_help.mapTo(view, QPoint(view._absence_help.width(), 0)).x()
        assert right_edge <= view.width()
        assert view._absence_help.text() == "?"
        for code, meaning in (
            ("ZCh", "zwolnienie lekarskie"),
            ("U", "urlop"),
            ("WN", "wolne za nadgodziny"),
            ("OD", "opieka nad dzieckiem"),
        ):
            assert f"{code} — {meaning}" in view._absence_help.toolTip()

    def test_question_mark_has_an_english_explanation(self) -> None:
        tooltip = absence_help_text(Language.EN)
        for code, meaning in (
            ("SL", "sick leave"),
            ("V", "vacation"),
            ("TO", "time off in lieu"),
            ("CC", "child care leave"),
        ):
            assert f"{code} — {meaning}" in tooltip

    def test_the_colours_are_spelled_out(self, view: ScheduleGridView) -> None:
        """Nothing else on the screen says what red means."""
        written = " ".join(label.text() for label in view._legend_strip.findChildren(QLabel))

        for meaning in ("brak magistra", "poza otwarciem", "święto", "zamknięte"):
            assert meaning in written

    def test_the_way_to_type_hours_is_shown_too(self, view: ScheduleGridView) -> None:
        written = " ".join(label.text() for label in view._legend_strip.findChildren(QLabel))

        assert "10-15" in written


def _close(a: QColor, b: str, tolerance: int = 8) -> bool:
    other = QColor(b)
    return all(
        abs(x - y) <= tolerance
        for x, y in ((a.red(), other.red()), (a.green(), other.green()), (a.blue(), other.blue()))
    )


def _settled(view: ScheduleGridView, width: int = 880, height: int = 560) -> None:
    view.resize(width, height)
    QApplication.processEvents()


def _cell_image(view: ScheduleGridView, row: int, column: int):
    _settled(view)
    image = view._table.viewport().grab().toImage()
    return image, view._table.visualRect(view._model.index(row, column))


class TestPills:
    def test_a_shift_is_drawn_as_a_blue_pill(self, view: ScheduleGridView) -> None:
        view._model.setData(view._model.index(0, 0), "8-20")
        image, rect = _cell_image(view, 0, 0)

        inside = image.pixelColor(rect.left() + METRICS.pill_inset + 6, rect.center().y())
        corner = image.pixelColor(rect.left() + 1, rect.top() + 1)
        assert _close(inside, LIGHT.work_surface)
        assert _close(corner, LIGHT.elevated)

    def test_a_long_name_is_elided(self, view: ScheduleGridView) -> None:
        font = QFont()
        font.setPointSizeF(12)
        metrics = QFontMetrics(font)
        elided = LaneHeader._elided("N" * 60, font, 120)

        assert elided.endswith("…")
        assert metrics.horizontalAdvance(elided) <= 120 - 12

    def test_ten_people_fit_the_smallest_window(
        self, application, engine: Engine, schedules: ScheduleService, shifts: ShiftService
    ) -> None:
        employees = EmployeeService(create_session_factory(engine))
        ids = [
            employees.create(f"Osoba{n}", "Testowa", Profession.PHARMACIST).id for n in range(10)
        ]
        created = schedules.create("Tłok", *PERIOD, ids, WEEK)
        grid = ScheduleGridView(
            schedules.open_schedule(created.id), schedules, shifts, LIGHT, employees=employees
        )
        for column in range(10):
            grid._model.setData(grid._model.index(0, column), "8-20")
        _settled(grid)
        bar = grid._table.horizontalScrollBar()
        last = grid._model.columnCount() - 1

        for column, position in ((0, 0), (last, bar.maximum())):
            bar.setValue(position)
            QApplication.processEvents()
            image = grid._table.viewport().grab().toImage()
            rect = grid._table.visualRect(grid._model.index(0, column))
            pill = ShiftDelegate._pill_rect(rect)

            assert QRectF(rect).contains(pill)
            assert pill.width() >= 40
            centre = image.pixelColor(round(pill.center().x()), round(pill.center().y() - 8))
            assert _close(centre, LIGHT.work_surface)

    def test_pills_follow_the_theme(self, view: ScheduleGridView) -> None:
        view._model.setData(view._model.index(0, 0), "8-20")
        view.apply_palette(DARK)
        image, rect = _cell_image(view, 0, 0)

        inside = image.pixelColor(rect.left() + METRICS.pill_inset + 6, rect.center().y())
        assert _close(inside, DARK.work_surface)

    def test_the_totals_bar_follows_the_theme(self, view: ScheduleGridView) -> None:
        view.apply_palette(DARK)
        _settled(view)
        image = view._totals_bar.grab().toImage()

        assert _close(image.pixelColor(image.width() - 2, 5), DARK.elevated, 2)


class TestHeader:
    def test_more_menu_holds_details_and_rules(self, view: ScheduleGridView) -> None:
        assert view._more_menu.actions() == [view._edit_details, view._edit_rules]

    def test_the_toolbar_has_one_primary_button(self, view: ScheduleGridView) -> None:
        bar = view.findChild(QFrame, "toolbar")
        primaries = [
            button
            for button in bar.findChildren(QPushButton)
            if button.property("variant") == "primary"
        ]
        assert primaries == [view._finish]

    def test_header_icons_follow_the_theme(self, view: ScheduleGridView) -> None:
        view.apply_palette(DARK)

        for button in (view._more, view._back):
            image = button.icon().pixmap(18, 18).toImage()
            assert any(
                _close(image.pixelColor(x, y), DARK.text_secondary)
                for x in range(image.width())
                for y in range(image.height())
                if image.pixelColor(x, y).alpha() > 200
            )


class TestFinalPolish:
    def test_the_card_rounds_its_corners_over_the_table(self, view: ScheduleGridView) -> None:
        view.resize(1180, 760)
        view.show()
        QApplication.processEvents()

        # A mask clips children, not the card's own grab, so look at the page around it.
        image = view.grab().toImage()
        radius = METRICS.radius_lg
        origin = view._card.mapTo(view, QPoint(0, 0))

        def near(colour: QColor) -> bool:
            return _close(colour, LIGHT.elevated)

        assert not near(image.pixelColor(origin.x() + 1, origin.y() + 1))
        assert near(image.pixelColor(origin.x() + radius, origin.y() + radius))

    def test_the_back_button_takes_no_focus_ring_on_open(self, view: ScheduleGridView) -> None:
        view.show()
        QApplication.processEvents()

        assert view._back.focusPolicy() == Qt.FocusPolicy.TabFocus
        assert view.focusWidget() is view._table

    def test_the_editor_sits_over_the_pill(self, view: ScheduleGridView) -> None:
        _settled(view)
        view.show()
        index = view._model.index(0, 0)
        view._table.setCurrentIndex(index)
        view._table.edit(index)

        editor = view._table.viewport().findChild(QLineEdit)
        pill = ShiftDelegate._pill_rect(view._table.visualRect(index)).toRect()
        assert editor is not None
        assert editor.geometry() == pill
