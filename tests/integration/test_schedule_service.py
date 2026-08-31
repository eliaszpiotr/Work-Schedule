from datetime import date, time

import pytest
from sqlalchemy import Engine

from work_scheduler.database.models import Profession, ScheduleStatus
from work_scheduler.database.session import create_session_factory
from work_scheduler.services import (
    ConflictError,
    DayHours,
    EmployeeService,
    ScheduleService,
    ShiftService,
    ValidationError,
)
from work_scheduler.services.schedule_service import days_between

AUGUST = (date(2026, 8, 10), date(2026, 8, 23))
OPEN_ALL_WEEK = [DayHours(weekday, time(8), time(20)) for weekday in range(7)]


@pytest.fixture
def employees(engine: Engine) -> EmployeeService:
    return EmployeeService(create_session_factory(engine))


@pytest.fixture
def service(engine: Engine) -> ScheduleService:
    return ScheduleService(create_session_factory(engine))


@pytest.fixture
def staff(employees: EmployeeService) -> list[int]:
    anna = employees.create("Anna", "Kowalska", Profession.PHARMACIST)
    marek = employees.create("Marek", "Nowak", Profession.TECHNICIAN)
    return [anna.id, marek.id]


def make(service: ScheduleService, staff: list[int], **overrides: object) -> int:
    values: dict[str, object] = {
        "name": "Sierpień",
        "start_date": AUGUST[0],
        "end_date": AUGUST[1],
        "employee_ids": staff,
        "week": OPEN_ALL_WEEK,
    }
    values.update(overrides)
    return service.create(**values).id  # type: ignore[arg-type]


class TestDaysBetween:
    def test_a_period_becomes_one_entry_per_day(self) -> None:
        assert days_between(date(2026, 8, 10), date(2026, 8, 12)) == [
            date(2026, 8, 10),
            date(2026, 8, 11),
            date(2026, 8, 12),
        ]

    def test_a_single_day_period_is_one_day(self) -> None:
        assert days_between(date(2026, 8, 10), date(2026, 8, 10)) == [date(2026, 8, 10)]

    def test_the_length_matches_the_period(self) -> None:
        assert len(days_between(date(2026, 8, 12), date(2026, 8, 31))) == 20


class TestCreating:
    def test_the_schedule_keeps_its_own_copy_of_the_opening_hours(
        self, service: ScheduleService, staff: list[int]
    ) -> None:
        schedule_id = make(service, staff)

        assert len(service.open_schedule(schedule_id).week) == 7

    def test_later_changes_to_the_settings_leave_it_alone(
        self, service: ScheduleService, staff: list[int]
    ) -> None:
        schedule_id = make(service, staff)
        settings_changed = [DayHours(weekday, time(6), time(10)) for weekday in range(7)]

        assert service.open_schedule(schedule_id).week[0].opens == time(8)
        assert settings_changed[0].opens == time(6)

    def test_the_chosen_people_become_columns_in_the_order_given(
        self, service: ScheduleService, staff: list[int]
    ) -> None:
        schedule_id = make(service, staff)

        assert [lane.name for lane in service.open_schedule(schedule_id).lanes] == [
            "Kowalska Anna",
            "Nowak Marek",
        ]

    def test_a_new_schedule_starts_as_a_draft(
        self, service: ScheduleService, staff: list[int]
    ) -> None:
        schedule_id = make(service, staff)

        assert service.open_schedule(schedule_id).status is ScheduleStatus.DRAFT

    def test_a_nameless_schedule_is_refused(
        self, service: ScheduleService, staff: list[int]
    ) -> None:
        with pytest.raises(ValidationError):
            make(service, staff, name="   ")

    def test_a_backwards_period_is_refused(
        self, service: ScheduleService, staff: list[int]
    ) -> None:
        with pytest.raises(ValidationError):
            make(service, staff, start_date=date(2026, 8, 23), end_date=date(2026, 8, 10))

    def test_a_schedule_without_anyone_is_refused(self, service: ScheduleService) -> None:
        with pytest.raises(ValidationError):
            make(service, [], employee_ids=[])

    def test_a_period_longer_than_a_year_is_refused(
        self, service: ScheduleService, staff: list[int]
    ) -> None:
        with pytest.raises(ValidationError):
            make(service, staff, start_date=date(2026, 1, 1), end_date=date(2030, 1, 1))

    def test_an_unknown_person_is_refused(self, service: ScheduleService, staff: list[int]) -> None:
        with pytest.raises(ValidationError):
            make(service, staff, employee_ids=[*staff, 999])


class TestHolidays:
    """15 August 2026 (Wniebowzięcie NMP) falls inside the August period."""

    HOLIDAY = date(2026, 8, 15)

    def test_a_holiday_is_closed_even_though_its_weekday_is_open(
        self, service: ScheduleService, staff: list[int]
    ) -> None:
        schedule = service.open_schedule(make(service, staff))

        assert schedule.day_info(self.HOLIDAY).closed is True

    def test_the_holiday_is_named(self, service: ScheduleService, staff: list[int]) -> None:
        schedule = service.open_schedule(make(service, staff))

        assert schedule.day_info(self.HOLIDAY).holiday == "Wniebowzięcie NMP"

    def test_an_ordinary_day_stays_open(self, service: ScheduleService, staff: list[int]) -> None:
        info = service.open_schedule(make(service, staff)).day_info(date(2026, 8, 14))

        assert info.closed is False
        assert info.holiday is None

    def test_a_holiday_can_be_declared_a_working_day(
        self, service: ScheduleService, staff: list[int]
    ) -> None:
        schedule_id = make(service, staff)
        service.override_day(schedule_id, self.HOLIDAY, time(9), time(14))

        info = service.open_schedule(schedule_id).day_info(self.HOLIDAY)
        assert info.closed is False
        assert info.opens == time(9)
        assert info.holiday == "Wniebowzięcie NMP", "nadal ma być widać, że to święto"

    def test_an_ordinary_day_can_be_closed(
        self, service: ScheduleService, staff: list[int]
    ) -> None:
        schedule_id = make(service, staff)
        service.override_day(schedule_id, date(2026, 8, 14), None, None)

        assert service.open_schedule(schedule_id).day_info(date(2026, 8, 14)).closed is True

    def test_clearing_the_exception_brings_back_the_default(
        self, service: ScheduleService, staff: list[int]
    ) -> None:
        schedule_id = make(service, staff)
        service.override_day(schedule_id, self.HOLIDAY, time(9), time(14))
        service.clear_override(schedule_id, self.HOLIDAY)

        assert service.open_schedule(schedule_id).day_info(self.HOLIDAY).closed is True

    def test_overriding_the_same_day_twice_replaces_the_first(
        self, service: ScheduleService, staff: list[int]
    ) -> None:
        schedule_id = make(service, staff)
        service.override_day(schedule_id, self.HOLIDAY, time(9), time(14))
        service.override_day(schedule_id, self.HOLIDAY, time(10), time(16))

        assert service.open_schedule(schedule_id).day_info(self.HOLIDAY).opens == time(10)

    def test_a_day_outside_the_period_is_refused(
        self, service: ScheduleService, staff: list[int]
    ) -> None:
        with pytest.raises(ValidationError):
            service.override_day(make(service, staff), date(2026, 9, 1), time(9), time(14))

    def test_backwards_hours_are_refused(self, service: ScheduleService, staff: list[int]) -> None:
        with pytest.raises(ValidationError):
            service.override_day(make(service, staff), self.HOLIDAY, time(14), time(9))

    def test_the_timeline_has_one_entry_per_day(
        self, service: ScheduleService, staff: list[int]
    ) -> None:
        timeline = service.open_schedule(make(service, staff)).timeline()

        assert len(timeline) == 14
        assert [info.day for info in timeline][:2] == [date(2026, 8, 10), date(2026, 8, 11)]


class TestChangingTheTeam:
    def test_a_person_can_be_added_without_replacing_existing_columns(
        self,
        engine: Engine,
        service: ScheduleService,
        staff: list[int],
        employees: EmployeeService,
    ) -> None:
        schedule_id = make(service, staff)
        before = service.open_schedule(schedule_id)
        extra = employees.create("Ewa", "Bąk", Profession.TECHNICIAN)

        service.update_employees(schedule_id, [*staff, extra.id])
        after = service.open_schedule(schedule_id)

        assert [lane.employee_id for lane in after.lanes] == [*staff, extra.id]
        assert [lane.id for lane in after.lanes[:2]] == [lane.id for lane in before.lanes]

    def test_removing_a_person_removes_only_that_columns_shifts(
        self, engine: Engine, service: ScheduleService, staff: list[int]
    ) -> None:
        schedule_id = make(service, staff)
        schedule = service.open_schedule(schedule_id)
        shifts = ShiftService(create_session_factory(engine))
        for lane in schedule.lanes:
            shifts.set_shift(lane.id, AUGUST[0], time(9), time(15))

        service.update_employees(schedule_id, [staff[1]])
        remaining = service.open_schedule(schedule_id).lanes[0]

        assert remaining.employee_id == staff[1]
        assert shifts.grid(schedule_id) == {(remaining.id, AUGUST[0]): (time(9), time(15))}

    def test_a_team_change_reopens_a_finished_schedule(
        self, service: ScheduleService, staff: list[int]
    ) -> None:
        schedule_id = make(service, staff)
        service.finalize(schedule_id)

        reopened = service.update_employees(schedule_id, [staff[1]])

        assert reopened is True
        assert service.open_schedule(schedule_id).status is ScheduleStatus.DRAFT

    def test_an_empty_replacement_is_refused_without_changing_the_team(
        self, service: ScheduleService, staff: list[int]
    ) -> None:
        schedule_id = make(service, staff)

        with pytest.raises(ValidationError):
            service.update_employees(schedule_id, [])

        assert [lane.employee_id for lane in service.open_schedule(schedule_id).lanes] == staff


class TestListing:
    def test_schedules_are_listed_newest_period_first(
        self, service: ScheduleService, staff: list[int]
    ) -> None:
        make(service, staff, name="Lipiec", start_date=date(2026, 7, 1), end_date=date(2026, 7, 31))
        make(service, staff)

        assert [row.name for row in service.list_schedules()] == ["Sierpień", "Lipiec"]

    def test_the_summary_counts_the_people(
        self, service: ScheduleService, staff: list[int]
    ) -> None:
        make(service, staff)

        assert service.list_schedules()[0].employee_count == 2

    def test_the_status_filter_narrows_the_list(
        self, service: ScheduleService, staff: list[int]
    ) -> None:
        make(service, staff)

        assert service.list_schedules(status=ScheduleStatus.DRAFT)
        assert service.list_schedules(status=ScheduleStatus.ARCHIVED) == []


class TestDeleting:
    def test_a_schedule_can_be_deleted(self, service: ScheduleService, staff: list[int]) -> None:
        service.delete(make(service, staff))

        assert service.list_schedules() == []

    def test_deleting_a_schedule_frees_its_people(
        self, service: ScheduleService, staff: list[int], employees: EmployeeService
    ) -> None:
        service.delete(make(service, staff))
        employees.delete(staff[0])

        assert len(employees.list_employees()) == 1

    def test_a_person_in_a_schedule_still_cannot_be_deleted(
        self, service: ScheduleService, staff: list[int], employees: EmployeeService
    ) -> None:
        make(service, staff)

        with pytest.raises(ConflictError):
            employees.delete(staff[0])
