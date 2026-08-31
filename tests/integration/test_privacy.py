import os
import stat
import tempfile
import time as clock
from datetime import date, time, timedelta
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel
from sqlalchemy import Engine

from work_scheduler.database.base import utcnow
from work_scheduler.database.bootstrap import (
    BACKUPS_KEPT,
    back_up,
    backup_dir,
    existing_backups,
    prepare_database,
)
from work_scheduler.database.models import Profession, Schedule
from work_scheduler.database.session import create_session_factory
from work_scheduler.export import document as document_module
from work_scheduler.export import save_pdf
from work_scheduler.privacy import (
    DIRECTORY_MODE,
    FILE_MODE,
    create_data_directory,
    create_private_file,
)
from work_scheduler.services import DayHours, EmployeeService, ScheduleService
from work_scheduler.services.report import Person, ScheduleReport
from work_scheduler.services.schedule_service import DayInfo, days_between
from work_scheduler.ui.components import ConfirmDialog, PlainLabel
from work_scheduler.ui.resources import ICON_CACHE_DIR
from work_scheduler.ui.theme import LIGHT

posix_only = pytest.mark.skipif(os.name == "nt", reason="Windows has no POSIX file modes")

AUGUST = (date(2026, 8, 3), date(2026, 8, 9))
OPEN_ALL_WEEK = [DayHours(weekday, time(8), time(20)) for weekday in range(7)]


def mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


@posix_only
class TestFilesOthersCannotRead:
    """Names and working hours of real people; another account has no business in them."""

    def test_the_database_is_closed_to_other_accounts(self, tmp_path: Path) -> None:
        database_path = tmp_path / "grafiki.db"

        prepare_database(database_path).dispose()

        assert mode(database_path) == FILE_MODE

    def test_a_directory_we_create_is_private(self, tmp_path: Path) -> None:
        created = create_data_directory(tmp_path / "dane" / "glebiej")

        assert mode(created) == DIRECTORY_MODE

    def test_a_directory_that_was_already_there_is_left_alone(self, tmp_path: Path) -> None:
        """The path can point at a home directory, and narrowing that would be rude."""
        existing = tmp_path / "istnieje"
        existing.mkdir()
        existing.chmod(0o755)

        create_data_directory(existing)

        assert mode(existing) == 0o755

    def test_a_private_file_is_empty_and_closed_before_anything_is_written(
        self, tmp_path: Path
    ) -> None:
        created = create_private_file(tmp_path / "szkic")

        assert created.read_bytes() == b""
        assert mode(created) == FILE_MODE


class TestBackupsBeforeMigrations:
    """A batch migration rewrites whole tables, and the whole history is one file."""

    def test_a_first_start_has_nothing_to_copy(self, tmp_path: Path) -> None:
        assert back_up(tmp_path / "jeszcze-nie-istnieje.db") is None

    def test_the_second_start_copies_what_the_first_one_left(self, tmp_path: Path) -> None:
        database_path = tmp_path / "grafiki.db"
        prepare_database(database_path).dispose()

        prepare_database(database_path).dispose()

        assert len(existing_backups(database_path)) == 1

    def test_restarting_without_changes_does_not_pile_up_copies(self, tmp_path: Path) -> None:
        database_path = tmp_path / "grafiki.db"
        prepare_database(database_path).dispose()

        for _ in range(3):
            back_up(database_path)

        assert len(existing_backups(database_path)) == 1

    def test_a_changed_database_is_copied_again(self, tmp_path: Path) -> None:
        database_path = tmp_path / "grafiki.db"
        prepare_database(database_path).dispose()
        back_up(database_path)

        database_path.write_bytes(database_path.read_bytes() + b"cokolwiek")
        back_up(database_path)

        assert len(existing_backups(database_path)) == 2

    def test_only_the_last_few_copies_are_kept(self, tmp_path: Path) -> None:
        database_path = tmp_path / "grafiki.db"
        database_path.write_bytes(b"start")

        for index in range(BACKUPS_KEPT + 3):
            database_path.write_bytes(b"zmiana" * (index + 1))
            back_up(database_path)

        assert len(existing_backups(database_path)) == BACKUPS_KEPT

    def test_the_newest_copy_sorts_last(self, tmp_path: Path) -> None:
        """Rotation drops from the front, so the order of the names has to be the order
        the copies were taken in."""
        database_path = tmp_path / "grafiki.db"
        database_path.write_bytes(b"pierwsza")
        first = back_up(database_path)
        database_path.write_bytes(b"druga")
        second = back_up(database_path)

        assert existing_backups(database_path) == [first, second]

    @posix_only
    def test_the_copy_is_as_private_as_the_original(self, tmp_path: Path) -> None:
        database_path = tmp_path / "grafiki.db"
        database_path.write_bytes(b"dane")

        copy = back_up(database_path)

        assert copy is not None
        assert mode(copy) == FILE_MODE

    def test_the_copies_sit_beside_the_database(self, tmp_path: Path) -> None:
        assert backup_dir(tmp_path / "grafiki.db").parent == tmp_path


def report() -> ScheduleReport:
    days = days_between(*AUGUST)
    hours = (time(8), time(16))
    return ScheduleReport(
        name="Sierpień 2026",
        start_date=AUGUST[0],
        end_date=AUGUST[1],
        days=[DayInfo(day, hours[0], hours[1], None, False) for day in days],
        people=[
            Person(
                name="Nazwisko Imię",
                profession="magister",
                shifts=dict.fromkeys(days, hours),
                minutes=480 * len(days),
            )
        ],
    )


class TestExportedSchedule:
    """The printout carries the whole team's hours; it is not a public document."""

    @posix_only
    def test_the_pdf_is_closed_to_other_accounts(self, tmp_path: Path, application) -> None:  # noqa: ANN001 - the shared QApplication
        written = save_pdf(report(), tmp_path / "grafik.pdf")

        assert mode(written) == FILE_MODE

    def test_a_render_that_fails_leaves_no_file_under_the_chosen_name(
        self, tmp_path: Path, application, monkeypatch: pytest.MonkeyPatch
    ) -> None:  # noqa: ANN001 - the shared QApplication
        """Half a grafik under the right name is worse than no grafik at all: that is
        the file somebody prints and puts on the wall."""
        target = tmp_path / "grafik.pdf"

        def explode(*_args: object, **_kwargs: object) -> None:
            raise OSError("dysk pełny")

        monkeypatch.setattr(document_module, "render", explode)

        with pytest.raises(OSError):
            save_pdf(report(), target)

        assert not target.exists()
        assert list(tmp_path.iterdir()) == []


class TestNamesAreNotMarkup:
    """Qt renders a string as HTML when it looks like HTML, and every name here is typed
    in by hand."""

    def test_a_plain_label_never_interprets_what_it_is_given(self, application) -> None:  # noqa: ANN001
        assert PlainLabel("<b>x</b>").textFormat() == Qt.TextFormat.PlainText

    def test_a_confirmation_shows_a_surname_exactly_as_it_was_typed(self, application) -> None:  # noqa: ANN001 - the shared QApplication
        dialog = ConfirmDialog(
            None,
            "Usunąć pracownika?",
            "<img src=x>Kowalski Jan zniknie z kartoteki.",
            "Usuń",
            palette=LIGHT,
        )

        labels = dialog.findChildren(QLabel)

        assert labels
        assert all(label.textFormat() == Qt.TextFormat.PlainText for label in labels)


class TestIconCache:
    def test_the_cache_is_not_in_the_shared_temporary_directory(self) -> None:
        """On Linux /tmp is writable by every account and these names are predictable,
        so somebody else could leave their markup where a stylesheet reads ours."""
        assert not ICON_CACHE_DIR.is_relative_to(Path(tempfile.gettempdir()))


@pytest.fixture
def schedules(engine: Engine) -> ScheduleService:
    return ScheduleService(create_session_factory(engine))


@pytest.fixture
def employees(engine: Engine) -> EmployeeService:
    return EmployeeService(create_session_factory(engine))


@posix_only
def test_closing_a_schedule_is_stamped_in_utc(
    engine: Engine,
    schedules: ScheduleService,
    employees: EmployeeService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run in a timezone fourteen hours from UTC, a local-time stamp is off by a day's
    worth of hours from created_at sitting in the next column."""
    monkeypatch.setenv("TZ", "Pacific/Kiritimati")
    clock.tzset()
    try:
        person = employees.create("Jan", "Kowalski", Profession.PHARMACIST)
        summary = schedules.create("Sierpień", *AUGUST, [person.id], OPEN_ALL_WEEK)

        schedules.finalize(summary.id)

        with create_session_factory(engine)() as session:
            finalized_at = session.get(Schedule, summary.id).finalized_at

        assert finalized_at is not None
        assert abs(finalized_at - utcnow()) < timedelta(minutes=5)
    finally:
        monkeypatch.undo()
        clock.tzset()
