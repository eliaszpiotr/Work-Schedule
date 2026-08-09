from datetime import date, time
from pathlib import Path

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

from work_scheduler.database.models import (
    Employee,
    Profession,
    Schedule,
    ScheduleEmployee,
    ScheduleStatus,
    Shift,
)
from work_scheduler.database.session import create_database_engine, create_session_factory


def make_employee(**overrides: object) -> Employee:
    values: dict[str, object] = {
        "first_name": "Anna",
        "last_name": "Kowalska",
        "profession": Profession.PHARMACIST,
    }
    values.update(overrides)
    return Employee(**values)  # type: ignore[arg-type]


def make_schedule(**overrides: object) -> Schedule:
    values: dict[str, object] = {
        "name": "10-23 sierpnia",
        "start_date": date(2026, 8, 10),
        "end_date": date(2026, 8, 23),
    }
    values.update(overrides)
    return Schedule(**values)  # type: ignore[arg-type]


class TestPersistence:
    def test_data_survives_reopening_the_database(self, database_path: Path) -> None:
        engine = create_database_engine(database_path)
        from work_scheduler.database.base import Base

        Base.metadata.create_all(engine)

        with create_session_factory(engine)() as session:
            employee = make_employee()
            schedule = make_schedule()
            lane = ScheduleEmployee(schedule=schedule, employee=employee, display_order=0)
            lane.shifts.append(
                Shift(shift_date=date(2026, 8, 10), start_time=time(8), end_time=time(16))
            )
            session.add(lane)
            session.commit()
        engine.dispose()

        reopened = create_database_engine(database_path)
        with create_session_factory(reopened)() as session:
            stored = session.query(Shift).one()
            assert stored.shift_date == date(2026, 8, 10)
            assert stored.schedule_employee.employee.full_name == "Anna Kowalska"
            assert stored.schedule_employee.schedule.name == "10-23 sierpnia"
        reopened.dispose()

    def test_new_schedule_starts_as_draft(self, session: Session) -> None:
        schedule = make_schedule()
        session.add(schedule)
        session.commit()

        assert schedule.status is ScheduleStatus.DRAFT
        assert schedule.finalized_at is None

    def test_employee_is_active_by_default(self, session: Session) -> None:
        employee = make_employee()
        session.add(employee)
        session.commit()

        assert employee.active is True


class TestConstraints:
    def test_rejects_unknown_profession(self, session: Session) -> None:
        session.add(make_employee(profession="KIEROWNIK"))

        with pytest.raises((StatementError, IntegrityError)):
            session.commit()

    def test_rejects_schedule_ending_before_it_starts(self, session: Session) -> None:
        session.add(make_schedule(start_date=date(2026, 8, 23), end_date=date(2026, 8, 10)))

        with pytest.raises(IntegrityError):
            session.commit()

    def test_rejects_shift_ending_before_it_starts(self, session: Session) -> None:
        lane = ScheduleEmployee(schedule=make_schedule(), employee=make_employee())
        lane.shifts.append(
            Shift(shift_date=date(2026, 8, 10), start_time=time(16), end_time=time(8))
        )
        session.add(lane)

        with pytest.raises(IntegrityError):
            session.commit()

    def test_rejects_the_same_employee_twice_in_one_schedule(self, session: Session) -> None:
        employee = make_employee()
        schedule = make_schedule()
        session.add_all(
            [
                ScheduleEmployee(schedule=schedule, employee=employee),
                ScheduleEmployee(schedule=schedule, employee=employee),
            ]
        )

        with pytest.raises(IntegrityError):
            session.commit()


class TestForeignKeysAreEnforced:
    """SQLite ignores foreign keys unless the connection switches them on."""

    def test_pragma_is_on(self, engine: Engine) -> None:
        with engine.connect() as connection:
            assert connection.execute(text("PRAGMA foreign_keys")).scalar() == 1

    def test_rejects_shift_pointing_at_a_missing_lane(self, session: Session) -> None:
        with pytest.raises(IntegrityError, match="FOREIGN KEY"):
            session.execute(
                text(
                    "INSERT INTO shifts "
                    "(schedule_employee_id, shift_date, start_time, end_time, "
                    " created_at, updated_at) "
                    "VALUES (9999, '2026-08-10', '08:00', '16:00', "
                    " '2026-08-09 00:00', '2026-08-09 00:00')"
                )
            )


class TestDeletion:
    def test_deleting_a_schedule_removes_its_lanes_and_shifts(self, session: Session) -> None:
        lane = ScheduleEmployee(schedule=make_schedule(), employee=make_employee())
        lane.shifts.append(
            Shift(shift_date=date(2026, 8, 10), start_time=time(8), end_time=time(16))
        )
        session.add(lane)
        session.commit()

        session.delete(lane.schedule)
        session.commit()

        assert session.query(ScheduleEmployee).count() == 0
        assert session.query(Shift).count() == 0
        assert session.query(Employee).count() == 1

    def test_removing_an_employee_from_a_schedule_removes_their_shifts(
        self, session: Session
    ) -> None:
        schedule = make_schedule()
        lane = ScheduleEmployee(schedule=schedule, employee=make_employee())
        lane.shifts.append(
            Shift(shift_date=date(2026, 8, 10), start_time=time(8), end_time=time(16))
        )
        session.add(lane)
        session.commit()

        schedule.employees.remove(lane)
        session.commit()

        assert session.query(Shift).count() == 0
        assert session.query(Employee).count() == 1

    def test_refuses_to_delete_an_employee_used_in_a_schedule(self, session: Session) -> None:
        employee = make_employee()
        session.add(ScheduleEmployee(schedule=make_schedule(), employee=employee))
        session.commit()

        session.delete(employee)

        with pytest.raises(IntegrityError):
            session.commit()

    def test_deactivating_keeps_the_employee_and_their_history(self, session: Session) -> None:
        employee = make_employee()
        session.add(ScheduleEmployee(schedule=make_schedule(), employee=employee))
        session.commit()

        employee.active = False
        session.commit()

        assert session.query(Employee).one().active is False
        assert session.query(ScheduleEmployee).count() == 1
