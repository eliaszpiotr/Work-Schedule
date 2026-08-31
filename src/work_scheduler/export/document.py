import logging
import os
from pathlib import Path

from PySide6.QtCore import QMarginsF
from PySide6.QtGui import QPageLayout, QPageSize, QPainter, QPdfWriter

from work_scheduler.export.pages import draw_grid, draw_person
from work_scheduler.export.paint import Sheet
from work_scheduler.i18n import translate
from work_scheduler.privacy import create_private_file
from work_scheduler.services.report import ScheduleReport

logger = logging.getLogger(__name__)

RESOLUTION = 300
MARGINS = QMarginsF(12, 11, 12, 11)

# Everything prints sideways. A month is 31 rows and a full team is eight or more
# columns; upright, one of the two has to give, and the whole point is that the period
# fits on a single sheet. The calendar pages follow suit so the printer is set once.
ORIENTATION = QPageLayout.Orientation.Landscape


def page_count(report: ScheduleReport) -> int:
    """Two pages of grid, then one for each person."""
    return 2 + len(report.people)


def render(report: ScheduleReport, device) -> None:  # noqa: ANN001 - QPagedPaintDevice
    """Draw the whole document onto a paged device: a PDF file or a printer.

    Both are QPagedPaintDevice, so the printout and the file cannot drift apart.
    """
    device.setPageOrientation(ORIENTATION)

    painter = QPainter(device)
    try:
        sheet = Sheet.open(painter, device)
        draw_grid(sheet, report, totals=True)
        sheet.close()

        device.newPage()
        sheet = Sheet.open(painter, device)
        draw_grid(sheet, report, totals=False)
        sheet.close()

        for person in report.people:
            device.newPage()
            sheet = Sheet.open(painter, device)
            draw_person(sheet, report, person)
            sheet.close()
    finally:
        painter.end()


def save_pdf(report: ScheduleReport, path: Path) -> Path:
    """Drawn beside the target and moved into place when it is whole.

    A printer dialog cancelled halfway, a full disk, a crash: none of them may leave a
    half-drawn document sitting under the name the user picked, because that is the file
    somebody prints and hangs on the wall.
    """
    target = Path(path)
    scratch = target.with_name(f".{target.name}.part")
    create_private_file(scratch)

    try:
        writer = QPdfWriter(str(scratch))
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        writer.setPageMargins(MARGINS, QPageLayout.Unit.Millimeter)
        writer.setResolution(RESOLUTION)
        writer.setTitle(translate("export.document_name", report.language, name=report.name))

        render(report, writer)
        # Qt writes out the document when the writer is destroyed, so it has to go
        # before the file is moved.
        del writer

        os.replace(scratch, target)
    except Exception:
        scratch.unlink(missing_ok=True)
        raise

    logger.info("Wrote %s pages to %s", page_count(report), target)
    return target


def print_report(report: ScheduleReport, printer) -> None:  # noqa: ANN001 - QPrinter
    printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    printer.setPageMargins(MARGINS, QPageLayout.Unit.Millimeter)
    render(report, printer)
