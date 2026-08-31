import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Everything this application writes — the database, its backups, an exported grafik —
# carries names and working hours of real people. Nobody else with an account on the
# machine has any business reading it, so the group and world bits come off.
DIRECTORY_MODE = 0o700
FILE_MODE = 0o600


def restrict(path: Path, mode: int) -> None:
    """Best effort: Windows has no POSIX modes and some filesystems refuse chmod."""
    if os.name == "nt":
        return
    try:
        path.chmod(mode)
    except OSError:
        logger.warning("Could not restrict permissions on %s", path)


def create_data_directory(path: Path) -> Path:
    """Make the directory private, but only when we are the ones creating it.

    A path can point at a directory that already exists — a home directory, even — and
    narrowing the permissions of something we did not make is a surprise nobody asked
    for.
    """
    existed = path.is_dir()
    path.mkdir(parents=True, exist_ok=True)
    if not existed:
        restrict(path, DIRECTORY_MODE)
    return path


def create_private_file(path: Path) -> Path:
    """An empty file that is already private before anything is written into it.

    Creating it first and letting the writer reopen it closes the window in which the
    file sits on disk with whatever the umask allows.
    """
    path.unlink(missing_ok=True)
    os.close(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, FILE_MODE))
    return path
