import logging
from pathlib import Path

from PySide6.QtCore import QMarginsF
from PySide6.QtGui import QPageLayout, QPageSize, QPainter, QPdfWriter

from work_scheduler.export.pages import draw_grid, draw_person
from work_scheduler.export.paint import Sheet
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
    writer = QPdfWriter(str(path))
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageMargins(MARGINS, QPageLayout.Unit.Millimeter)
    writer.setResolution(RESOLUTION)
    writer.setTitle(f"{report.name} — grafik pracy")

    render(report, writer)
    logger.info("Wrote %s pages to %s", page_count(report), path)
    return path


def print_report(report: ScheduleReport, printer) -> None:  # noqa: ANN001 - QPrinter
    printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    printer.setPageMargins(MARGINS, QPageLayout.Unit.Millimeter)
    render(report, printer)
