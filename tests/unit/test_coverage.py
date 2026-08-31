from dataclasses import replace
from datetime import date, time

import pytest

from work_scheduler.database.models import Profession, ScheduleStatus
from work_scheduler.services import DayHours, Lane, ScheduleData
from work_scheduler.services.coverage import gaps, uncovered_days

OPEN = (time(8), time(20))

MAGISTER, TECHNIK = 1, 2
MONDAY, TUESDAY = date(2026, 8, 10), date(2026, 8, 11)


def test_nobody_working_leaves_the_whole_day_uncovered() -> None:
    assert gaps(*OPEN, []) == [(time(8), time(20))]


def test_one_shift_across_the_whole_day_leaves_nothing() -> None:
    assert gaps(*OPEN, [(time(8), time(20))]) == []


def test_a_late_start_leaves_a_gap_at_the_front() -> None:
    assert gaps(*OPEN, [(time(10), time(20))]) == [(time(8), time(10))]


def test_an_early_finish_leaves_a_gap_at_the_end() -> None:
    assert gaps(*OPEN, [(time(8), time(16))]) == [(time(16), time(20))]


def test_a_hole_between_two_shifts_is_found() -> None:
    assert gaps(*OPEN, [(time(8), time(12)), (time(14), time(20))]) == [(time(12), time(14))]


def test_shifts_that_touch_leave_no_hole() -> None:
    assert gaps(*OPEN, [(time(8), time(14)), (time(14), time(20))]) == []


def test_overlapping_shifts_are_merged() -> None:
    assert gaps(*OPEN, [(time(8), time(15)), (time(12), time(20))]) == []


def test_shifts_reaching_past_the_opening_hours_still_count() -> None:
    assert gaps(*OPEN, [(time(6), time(22))]) == []


def test_a_shift_entirely_outside_the_opening_hours_covers_nothing() -> None:
    assert gaps(*OPEN, [(time(20), time(22))]) == [(time(8), time(20))]


def test_shifts_given_out_of_order_are_handled() -> None:
    assert gaps(*OPEN, [(time(14), time(20)), (time(8), time(12))]) == [(time(12), time(14))]


def test_two_holes_are_both_reported() -> None:
    shifts = [(time(9), time(11)), (time(13), time(15))]

    assert gaps(*OPEN, shifts) == [
        (time(8), time(9)),
        (time(11), time(13)),
        (time(15), time(20)),
    ]


@pytest.fixture
def schedule() -> ScheduleData:
    """Two days, one pharmacist and one technician, open 8-20 every day."""
    return ScheduleData(
        id=1,
        name="Test",
        start_date=MONDAY,
        end_date=TUESDAY,
        status=ScheduleStatus.DRAFT,
        lanes=[
            Lane(MAGISTER, 10, "Kowalska Anna", Profession.PHARMACIST),
            Lane(TECHNIK, 11, "Nowak Marek", Profession.TECHNICIAN),
        ],
        week=[DayHours(weekday, time(8), time(20)) for weekday in range(7)],
        overrides={},
    )


class TestPharmacistCoverage:
    def test_a_day_nobody_is_on_yet_is_not_a_mistake(self, schedule: ScheduleData) -> None:
        assert uncovered_days(schedule, {}) == {}

    def test_a_pharmacist_across_the_whole_day_settles_it(self, schedule: ScheduleData) -> None:
        cells = {(MAGISTER, MONDAY): (time(8), time(20))}

        assert uncovered_days(schedule, cells) == {}

    def test_a_technician_alone_does_not_count(self, schedule: ScheduleData) -> None:
        cells = {(TECHNIK, MONDAY): (time(8), time(20))}
        found = uncovered_days(schedule, cells)

        assert list(found) == [MONDAY]
        assert found[MONDAY].whole_day

    def test_a_pharmacist_leaving_early_is_reported(self, schedule: ScheduleData) -> None:
        cells = {(MAGISTER, MONDAY): (time(8), time(16))}
        monday = uncovered_days(schedule, cells)[MONDAY]

        assert monday.intervals == [(time(16), time(20))]
        assert monday.whole_day is False

    def test_only_the_day_that_was_filled_in_is_judged(self, schedule: ScheduleData) -> None:
        cells = {(TECHNIK, MONDAY): (time(8), time(20))}

        assert TUESDAY not in uncovered_days(schedule, cells)

    def test_a_closed_day_is_not_a_problem(self, schedule: ScheduleData) -> None:
        closed = replace(schedule, overrides={MONDAY: (None, None)})
        cells = {(TECHNIK, MONDAY): (time(8), time(20))}

        assert uncovered_days(closed, cells) == {}

    def test_a_holiday_is_not_a_problem_either(self) -> None:
        holiday = date(2026, 8, 15)
        schedule = ScheduleData(
            id=1,
            name="Test",
            start_date=holiday,
            end_date=holiday,
            status=ScheduleStatus.DRAFT,
            lanes=[Lane(TECHNIK, 11, "Nowak Marek", Profession.TECHNICIAN)],
            week=[DayHours(weekday, time(8), time(20)) for weekday in range(7)],
            overrides={},
        )

        assert uncovered_days(schedule, {(TECHNIK, holiday): (time(8), time(20))}) == {}

    def test_the_shorter_hours_of_an_override_are_what_must_be_covered(
        self, schedule: ScheduleData
    ) -> None:
        shortened = replace(schedule, overrides={MONDAY: (time(10), time(14))})
        cells = {(MAGISTER, MONDAY): (time(10), time(14))}

        assert uncovered_days(shortened, cells) == {}

    def test_a_problem_names_just_the_missing_hours(self, schedule: ScheduleData) -> None:
        cells = {(MAGISTER, MONDAY): (time(8), time(16))}

        assert uncovered_days(schedule, cells)[MONDAY].hours == "16–20"

    def test_a_wholly_uncovered_day_says_so_plainly(self, schedule: ScheduleData) -> None:
        cells = {(TECHNIK, MONDAY): (time(8), time(20))}

        assert uncovered_days(schedule, cells)[MONDAY].hours == "cały dzień"
