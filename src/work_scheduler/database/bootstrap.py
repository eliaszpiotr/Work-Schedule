import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine

from work_scheduler.database.session import create_database_engine, database_url

logger = logging.getLogger(__name__)

# Migrations live inside the package so they survive a wheel install, unlike a file
# sitting next to the repository checkout.
MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


class DatabaseUnavailableError(RuntimeError):
    """Raised when the database cannot be prepared; shown to the user as a message."""


def alembic_config(database_path: Path | str) -> Config:
    """Built in code rather than read from alembic.ini, which is not shipped."""
    if not (MIGRATIONS_DIR / "env.py").is_file():
        raise DatabaseUnavailableError(f"Brak plików migracji w {MIGRATIONS_DIR}")

    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.set_main_option("sqlalchemy.url", database_url(database_path))
    # The application already configured logging; env.py must not take it over.
    config.attributes["configure_logger"] = False
    return config


def upgrade_to_head(database_path: Path) -> None:
    Path(database_path).parent.mkdir(parents=True, exist_ok=True)
    command.upgrade(alembic_config(database_path), "head")


def prepare_database(database_path: Path) -> Engine:
    """Run outstanding migrations and hand back a ready engine."""
    logger.info("Preparing database at %s", database_path)
    try:
        upgrade_to_head(database_path)
        return create_database_engine(database_path)
    except DatabaseUnavailableError:
        raise
    except Exception as error:  # noqa: BLE001 - turned into a message for the user
        raise DatabaseUnavailableError(str(error)) from error
