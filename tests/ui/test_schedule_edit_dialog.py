from datetime import date, time

import pytest
from PySide6.QtCore import Qt, QTime
from sqlalchemy import Engine

from work_scheduler.database.models import Employee, Profession
from work_scheduler.database.session import create_session_factory
from work_scheduler.services import EmployeeService
from work_scheduler.ui.schedules.schedule_edit_dialog import DayHoursDialog, ScheduleTeamDialog
from work_scheduler.ui.theme import LIGHT


@pytest.fixture
def employees(engine: Engine) -> list[Employee]:
    service = EmployeeService(create_session_factory(engine))
    anna = service.create("Anna", "Kowalska", Profession.PHARMACIST)
    marek = service.create("Marek", "Nowak", Profession.TECHNICIAN)
    return [anna, marek]


class TestScheduleTeamDialog:
    def test_it_starts_with_the_current_team_selected(
        self, application, employees: list[Employee]
    ) -> None:
        dialog = ScheduleTeamDialog(None, employees, [employees[1].id], LIGHT)

        assert dialog.employee_ids == [employees[1].id]

    def test_it_requires_at_least_one_person(self, application, employees: list[Employee]) -> None:
        dialog = ScheduleTeamDialog(None, employees, [], LIGHT)

        assert dialog._save.isEnabled() is False

    def test_a_whole_row_toggles_the_person(self, application, employees: list[Employee]) -> None:
        dialog = ScheduleTeamDialog(None, employees, [], LIGHT)

        dialog._toggle_row(dialog._people.item(0))

        assert dialog.employee_ids == [employees[0].id]
        assert dialog._save.isEnabled()

    def test_an_inactive_current_member_can_still_be_retained(
        self, application, engine: Engine, employees: list[Employee]
    ) -> None:
        service = EmployeeService(create_session_factory(engine))
        inactive = service.set_active(employees[0].id, False)

        dialog = ScheduleTeamDialog(None, [inactive, employees[1]], [inactive.id], LIGHT)

        assert dialog._people.item(0).flags() & Qt.ItemFlag.ItemIsEnabled
        assert dialog.employee_ids == [inactive.id]


class TestDayHoursDialog:
    def test_it_returns_custom_hours(self, application) -> None:  # noqa: ANN001
        dialog = DayHoursDialog(
            None,
            date(2026, 8, 18),
            time(8),
            time(20),
            (time(8), time(20)),
        )
        dialog._opens.setTime(QTime(10, 0))
        dialog._closes.setTime(QTime(16, 30))

        assert dialog.hours == (time(10), time(16, 30))

    def test_a_day_can_be_closed(self, application) -> None:  # noqa: ANN001
        dialog = DayHoursDialog(
            None,
            date(2026, 8, 18),
            time(8),
            time(20),
            (time(8), time(20)),
        )
        dialog._open.setChecked(False)

        assert dialog.hours == (None, None)
        assert dialog._save.isEnabled()

    def test_backwards_hours_cannot_be_saved(self, application) -> None:  # noqa: ANN001
        dialog = DayHoursDialog(
            None,
            date(2026, 8, 18),
            time(8),
            time(20),
            (time(8), time(20)),
        )
        dialog._opens.setTime(QTime(16, 0))
        dialog._closes.setTime(QTime(10, 0))

        assert dialog._save.isEnabled() is False
        assert dialog._error.text()
