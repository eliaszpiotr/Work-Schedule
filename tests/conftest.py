import os

# Qt must run headless in tests; set before PySide6 is imported anywhere.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from collections.abc import Iterator  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from PySide6.QtCore import QSettings  # noqa: E402
from sqlalchemy import Engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from work_scheduler.database.base import Base  # noqa: E402
from work_scheduler.database.session import (  # noqa: E402
    create_database_engine,
    create_session_factory,
)
from work_scheduler.i18n import Language, current_language, set_language  # noqa: E402
from work_scheduler.main import create_application  # noqa: E402

TEST_CATEGORIES = {"unit", "integration", "ui"}


@pytest.fixture(scope="session", autouse=True)
def isolated_preferences(tmp_path_factory: pytest.TempPathFactory):
    """Tests must not inherit the language saved by the person running them."""
    previous_language = current_language()
    previous_format = QSettings.defaultFormat()
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat,
        QSettings.Scope.UserScope,
        str(tmp_path_factory.mktemp("preferences")),
    )
    set_language(Language.PL)
    yield
    set_language(previous_language)
    QSettings.setDefaultFormat(previous_format)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Give every test the marker matching its top-level test directory."""
    tests_root = Path(__file__).parent
    for item in items:
        relative = item.path.relative_to(tests_root)
        category = relative.parts[0]
        if category in TEST_CATEGORIES:
            item.add_marker(getattr(pytest.mark, category))


@pytest.fixture(scope="session")
def application(tmp_path_factory: pytest.TempPathFactory):
    """The single QApplication plus its main window, on a throwaway database."""
    engine = create_database_engine(tmp_path_factory.mktemp("app") / "app.db")
    Base.metadata.create_all(engine)

    app, window = create_application([], session_factory=create_session_factory(engine))
    yield app, window

    window.close()
    engine.dispose()


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    """A real file, so tests can close and reopen the database like the app does."""
    return tmp_path / "test.db"


@pytest.fixture
def engine(database_path: Path) -> Iterator[Engine]:
    engine = create_database_engine(database_path)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    factory = create_session_factory(engine)
    with factory() as session:
        yield session
