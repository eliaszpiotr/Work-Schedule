from datetime import date, time

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from work_scheduler.database.models import (
    Employee,
    OpeningHours,
    Profession,
    Schedule,
    ScheduleDayOverride,
    ScheduleEmployee,
    ScheduleOpeningHours,
    Shift,
)


def make_lane(session: Session) -> ScheduleEmployee:
    lane = ScheduleEmployee(
        schedule=Schedule(
            name="Sierpień", start_date=date(2026, 8, 10), end_date=date(2026, 8, 23)
        ),
        employee=Employee(
            first_name="Anna", last_name="Kowalska", profession=Profession.PHARMACIST
        ),
        display_order=0,
    )
    session.add(lane)
    session.flush()
    return lane


class TestOpeningHours:
    def test_a_day_can_be_open(self, session: Session) -> None:
        session.add(OpeningHours(weekday=0, opens=time(8), closes=time(20)))
        session.commit()

        assert session.query(OpeningHours).one().opens == time(8)

    def test_a_day_with_no_hours_is_closed(self, session: Session) -> None:
        session.add(OpeningHours(weekday=6))
        session.commit()

        assert session.query(OpeningHours).one().closed is True

    def test_the_same_weekday_cannot_be_described_twice(self, session: Session) -> None:
        session.add(OpeningHours(weekday=0, opens=time(8), closes=time(20)))
        session.commit()
        session.add(OpeningHours(weekday=0, opens=time(9), closes=time(17)))

        with pytest.raises(IntegrityError):
            session.commit()

    def test_closing_before_opening_is_refused(self, session: Session) -> None:
        session.add(OpeningHours(weekday=0, opens=time(20), closes=time(8)))

        with pytest.raises(IntegrityError):
            session.commit()

    def test_half_filled_hours_are_refused(self, session: Session) -> None:
        session.add(OpeningHours(weekday=0, opens=time(8)))

        with pytest.raises(IntegrityError):
            session.commit()


class TestScheduleOpeningHours:
    def test_a_schedule_carries_its_own_copy(self, session: Session) -> None:
        lane = make_lane(session)
        lane.schedule.opening_hours.append(
            ScheduleOpeningHours(weekday=0, opens=time(8), closes=time(20))
        )
        session.commit()

        assert session.query(ScheduleOpeningHours).one().schedule_id == lane.schedule_id

    def test_deleting_the_schedule_takes_its_hours_along(self, session: Session) -> None:
        lane = make_lane(session)
        lane.schedule.opening_hours.append(ScheduleOpeningHours(weekday=0))
        session.commit()

        session.delete(lane.schedule)
        session.commit()

        assert session.query(ScheduleOpeningHours).count() == 0

    def test_one_schedule_cannot_describe_a_weekday_twice(self, session: Session) -> None:
        lane = make_lane(session)
        session.add_all(
            [
                ScheduleOpeningHours(schedule_id=lane.schedule_id, weekday=0),
                ScheduleOpeningHours(schedule_id=lane.schedule_id, weekday=0),
            ]
        )

        with pytest.raises(IntegrityError):
            session.commit()


class TestDayOverrides:
    def test_a_single_date_can_be_given_its_own_hours(self, session: Session) -> None:
        lane = make_lane(session)
        session.add(
            ScheduleDayOverride(
                schedule_id=lane.schedule_id,
                day=date(2026, 8, 15),
                opens=time(10),
                closes=time(14),
            )
        )
        session.commit()

        assert session.query(ScheduleDayOverride).one().opens == time(10)

    def test_empty_hours_mean_the_day_is_closed(self, session: Session) -> None:
        lane = make_lane(session)
        session.add(ScheduleDayOverride(schedule_id=lane.schedule_id, day=date(2026, 8, 15)))
        session.commit()

        assert session.query(ScheduleDayOverride).one().closed is True

    def test_one_date_cannot_be_overridden_twice(self, session: Session) -> None:
        lane = make_lane(session)
        session.add_all(
            [
                ScheduleDayOverride(schedule_id=lane.schedule_id, day=date(2026, 8, 15)),
                ScheduleDayOverride(schedule_id=lane.schedule_id, day=date(2026, 8, 15)),
            ]
        )

        with pytest.raises(IntegrityError):
            session.commit()

    def test_half_filled_hours_are_refused(self, session: Session) -> None:
        lane = make_lane(session)
        session.add(
            ScheduleDayOverride(schedule_id=lane.schedule_id, day=date(2026, 8, 15), opens=time(10))
        )

        with pytest.raises(IntegrityError):
            session.commit()

    def test_deleting_the_schedule_takes_its_overrides_along(self, session: Session) -> None:
        lane = make_lane(session)
        session.add(ScheduleDayOverride(schedule_id=lane.schedule_id, day=date(2026, 8, 15)))
        session.commit()

        session.delete(lane.schedule)
        session.commit()

        assert session.query(ScheduleDayOverride).count() == 0


class TestOneShiftPerDay:
    def test_the_same_person_cannot_have_two_shifts_on_one_day(self, session: Session) -> None:
        lane = make_lane(session)
        session.add_all(
            [
                Shift(
                    schedule_employee_id=lane.id,
                    shift_date=date(2026, 8, 10),
                    start_time=time(8),
                    end_time=time(12),
                ),
                Shift(
                    schedule_employee_id=lane.id,
                    shift_date=date(2026, 8, 10),
                    start_time=time(16),
                    end_time=time(20),
                ),
            ]
        )

        with pytest.raises(IntegrityError):
            session.commit()

    def test_the_same_day_in_another_schedule_is_fine(self, session: Session) -> None:
        first = make_lane(session)
        second = make_lane(session)
        session.add_all(
            [
                Shift(
                    schedule_employee_id=first.id,
                    shift_date=date(2026, 8, 10),
                    start_time=time(8),
                    end_time=time(12),
                ),
                Shift(
                    schedule_employee_id=second.id,
                    shift_date=date(2026, 8, 10),
                    start_time=time(8),
                    end_time=time(12),
                ),
            ]
        )
        session.commit()

        assert session.query(Shift).count() == 2
