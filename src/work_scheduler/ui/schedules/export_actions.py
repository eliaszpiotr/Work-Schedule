import logging
from pathlib import Path

from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget

from work_scheduler.export import print_report, save_pdf
from work_scheduler.services import ScheduleService, ServiceError, ShiftService
from work_scheduler.services.report import ScheduleReport, build_report, suggested_filename

logger = logging.getLogger(__name__)

PDF_FILTER = "Dokument PDF (*.pdf)"


def build(schedules: ScheduleService, shifts: ShiftService, schedule_id: int) -> ScheduleReport:
    return build_report(schedules.open_schedule(schedule_id), shifts.grid(schedule_id))


def save_as_pdf(
    parent: QWidget | None,
    schedules: ScheduleService,
    shifts: ShiftService,
    schedule_id: int,
    *,
    path: Path | None = None,
) -> Path | None:
    """Ask where to put the file and write it. ``path`` skips the dialog, for tests."""
    try:
        report = build(schedules, shifts, schedule_id)
    except ServiceError as error:
        QMessageBox.warning(parent, "Nie udało się", str(error))
        return None

    if path is None:
        chosen, _ = QFileDialog.getSaveFileName(
            parent,
            "Zapisz grafik jako PDF",
            str(Path.home() / suggested_filename(report)),
            PDF_FILTER,
        )
        if not chosen:
            return None
        path = Path(chosen)

    # A file dialog may hand back a name without the extension, and a PDF without .pdf
    # opens in the wrong application on every system we care about.
    if path.suffix.lower() != ".pdf":
        path = path.with_suffix(".pdf")

    try:
        save_pdf(report, path)
    except OSError as error:
        logger.exception("Could not write %s", path)
        QMessageBox.warning(parent, "Nie udało się zapisać", str(error))
        return None
    return path


def send_to_printer(
    parent: QWidget | None,
    schedules: ScheduleService,
    shifts: ShiftService,
    schedule_id: int,
    *,
    printer: QPrinter | None = None,
) -> bool:
    """The same drawing, on paper. ``printer`` skips the system dialog, for tests."""
    try:
        report = build(schedules, shifts, schedule_id)
    except ServiceError as error:
        QMessageBox.warning(parent, "Nie udało się", str(error))
        return False

    if printer is None:
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setDocName(f"{report.name} — grafik pracy")
        if QPrintDialog(printer, parent).exec() != QPrintDialog.DialogCode.Accepted:
            return False

    print_report(report, printer)
    return True
