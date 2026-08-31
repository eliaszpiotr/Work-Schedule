from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from sqlite3 import Connection as SQLiteConnection

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from work_scheduler.privacy import FILE_MODE, create_data_directory, restrict


def _enable_sqlite_foreign_keys(dbapi_connection: object, _record: object) -> None:
    """SQLite ignores foreign keys unless they are switched on per connection."""
    if not isinstance(dbapi_connection, SQLiteConnection):
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def _restrict_database_file(engine: Engine) -> None:
    """SQLite creates the file on the first connection, which is the first chance to
    take the group and world bits off it."""
    path = engine.url.database
    if path and path != ":memory:":
        restrict(Path(path), FILE_MODE)


def database_url(database_path: Path | str) -> str:
    return f"sqlite:///{database_path}"


def create_engine_for_url(url: str, *, echo: bool = False) -> Engine:
    engine = create_engine(url, echo=echo)
    event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    event.listen(engine, "first_connect", lambda *_: _restrict_database_file(engine))
    return engine


def create_database_engine(database_path: Path | str, *, echo: bool = False) -> Engine:
    """Build an engine for a SQLite file, or for ':memory:' in tests."""
    if database_path != ":memory:":
        create_data_directory(Path(database_path).parent)

    return create_engine_for_url(database_url(database_path), echo=echo)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def session_scope(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    """One user operation, one transaction. Rolls back on any failure."""
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
