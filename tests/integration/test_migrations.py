from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text

from work_scheduler.database.autogenerate import build_include_object
from work_scheduler.database.base import Base
from work_scheduler.database.bootstrap import alembic_config
from work_scheduler.database.session import create_database_engine


def _upgrade_to_head(database_path: Path) -> None:
    command.upgrade(alembic_config(database_path), "head")


def test_alembic_check_reports_nothing_to_do(database_path: Path) -> None:
    """Guards env.py itself: a dirty check means the next autogenerate is unsafe."""
    _upgrade_to_head(database_path)

    command.check(alembic_config(database_path))


def test_migration_creates_every_table(database_path: Path) -> None:
    _upgrade_to_head(database_path)

    engine = create_database_engine(database_path)
    tables = set(inspect(engine).get_table_names())
    engine.dispose()

    assert set(Base.metadata.tables) <= tables


def test_migration_matches_the_models(database_path: Path) -> None:
    """Fails when someone edits a model without writing a migration."""
    _upgrade_to_head(database_path)

    engine = create_database_engine(database_path)
    with engine.connect() as connection:
        migration_context = MigrationContext.configure(
            connection, opts={"include_object": build_include_object(Base.metadata)}
        )
        differences = compare_metadata(migration_context, Base.metadata)
    engine.dispose()

    assert differences == []


def test_enum_checks_reached_the_database(database_path: Path) -> None:
    _upgrade_to_head(database_path)

    engine = create_database_engine(database_path)
    with engine.connect() as connection:
        schema = "\n".join(
            row[0]
            for row in connection.execute(text("SELECT sql FROM sqlite_master WHERE type='table'"))
            if row[0]
        )
    engine.dispose()

    assert "CHECK (profession IN ('PHARMACIST', 'TECHNICIAN'))" in schema
    assert "CHECK (status IN ('DRAFT', 'FINAL', 'ARCHIVED'))" in schema


def test_rule_set_migration_preserves_existing_schedule_children(database_path: Path) -> None:
    """Adding schedule columns must not cascade-delete its existing contents."""
    config = alembic_config(database_path)
    command.upgrade(config, "b4d715a1c582")
    engine = create_database_engine(database_path)
    stamp = "2026-10-01 12:00:00"
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO employees "
                "(id, first_name, last_name, profession, active, created_at, updated_at) "
                "VALUES (1, 'Anna', 'Test', 'PHARMACIST', 1, :stamp, :stamp)"
            ),
            {"stamp": stamp},
        )
        connection.execute(
            text(
                "INSERT INTO schedules "
                "(id, name, start_date, end_date, status, created_at, updated_at) "
                "VALUES (1, 'Test', '2026-10-01', '2026-10-31', 'DRAFT', :stamp, :stamp)"
            ),
            {"stamp": stamp},
        )
        connection.execute(
            text(
                "INSERT INTO schedule_employees "
                "(id, schedule_id, employee_id, display_order) VALUES (1, 1, 1, 0)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO schedule_opening_hours "
                "(schedule_id, weekday, opens, closes) "
                "VALUES (1, :day, '08:00:00', '20:00:00')"
            ),
            [{"day": day} for day in range(7)],
        )
        connection.execute(
            text(
                "INSERT INTO shifts "
                "(schedule_employee_id, shift_date, start_time, end_time, created_at, updated_at) "
                "VALUES (1, '2026-10-01', '08:00:00', '16:00:00', :stamp, :stamp)"
            ),
            {"stamp": stamp},
        )
        connection.execute(
            text(
                "INSERT INTO absences "
                "(schedule_employee_id, absence_date, code, created_at, updated_at) "
                "VALUES (1, '2026-10-02', 'U', :stamp, :stamp)"
            ),
            {"stamp": stamp},
        )
    engine.dispose()

    command.upgrade(config, "head")
    engine = create_database_engine(database_path)
    with engine.connect() as connection:
        counts = {
            table: connection.scalar(text(f"SELECT COUNT(*) FROM {table}"))
            for table in (
                "schedules",
                "schedule_employees",
                "schedule_opening_hours",
                "shifts",
                "absences",
            )
        }
        rules = connection.scalar(text("SELECT rules FROM schedules WHERE id = 1"))
    engine.dispose()
    assert counts == {
        "schedules": 1,
        "schedule_employees": 1,
        "schedule_opening_hours": 7,
        "shifts": 1,
        "absences": 1,
    }
    assert rules == "[]"

    command.downgrade(config, "b4d715a1c582")
    engine = create_database_engine(database_path)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM schedule_employees")) == 1
        assert connection.scalar(text("SELECT COUNT(*) FROM schedule_opening_hours")) == 7
        assert connection.scalar(text("SELECT COUNT(*) FROM shifts")) == 1
        assert connection.scalar(text("SELECT COUNT(*) FROM absences")) == 1
    engine.dispose()
