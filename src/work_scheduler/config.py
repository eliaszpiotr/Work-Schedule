import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from work_scheduler import __version__

DATABASE_PATH_ENV = "WORK_SCHEDULER_DB"


def default_data_dir() -> Path:
    """Where the operating system expects an application to keep its own files."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "WorkScheduler"
    if os.name == "nt":
        # LOCALAPPDATA, not APPDATA: a SQLite file must not sit in a roaming profile.
        local = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        return Path(local or Path.home()) / "WorkScheduler"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share") / "work-scheduler"


def default_database_path() -> Path:
    """Absolute, so it does not depend on the directory the app was started from."""
    override = os.environ.get(DATABASE_PATH_ENV)
    if override:
        return Path(override).expanduser().resolve()
    return default_data_dir() / "work_scheduler.db"


@dataclass(frozen=True, slots=True)
class AppConfig:
    app_name: str = "Work Scheduler"
    organization_name: str = "Work Scheduler"
    version: str = __version__
    database_path: Path = field(default_factory=default_database_path)
