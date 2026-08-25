from datetime import date, time

import pytest
from sqlalchemy import Engine

from work_scheduler.database.models import Profession
from work_scheduler.database.session import create_session_factory
from work_scheduler.services import DayHours, EmployeeService, ScheduleService, ShiftService
from work_scheduler.services.audit import Kind, audit

WEEK = (date(2026, 8, 10), date(2026, 8, 16))
OPEN_ALL_WEEK = [DayHours(weekday, time(8), time(20)) for weekday in range(7)]


@pytest.fixture
def factory(engine: Engine):  # noqa: ANN201 - sessionmaker
    return create_session_factory(engine)


@pytest.fixture
def schedules(factory) -> ScheduleService:  # noqa: ANN001
    return ScheduleService(factory)


@pytest.fixture
def shifts(factory) -> ShiftService:  # noqa: ANN001
    return ShiftService(factory)


@pytest.fixture
def staff(factory) -> list[int]:  # noqa: ANN001
    employees = EmployeeService(factory)
    return [
        employees.create("Anna", "Kowalska", Profession.PHARMACIST).id,
        employees.create("Marek", "Nowak", Profession.TECHNICIAN).id,
    ]


@pytest.fixture
def schedule_id(schedules: ScheduleService, staff: list[int]) -> int:
    return schedules.create("Sierpień", WEEK[0], WEEK[1], staff, OPEN_ALL_WEEK).id


def fill_week(schedules: ScheduleService, shifts: ShiftService, schedule_id: int) -> None:
    """Both people on every day, covering the whole of the opening hours."""
    data = schedules.open_schedule(schedule_id)
    for lane in data.lanes:
        for day in data.days():
            shifts.set_shift(lane.id, day, time(8), time(20))


def kinds(schedules: ScheduleService, shifts: ShiftService, schedule_id: int) -> list[Kind]:
    data = schedules.open_schedule(schedule_id)
    return [finding.kind for finding in audit(data, shifts.grid(schedule_id)).findings]


class TestEmptyDays:
    def test_an_open_day_with_nobody_on_it_is_a_problem(
        self, schedules: ScheduleService, shifts: ShiftService, schedule_id: int
    ) -> None:
        fill_week(schedules, shifts, schedule_id)
        data = schedules.open_schedule(schedule_id)
        for lane in data.lanes:
            shifts.clear_shift(lane.id, date(2026, 8, 12))

        result = audit(schedules.open_schedule(schedule_id), shifts.grid(schedule_id))
        assert [finding.kind for finding in result.problems] == [Kind.EMPTY_DAY]
        assert "12.08" in result.problems[0].text

    def test_a_closed_day_with_nobody_on_it_is_not(
        self, schedules: ScheduleService, shifts: ShiftService, staff: list[int]
    ) -> None:
        week = [*OPEN_ALL_WEEK[:2], DayHours(2, None, None), *OPEN_ALL_WEEK[3:]]
        schedule_id = schedules.create("Sierpień", WEEK[0], WEEK[1], staff, week).id
        fill_week(schedules, shifts, schedule_id)

        assert Kind.EMPTY_DAY not in kinds(schedules, shifts, schedule_id)

    def test_every_empty_day_is_named_in_one_finding(
        self, schedules: ScheduleService, shifts: ShiftService, schedule_id: int
    ) -> None:
        data = schedules.open_schedule(schedule_id)
        shifts.set_shift(data.lanes[0].id, date(2026, 8, 10), time(8), time(20))

        result = audit(schedules.open_schedule(schedule_id), shifts.grid(schedule_id))
        assert len(result.problems) == 1
        assert "16.08" in result.problems[0].text


class TestOtherFindings:
    def test_a_gap_in_pharmacist_cover_is_a_note_not_a_problem(
        self, schedules: ScheduleService, shifts: ShiftService, schedule_id: int
    ) -> None:
        data = schedules.open_schedule(schedule_id)
        pharmacist, technician = data.lanes
        for day in data.days():
            shifts.set_shift(pharmacist.id, day, time(8), time(14))
            shifts.set_shift(technician.id, day, time(8), time(20))

        result = audit(schedules.open_schedule(schedule_id), shifts.grid(schedule_id))
        assert result.problems == []
        assert {finding.kind for finding in result.notes} == {Kind.NO_PHARMACIST}

    def test_hours_reaching_past_the_opening_are_reported(
        self, schedules: ScheduleService, shifts: ShiftService, schedule_id: int
    ) -> None:
        fill_week(schedules, shifts, schedule_id)
        data = schedules.open_schedule(schedule_id)
        shifts.set_shift(data.lanes[0].id, date(2026, 8, 11), time(6), time(20))

        outside = [
            finding
            for finding in audit(data, shifts.grid(schedule_id)).findings
            if finding.kind is Kind.OUTSIDE_HOURS
        ]
        assert len(outside) == 1
        assert "Kowalska Anna" in outside[0].text

    def test_a_person_with_no_shifts_at_all_is_reported(
        self, schedules: ScheduleService, shifts: ShiftService, schedule_id: int
    ) -> None:
        data = schedules.open_schedule(schedule_id)
        for day in data.days():
            shifts.set_shift(data.lanes[0].id, day, time(8), time(20))

        idle = [
            finding
            for finding in audit(data, shifts.grid(schedule_id)).findings
            if finding.kind is Kind.IDLE_PERSON
        ]
        assert len(idle) == 1
        assert "Nowak Marek" in idle[0].text

    def test_a_full_week_raises_nothing(
        self, schedules: ScheduleService, shifts: ShiftService, schedule_id: int
    ) -> None:
        fill_week(schedules, shifts, schedule_id)
        assert audit(schedules.open_schedule(schedule_id), shifts.grid(schedule_id)).clean


class TestBlocking:
    def test_only_an_empty_day_stands_in_the_way(
        self, schedules: ScheduleService, shifts: ShiftService, schedule_id: int
    ) -> None:
        data = schedules.open_schedule(schedule_id)
        shifts.set_shift(data.lanes[1].id, date(2026, 8, 10), time(6), time(21))

        result = audit(schedules.open_schedule(schedule_id), shifts.grid(schedule_id))
        assert {finding.kind for finding in result.problems} == {Kind.EMPTY_DAY}
        assert Kind.OUTSIDE_HOURS in {finding.kind for finding in result.notes}
        assert Kind.NO_PHARMACIST in {finding.kind for finding in result.notes}
