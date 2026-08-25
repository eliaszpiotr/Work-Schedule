from datetime import time

import pytest
from sqlalchemy import Engine

from work_scheduler.database.session import create_session_factory
from work_scheduler.services import DayHours, OpeningHoursService
from work_scheduler.ui.settings.opening_hours_editor import OpeningHoursEditor
from work_scheduler.ui.settings.settings_view import SettingsView
from work_scheduler.ui.theme import LIGHT

OPEN_ALL_WEEK = [DayHours(weekday, time(8), time(20)) for weekday in range(7)]


@pytest.fixture
def service(engine: Engine) -> OpeningHoursService:
    return OpeningHoursService(create_session_factory(engine))


@pytest.fixture
def editor(application) -> OpeningHoursEditor:
    return OpeningHoursEditor()


@pytest.fixture
def view(application, service: OpeningHoursService) -> SettingsView:
    return SettingsView(service, LIGHT)


class TestEditor:
    def test_it_has_a_row_for_every_weekday(self, editor: OpeningHoursEditor) -> None:
        editor.set_week(OPEN_ALL_WEEK)

        assert len(editor.week()) == 7

    def test_hours_survive_a_round_trip(self, editor: OpeningHoursEditor) -> None:
        editor.set_week([DayHours(0, time(9), time(17)), *OPEN_ALL_WEEK[1:]])

        assert editor.week()[0] == DayHours(0, time(9), time(17))

    def test_a_closed_day_comes_back_closed(self, editor: OpeningHoursEditor) -> None:
        editor.set_week([DayHours(0, None, None), *OPEN_ALL_WEEK[1:]])

        assert editor.week()[0].closed is True

    def test_closing_a_day_switches_its_hours_off(self, editor: OpeningHoursEditor) -> None:
        editor.set_week(OPEN_ALL_WEEK)
        editor.rows[0].open_switch.setChecked(False)

        assert editor.week()[0].closed is True
        assert editor.rows[0].opens.isEnabled() is False


class TestSettingsView:
    def test_it_opens_on_the_stored_week(
        self, view: SettingsView, service: OpeningHoursService
    ) -> None:
        assert view._editor.week() == service.week()

    def test_saving_keeps_the_change(
        self, view: SettingsView, service: OpeningHoursService
    ) -> None:
        view._editor.set_week([DayHours(0, time(9), time(17)), *OPEN_ALL_WEEK[1:]])
        view.save()

        assert service.week()[0].opens == time(9)

    def test_hours_in_the_wrong_order_are_not_saved(
        self, view: SettingsView, service: OpeningHoursService
    ) -> None:
        view._editor.set_week([DayHours(0, time(20), time(8)), *OPEN_ALL_WEEK[1:]])
        view.save()

        assert service.week()[0].opens == time(8)
