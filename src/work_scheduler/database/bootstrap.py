import logging
import shutil
from datetime import datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine

from work_scheduler.database.session import create_database_engine, database_url
from work_scheduler.privacy import FILE_MODE, create_data_directory, restrict

logger = logging.getLogger(__name__)

# Migrations live inside the package so they survive a wheel install, unlike a file
# sitting next to the repository checkout.
MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"

BACKUP_DIR_NAME = "backups"
BACKUPS_KEPT = 5


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


def backup_dir(database_path: Path) -> Path:
    return database_path.parent / BACKUP_DIR_NAME


def existing_backups(database_path: Path) -> list[Path]:
    """Newest last, which is the order the names sort in."""
    return sorted(backup_dir(database_path).glob(f"{database_path.stem}-*{database_path.suffix}"))


def _already_copied(database_path: Path, backups: list[Path]) -> bool:
    """Restarting the application twice without touching anything is not worth a copy."""
    if not backups:
        return False
    newest = backups[-1].stat()
    current = database_path.stat()
    return newest.st_size == current.st_size and newest.st_mtime_ns == current.st_mtime_ns


def prune_backups(database_path: Path, keep: int = BACKUPS_KEPT) -> None:
    for stale in existing_backups(database_path)[:-keep]:
        stale.unlink(missing_ok=True)


def back_up(database_path: Path, keep: int = BACKUPS_KEPT) -> Path | None:
    """A copy taken before migrations run.

    A batch migration rewrites whole tables, and the whole history of the pharmacy is
    one file. Returns the copy, or None when there was nothing to copy.
    """
    if not database_path.is_file():
        return None

    backups = existing_backups(database_path)
    if _already_copied(database_path, backups):
        return None

    create_data_directory(backup_dir(database_path))
    # Microseconds as well as seconds: two copies inside the same second would
    # otherwise land on one name, and the names are what put the copies in order.
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    target = backup_dir(database_path) / f"{database_path.stem}-{stamp}{database_path.suffix}"

    # copy2 keeps the modification time, which is what tells the next start that this
    # copy is still current.
    shutil.copy2(database_path, target)
    restrict(target, FILE_MODE)
    prune_backups(database_path, keep)

    logger.info("Backed up the database to %s", target)
    return target


def upgrade_to_head(database_path: Path) -> None:
    create_data_directory(Path(database_path).parent)
    back_up(Path(database_path))
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
        # The user gets somewhere to look; the technical detail belongs in the log,
        # which main() has already written through logger.exception.
        raise DatabaseUnavailableError(
            f"Nie udało się otworzyć bazy danych w {database_path}.\n"
            "Sprawdź, czy plik nie jest otwarty w innym programie i czy jest miejsce na dysku."
        ) from error
