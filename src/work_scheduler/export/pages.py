from datetime import date, timedelta

from PySide6.QtCore import QPointF, QRectF

from work_scheduler.database.models import WEEKDAY_SHORT
from work_scheduler.export.paint import (
    CLOSED_FILL,
    HAIRLINE,
    HEADER_FILL,
    HOLIDAY_FILL,
    HOLIDAY_INK,
    INK,
    LEFT,
    MUTED,
    RIGHT,
    SATURDAY_FILL,
    SUNDAY_FILL,
    Sheet,
)
from work_scheduler.services.report import Person, ScheduleReport
from work_scheduler.services.schedule_service import DayInfo
from work_scheduler.services.time_text import format_hours, format_range
from work_scheduler.ui.text import people as count_people

MONTHS_IN = (
    "stycznia",
    "lutego",
    "marca",
    "kwietnia",
    "maja",
    "czerwca",
    "lipca",
    "sierpnia",
    "września",
    "października",
    "listopada",
    "grudnia",
)
MONTHS_SHORT = (
    "sty",
    "lut",
    "mar",
    "kwi",
    "maj",
    "cze",
    "lip",
    "sie",
    "wrz",
    "paź",
    "lis",
    "gru",
)

# The whole period has to land on one sheet, so nothing here may grow without limit.
MAX_ROW_HEIGHT = 26
MAX_CELL_HEIGHT = 86
DATE_COLUMN_SHARE = 0.13
TOTALS_BAR = 46
SATURDAY, SUNDAY = 5, 6


def day_fill(info: DayInfo):  # noqa: ANN201 - QColor or nothing
    """The background a day earns, on every page that draws days.

    Whether anyone works is not part of it. A free Thursday is an ordinary day with an
    empty box; shading it would say the pharmacy was shut, which it was not.
    """
    if info.holiday:
        return HOLIDAY_FILL
    if info.day.weekday() == SATURDAY:
        return SATURDAY_FILL
    if info.day.weekday() == SUNDAY:
        return SUNDAY_FILL
    if info.closed:
        return CLOSED_FILL
    return None


def open_runs(days: list[DayInfo]) -> list[tuple[int, int]]:
    """Stretches of rows the column rules may cross, as half-open index ranges.

    Only a holiday breaks a run, because only a holiday writes its name across the
    row. A shut Sunday keeps every line the other days have and says it is shut with
    its colour alone — a row missing its rules reads as a hole in the table.
    """
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for index, day in enumerate(days):
        if day.holiday:
            if start is not None:
                runs.append((start, index))
                start = None
        elif start is None:
            start = index
    if start is not None:
        runs.append((start, len(days)))
    return runs


def period_words(report: ScheduleReport) -> str:
    """The period as a person would say it: "25 sierpnia – 1 września 2026"."""
    start, end = report.start_date, report.end_date
    if (start.year, start.month) == (end.year, end.month):
        return f"{start.day}–{end.day} {MONTHS_IN[start.month - 1]} {start.year}"
    if start.year == end.year:
        return (
            f"{start.day} {MONTHS_IN[start.month - 1]} – "
            f"{end.day} {MONTHS_IN[end.month - 1]} {start.year}"
        )
    return report.period


def draw_grid(sheet: Sheet, report: ScheduleReport, *, totals: bool) -> None:
    """Days down the side, people across the top — the whole period on one sheet."""
    top = sheet.heading(
        report.name,
        f"{period_words(report)} · {count_people(len(report.people))}",
        f"Wygenerowano {date.today():%d.%m.%Y}" if totals else "",
    )

    columns = max(len(report.people), 1)
    reserved = 18
    head_units = 1.8 if totals else 1.2
    units = len(report.days) + head_units + (1.4 if totals else 0)
    row_height = min((sheet.height - top - reserved) / units, MAX_ROW_HEIGHT)
    head_height = row_height * head_units

    date_width = sheet.width * DATE_COLUMN_SHARE
    column = (sheet.width - date_width) / columns
    body_size = min(row_height * 0.62, 11)
    date_size = min(row_height * 0.6, 10.4)

    y = top
    sheet.fill(QRectF(0, y, sheet.width, head_height), HEADER_FILL)
    for index, person in enumerate(report.people):
        x = date_width + index * column
        if not totals:
            # The wall copy names people and nothing else: everyone reading it knows
            # who is a pharmacist, and the trade is only there for checking cover.
            sheet.shrunk_text(
                QRectF(x, y, column, head_height), person.name, sheet.font(11, bold=True)
            )
            continue

        box = QRectF(x, y, column, head_height * 0.58)
        sheet.shrunk_text(box, person.name, sheet.font(min(head_height * 0.34, 10.5), bold=True))
        sheet.text(
            QRectF(x, y + head_height * 0.55, column, head_height * 0.42),
            person.profession,
            sheet.font(min(head_height * 0.27, 8)),
            MUTED,
        )
    y += head_height
    sheet.rule(y)

    for day in report.days:
        row = QRectF(0, y, sheet.width, row_height)
        fill = day_fill(day)
        if fill is not None:
            sheet.fill(row, fill)

        ink = HOLIDAY_INK if day.holiday else INK
        sheet.text(
            QRectF(8, y, date_width * 0.58, row_height),
            f"{day.day:%d.%m}",
            sheet.font(date_size, bold=True),
            ink,
            LEFT,
        )
        sheet.text(
            QRectF(date_width * 0.58, y, date_width * 0.4, row_height),
            WEEKDAY_SHORT[day.day.weekday()],
            sheet.font(date_size * 0.86),
            HOLIDAY_INK if day.holiday else MUTED,
            LEFT,
        )

        if day.closed:
            # Only a holiday earns a word. A shut Sunday says so with its colour; a
            # label stretched across the columns pulls the table apart.
            if day.holiday:
                sheet.shrunk_text(
                    QRectF(date_width, y, sheet.width - date_width, row_height),
                    day.holiday,
                    sheet.font(min(body_size, 9.4)),
                    HOLIDAY_INK,
                )
        else:
            for index, person in enumerate(report.people):
                hours = person.shifts.get(day.day)
                if hours is None:
                    continue
                cell = QRectF(date_width + index * column, y, column, row_height)
                sheet.shrunk_text(cell, format_range(*hours), sheet.font(body_size))
        y += row_height
        sheet.rule(y)

    if totals:
        height = row_height * 1.4
        sheet.fill(QRectF(0, y, sheet.width, height), HEADER_FILL)
        sheet.rule(y, INK, 1.6)
        sheet.text(
            QRectF(8, y, date_width, height), "Razem", sheet.font(date_size, bold=True), INK, LEFT
        )
        for index, person in enumerate(report.people):
            sheet.text(
                QRectF(date_width + index * column, y, column, height),
                format_hours(person.minutes),
                sheet.font(min(body_size * 1.05, 11), bold=True),
            )
        y += height

    spans = [(top, top + head_height)]
    spans += [
        (top + head_height + first * row_height, top + head_height + last * row_height)
        for first, last in open_runs(report.days)
    ]
    if totals:
        spans.append((y - row_height * 1.4, y))

    for index in range(columns + 1):
        x = date_width + index * column
        for upper, lower in spans:
            sheet.painter.drawLine(QPointF(x, upper), QPointF(x, lower))


def draw_person(sheet: Sheet, report: ScheduleReport, person: Person) -> None:
    """One person's own sheet: a single run of weeks, whatever months it crosses.

    Nothing says what they do for a living — they know. The calendar carries straight
    through a month boundary, because the schedule is one stretch of time and splitting
    it into two calendars only makes the reader find their place twice.
    """
    top = sheet.heading(person.name, period_words(report), "")
    days = {info.day: info for info in report.days}

    monday = report.start_date - timedelta(days=report.start_date.weekday())
    weeks = (report.start_date.weekday() + len(report.days) + 6) // 7
    column = sheet.width / 7
    labels = 26
    available = sheet.height - top - labels - TOTALS_BAR
    cell_height = min(available / max(weeks, 1), MAX_CELL_HEIGHT)

    # A filled band, not a second heavy rule: one already sits under the heading, and
    # two dark lines a few points apart read as a collision even when nothing touches.
    y = top
    sheet.fill(QRectF(0, y, sheet.width, labels), HEADER_FILL)
    for index in range(7):
        sheet.text(
            QRectF(index * column, y, column, labels),
            WEEKDAY_SHORT[index].upper(),
            sheet.font(8.8, bold=True),
            MUTED,
        )
    y += labels

    for slot in range(weeks * 7):
        day = monday + timedelta(days=slot)
        if not report.start_date <= day <= report.end_date:
            continue
        rect = QRectF((slot % 7) * column, y + (slot // 7) * cell_height, column, cell_height)
        _calendar_cell(sheet, rect, day, person, days.get(day))

    y += weeks * cell_height + 16
    sheet.rule(y, INK, 1.6)
    sheet.text(QRectF(0, y + 8, sheet.width, 26), "Razem w okresie", sheet.font(10.4), MUTED, LEFT)
    sheet.text(
        QRectF(0, y + 4, sheet.width, 30),
        format_hours(person.minutes),
        sheet.font(15, bold=True),
        INK,
        RIGHT,
    )


def _calendar_cell(sheet: Sheet, rect: QRectF, day: date, person: Person, info) -> None:  # noqa: ANN001
    hours = person.shifts.get(day)
    holiday = info is not None and info.holiday
    fill = day_fill(info) if info is not None else None
    if fill is not None:
        sheet.fill(rect, fill)
    sheet.outline(rect, HAIRLINE)

    # The month is named only where it turns over, so a period reaching into September
    # reads as one run of days rather than as two calendars.
    number = f"{day.day} {MONTHS_SHORT[day.month - 1]}" if day.day == 1 else str(day.day)
    sheet.text(
        QRectF(rect.x() + 8, rect.y() + 4, rect.width() - 16, 18),
        number,
        sheet.font(9.4, bold=True),
        HOLIDAY_INK if holiday else MUTED,
        LEFT,
    )

    if hours is not None:
        start, end = hours
        sheet.shrunk_text(
            QRectF(rect.x(), rect.y() + rect.height() * 0.3, rect.width(), rect.height() * 0.42),
            format_range(start, end),
            sheet.font(min(rect.height() * 0.2, 13), bold=True),
        )
        sheet.text(
            QRectF(rect.x(), rect.y() + 4, rect.width() - 8, 18),
            format_hours(_minutes(hours)),
            sheet.font(8.2),
            MUTED,
            RIGHT,
        )
    elif holiday:
        sheet.shrunk_text(
            QRectF(rect.x() + 4, rect.y() + rect.height() * 0.34, rect.width() - 8, 18),
            info.holiday,
            sheet.font(8.6),
            HOLIDAY_INK,
        )


def _minutes(hours) -> int:  # noqa: ANN001 - a pair of times
    start, end = hours
    return (end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)
