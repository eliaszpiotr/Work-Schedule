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
