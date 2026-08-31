from datetime import date, time

import pytest
from sqlalchemy import Engine

from work_scheduler.database.models import Profession
from work_scheduler.database.session import create_session_factory
from work_scheduler.services import (
    DayHours,
    EmployeeService,
    OpeningHoursService,
    ScheduleService,
    ShiftService,
)
from work_scheduler.ui.schedules.schedules_page import LIST_PAGE, SchedulesPage
from work_scheduler.ui.theme import DARK, LIGHT

WEEK = [DayHours(weekday, time(8), time(20)) for weekday in range(7)]


@pytest.fixture
def page(application, engine: Engine) -> SchedulesPage:
    factory = create_session_factory(engine)
    return SchedulesPage(
        ScheduleService(factory),
        EmployeeService(factory),
        OpeningHoursService(factory),
        ShiftService(factory),
        LIGHT,
    )


@pytest.fixture
def schedule_id(engine: Engine) -> int:
    factory = create_session_factory(engine)
    person = EmployeeService(factory).create("Anna", "Kowalska", Profession.PHARMACIST)
    created = ScheduleService(factory).create(
        "Sierpień", date(2026, 8, 12), date(2026, 8, 16), [person.id], WEEK
    )
    return created.id


def test_it_starts_on_the_list(page: SchedulesPage) -> None:
    assert page._stack.currentIndex() == LIST_PAGE


def test_opening_a_schedule_shows_its_grid(page: SchedulesPage, schedule_id: int) -> None:
    page.open_schedule(schedule_id)

    assert page._stack.currentIndex() != LIST_PAGE
    assert page._grid is not None
    assert page._grid._model.rowCount() == 5
    assert page._grid._edit_team.isEnabled()


def test_going_back_returns_to_the_list(page: SchedulesPage, schedule_id: int) -> None:
    page.open_schedule(schedule_id)
    page.close_grid()

    assert page._stack.currentIndex() == LIST_PAGE


def test_the_previous_grid_is_not_kept_around(page: SchedulesPage, schedule_id: int) -> None:
    page.open_schedule(schedule_id)
    page.close_grid()

    assert page._stack.count() == 1


def test_a_theme_change_reaches_the_open_grid(page: SchedulesPage, schedule_id: int) -> None:
    page.open_schedule(schedule_id)
    page.apply_palette(DARK)

    assert page._grid._palette is DARK
