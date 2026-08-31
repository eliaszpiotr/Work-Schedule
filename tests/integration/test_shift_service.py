from datetime import date, time

import pytest
from sqlalchemy import Engine

from work_scheduler.database.models import Profession
from work_scheduler.database.session import create_session_factory
from work_scheduler.services import (
    DayHours,
    EmployeeService,
    ScheduleData,
    ScheduleService,
    ShiftService,
    ValidationError,
)

AUGUST = (date(2026, 8, 10), date(2026, 8, 23))
OPEN_ALL_WEEK = [DayHours(weekday, time(8), time(20)) for weekday in range(7)]


@pytest.fixture
def shifts(engine: Engine) -> ShiftService:
    return ShiftService(create_session_factory(engine))


@pytest.fixture
def schedule(engine: Engine) -> ScheduleData:
    factory = create_session_factory(engine)
    employees = EmployeeService(factory)
    anna = employees.create("Anna", "Kowalska", Profession.PHARMACIST)
    marek = employees.create("Marek", "Nowak", Profession.TECHNICIAN)

    service = ScheduleService(factory)
    created = service.create("Sierpień", *AUGUST, [anna.id, marek.id], OPEN_ALL_WEEK)
    return service.open_schedule(created.id)


class TestWriting:
    def test_a_shift_can_be_written_into_a_cell(
        self, shifts: ShiftService, schedule: ScheduleData
    ) -> None:
        lane = schedule.lanes[0].id
        shifts.set_shift(lane, date(2026, 8, 10), time(10), time(15))

        assert shifts.grid(schedule.id)[lane, date(2026, 8, 10)] == (time(10), time(15))

    def test_writing_again_replaces_the_old_hours(
        self, shifts: ShiftService, schedule: ScheduleData
    ) -> None:
        lane = schedule.lanes[0].id
        shifts.set_shift(lane, date(2026, 8, 10), time(10), time(15))
        shifts.set_shift(lane, date(2026, 8, 10), time(8), time(16))

        assert shifts.grid(schedule.id)[lane, date(2026, 8, 10)] == (time(8), time(16))
        assert len(shifts.grid(schedule.id)) == 1

    def test_clearing_a_cell_removes_the_shift(
        self, shifts: ShiftService, schedule: ScheduleData
    ) -> None:
        lane = schedule.lanes[0].id
        shifts.set_shift(lane, date(2026, 8, 10), time(10), time(15))
        shifts.clear_shift(lane, date(2026, 8, 10))

        assert shifts.grid(schedule.id) == {}

    def test_clearing_an_empty_cell_is_harmless(
        self, shifts: ShiftService, schedule: ScheduleData
    ) -> None:
        shifts.clear_shift(schedule.lanes[0].id, date(2026, 8, 10))

        assert shifts.grid(schedule.id) == {}

    def test_two_people_can_work_the_same_day(
        self, shifts: ShiftService, schedule: ScheduleData
    ) -> None:
        for lane in schedule.lanes:
            shifts.set_shift(lane.id, date(2026, 8, 10), time(10), time(15))

        assert len(shifts.grid(schedule.id)) == 2


class TestRefusals:
    def test_a_day_outside_the_period_is_refused(
        self, shifts: ShiftService, schedule: ScheduleData
    ) -> None:
        with pytest.raises(ValidationError):
            shifts.set_shift(schedule.lanes[0].id, date(2026, 9, 1), time(10), time(15))

    def test_ending_before_starting_is_refused(
        self, shifts: ShiftService, schedule: ScheduleData
    ) -> None:
        with pytest.raises(ValidationError):
            shifts.set_shift(schedule.lanes[0].id, date(2026, 8, 10), time(15), time(10))

    def test_an_unknown_column_is_refused(self, shifts: ShiftService) -> None:
        with pytest.raises(ValidationError):
            shifts.set_shift(999, date(2026, 8, 10), time(10), time(15))


class TestTotals:
    def test_a_column_without_shifts_totals_zero(
        self, shifts: ShiftService, schedule: ScheduleData
    ) -> None:
        assert shifts.totals(schedule.id) == {lane.id: 0 for lane in schedule.lanes}

    def test_hours_add_up_across_the_period(
        self, shifts: ShiftService, schedule: ScheduleData
    ) -> None:
        lane = schedule.lanes[0].id
        shifts.set_shift(lane, date(2026, 8, 10), time(10), time(15))
        shifts.set_shift(lane, date(2026, 8, 11), time(8), time(16))

        assert shifts.totals(schedule.id)[lane] == (5 + 8) * 60

    def test_half_hours_are_not_lost(self, shifts: ShiftService, schedule: ScheduleData) -> None:
        lane = schedule.lanes[0].id
        shifts.set_shift(lane, date(2026, 8, 10), time(8, 30), time(16))

        assert shifts.totals(schedule.id)[lane] == 450

    def test_each_column_is_counted_on_its_own(
        self, shifts: ShiftService, schedule: ScheduleData
    ) -> None:
        first, second = schedule.lanes
        shifts.set_shift(first.id, date(2026, 8, 10), time(8), time(16))
        shifts.set_shift(second.id, date(2026, 8, 10), time(10), time(15))

        assert shifts.totals(schedule.id) == {first.id: 480, second.id: 300}
