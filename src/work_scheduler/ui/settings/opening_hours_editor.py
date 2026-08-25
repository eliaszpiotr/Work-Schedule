from dataclasses import dataclass
from datetime import time

from PySide6.QtCore import Qt, QTime
from PySide6.QtWidgets import QCheckBox, QGridLayout, QLabel, QTimeEdit, QWidget

from work_scheduler.database.models import WEEKDAY_NAMES
from work_scheduler.services import DEFAULT_WEEK, DayHours
from work_scheduler.ui.theme import METRICS

TIME_FORMAT = "HH:mm"


def _to_qtime(value: time | None) -> QTime:
    return QTime(value.hour, value.minute) if value else QTime(8, 0)


def _from_qtime(value: QTime) -> time:
    return time(value.hour(), value.minute())


@dataclass(slots=True)
class DayRow:
    """The three controls describing one weekday, kept together for the tests."""

    open_switch: QCheckBox
    opens: QTimeEdit
    closes: QTimeEdit


class OpeningHoursEditor(QWidget):
    """Seven rows of opening times. Shared by the settings screen and the wizard."""

    def __init__(self, week: list[DayHours] | None = None) -> None:
        super().__init__()
        self.rows: list[DayRow] = []

        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(METRICS.space_3)
        layout.setVerticalSpacing(METRICS.space_2)
        layout.setColumnStretch(4, 1)

        for weekday, name in enumerate(WEEKDAY_NAMES):
            self.rows.append(self._build_row(layout, weekday, name))

        self.set_week(list(week or DEFAULT_WEEK))

    def _build_row(self, layout: QGridLayout, weekday: int, name: str) -> DayRow:
        label = QLabel(name.capitalize())
        label.setMinimumWidth(METRICS.weekday_label_width)

        open_switch = QCheckBox("otwarte")
        open_switch.setAccessibleName(f"{name} otwarte")

        opens, closes = QTimeEdit(), QTimeEdit()
        for field, role in ((opens, "otwarcie"), (closes, "zamknięcie")):
            field.setDisplayFormat(TIME_FORMAT)
            field.setAccessibleName(f"{name} {role}")
            field.setFixedWidth(METRICS.time_field_width)

        separator = QLabel("–")
        separator.setObjectName("mutedText")

        open_switch.toggled.connect(opens.setEnabled)
        open_switch.toggled.connect(closes.setEnabled)
        open_switch.toggled.connect(separator.setEnabled)

        layout.addWidget(label, weekday, 0)
        layout.addWidget(open_switch, weekday, 1)
        layout.addWidget(opens, weekday, 2)
        layout.addWidget(separator, weekday, 3, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(closes, weekday, 4, alignment=Qt.AlignmentFlag.AlignLeft)
        return DayRow(open_switch, opens, closes)

    def set_week(self, week: list[DayHours]) -> None:
        for day in sorted(week, key=lambda day: day.weekday):
            row = self.rows[day.weekday]
            row.open_switch.setChecked(not day.closed)
            row.opens.setTime(_to_qtime(day.opens))
            row.closes.setTime(_to_qtime(day.closes) if day.closes else QTime(20, 0))

    def week(self) -> list[DayHours]:
        return [
            DayHours(
                weekday,
                _from_qtime(row.opens.time()) if row.open_switch.isChecked() else None,
                _from_qtime(row.closes.time()) if row.open_switch.isChecked() else None,
            )
            for weekday, row in enumerate(self.rows)
        ]

    def summary(self) -> str:
        """One line for the wizard, so it does not have to show the whole table."""
        open_days = [day for day in self.week() if not day.closed]
        if not open_days:
            return "Zamknięte przez cały tydzień"

        hours = {(day.opens, day.closes) for day in open_days}
        if len(hours) == 1:
            opens, closes = next(iter(hours))
            return f"{len(open_days)} dni w tygodniu, {opens:%H:%M}–{closes:%H:%M}"
        return f"{len(open_days)} dni w tygodniu, różne godziny"
