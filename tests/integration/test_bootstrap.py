from pathlib import Path

import pytest
from sqlalchemy import inspect

import work_scheduler
from work_scheduler.config import DATABASE_PATH_ENV, AppConfig, default_database_path
from work_scheduler.database.base import Base
from work_scheduler.database.bootstrap import (
    MIGRATIONS_DIR,
    DatabaseUnavailableError,
    prepare_database,
)


class TestDatabaseLocation:
    def test_default_path_is_absolute(self) -> None:
        """A relative path would put the database wherever the app happened to start."""
        assert default_database_path().is_absolute()

    def test_environment_variable_wins(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(DATABASE_PATH_ENV, str(tmp_path / "elsewhere.db"))

        assert AppConfig().database_path == tmp_path / "elsewhere.db"


def test_migrations_live_inside_the_package() -> None:
    """Outside the package they would not ship with a wheel or a packaged build."""
    package_root = Path(work_scheduler.__file__).resolve().parent

    assert MIGRATIONS_DIR.is_relative_to(package_root)
    assert (MIGRATIONS_DIR / "env.py").is_file()
    assert list((MIGRATIONS_DIR / "versions").glob("*.py"))


class TestPrepareDatabase:
    def test_creates_the_file_and_every_table(self, tmp_path: Path) -> None:
        database_path = tmp_path / "nested" / "fresh.db"

        engine = prepare_database(database_path)
        tables = set(inspect(engine).get_table_names())
        engine.dispose()

        assert database_path.exists()
        assert set(Base.metadata.tables) <= tables

    def test_running_twice_is_harmless(self, tmp_path: Path) -> None:
        database_path = tmp_path / "twice.db"

        prepare_database(database_path).dispose()
        engine = prepare_database(database_path)
        engine.dispose()

        assert database_path.exists()

    def test_reports_a_readable_error_when_the_path_cannot_be_used(self, tmp_path: Path) -> None:
        blocker = tmp_path / "blocker"
        blocker.write_text("this is a file, not a directory")

        with pytest.raises(DatabaseUnavailableError):
            prepare_database(blocker / "impossible.db")
