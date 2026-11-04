"""The smallest main window must keep every screen usable."""

from datetime import date, time

import pytest
from PySide6.QtCore import QPoint, QSettings
from PySide6.QtWidgets import QApplication, QScrollArea
from sqlalchemy import Engine

from work_scheduler.config import AppConfig
from work_scheduler.database.models import Profession
from work_scheduler.database.session import create_session_factory
from work_scheduler.i18n import Language, current_language, set_language
from work_scheduler.services import DayHours, EmployeeService, ScheduleService
from work_scheduler.settings import Settings, ThemeMode
from work_scheduler.ui.main_window import MainWindow
from work_scheduler.ui.theme import METRICS, ThemeManager


@pytest.mark.parametrize("language", [Language.PL, Language.EN])
@pytest.mark.parametrize("collapsed", [False, True])
def test_all_main_screens_remain_usable_at_minimum_window_size(
    application,
    engine: Engine,
    database_path,
    tmp_path,
    language: Language,
    collapsed: bool,
) -> None:
    previous_language = current_language()
    settings = Settings(QSettings(str(tmp_path / "window.ini"), QSettings.Format.IniFormat))
    settings.language = language
    set_language(language)
    factory = create_session_factory(engine)
    window = MainWindow(
        AppConfig(database_path=database_path),
        factory,
        ThemeManager(ThemeMode.LIGHT),
        settings,
    )
    try:
        window.show()
        window.resize(1180, 900)
        QApplication.processEvents()
        window.resize(880, 560)
        window.set_sidebar_collapsed(collapsed)
        QApplication.processEvents()

        window._navigation.setCurrentRow(0)
        QApplication.processEvents()
        assert window._schedules._list._stack.height() > 200

        window._navigation.setCurrentRow(1)
        QApplication.processEvents()
        assert window._employees._stack.currentIndex() == 1
        assert window._employees._stack.height() > 200

        window._navigation.setCurrentRow(2)
        QApplication.processEvents()
        settings_page = window._settings_view
        settings_page.show_section("hours")
        QApplication.processEvents()
        scroller = settings_page.findChild(QScrollArea, "settingsScroll")
        editor = settings_page._editor
        assert scroller.horizontalScrollBar().maximum() == 0
        assert editor.height() >= editor.sizeHint().height()

        # The switch is the one control every row shows, open or closed.
        def top_of(widget) -> int:  # noqa: ANN001 - any row widget
            return widget.mapTo(editor, QPoint(0, 0)).y()

        for earlier, later in zip(editor.rows, editor.rows[1:], strict=False):
            switch = earlier.open_switch
            assert top_of(switch) + switch.height() <= top_of(later.open_switch)
        scroller.verticalScrollBar().setValue(scroller.verticalScrollBar().maximum())
        QApplication.processEvents()
        sunday = editor.rows[-1]
        last = sunday.closes if sunday.closes.isVisibleTo(editor) else sunday.closed_label
        assert last.mapTo(scroller.viewport(), QPoint(0, last.height())).y() <= (
            scroller.viewport().height()
        )

        people = EmployeeService(factory)
        pharmacist = people.create("Anna", "Kowalska", Profession.PHARMACIST)
        technician = people.create("Marek", "Nowak", Profession.TECHNICIAN)
        week = [DayHours(weekday, time(8), time(20)) for weekday in range(7)]
        schedule = ScheduleService(factory).create(
            "Sierpień",
            date(2026, 8, 1),
            date(2026, 8, 31),
            [pharmacist.id, technician.id],
            week,
        )
        window._navigation.setCurrentRow(1)
        QApplication.processEvents()
        assert window._employees._stack.currentIndex() == 0
        assert window._employees._table.height() > METRICS.employee_row_height

        window._navigation.setCurrentRow(0)
        QApplication.processEvents()
        assert window._schedules._list._cards.cards()
        window._schedules.open_schedule(schedule.id)
        QApplication.processEvents()
        grid = window._schedules._grid
        assert grid._table.viewport().height() >= METRICS.table_row_height
        assert grid._table.verticalScrollBar().maximum() > 0
        assert grid._totals_bar.geometry().top() >= grid._table.geometry().bottom()
        help_button = grid._absence_help
        assert help_button.mapTo(grid, QPoint(help_button.width(), 0)).x() <= grid.width()
        assert grid._more.mapTo(grid, QPoint(grid._more.width(), 0)).x() <= grid.width()
        assert grid._finish.mapTo(grid, QPoint(grid._finish.width(), 0)).x() <= grid.width()

        window.resize(1180, 900)
        window._navigation.setCurrentRow(2)
        QApplication.processEvents()
        assert editor.height() >= editor.sizeHint().height()
        assert scroller.horizontalScrollBar().maximum() == 0
    finally:
        window.close()
        set_language(previous_language)
