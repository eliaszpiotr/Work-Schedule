from dataclasses import dataclass
from datetime import time

from PySide6.QtCore import Qt, QTime
from PySide6.QtWidgets import QHBoxLayout, QTimeEdit, QVBoxLayout, QWidget

from work_scheduler.i18n import t, weekday_name
from work_scheduler.services import DEFAULT_WEEK, DayHours
from work_scheduler.ui.components import PlainLabel, Switch, inset_divider
from work_scheduler.ui.theme import METRICS

TIME_FORMAT = "HH:mm"


def _to_qtime(value: time | None) -> QTime:
    return QTime(value.hour, value.minute) if value else QTime(8, 0)


def _from_qtime(value: QTime) -> time:
    return time(value.hour(), value.minute())


@dataclass(slots=True)
class DayRow:
    """The controls describing one weekday, kept together for the tests."""

    open_switch: Switch
    opens: QTimeEdit
    closes: QTimeEdit
    closed_label: PlainLabel


class OpeningHoursEditor(QWidget):
    """Seven rows of opening times. Shared by the settings screen and the wizard.

    ``inset`` pads each row and starts the dividers where the text does; the settings
    card asks for it, the wizard leaves it at zero to line up with its own form.
    """

    def __init__(self, week: list[DayHours] | None = None, *, inset: int = 0) -> None:
        super().__init__()
        self.rows: list[DayRow] = []
        self._hour_parts: list[tuple[QWidget, ...]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        for weekday in range(7):
            if weekday:
                layout.addWidget(inset_divider(inset))
            self.rows.append(self._build_row(layout, weekday_name(weekday), inset))

        self.set_week(list(week or DEFAULT_WEEK))

    def _build_row(self, layout: QVBoxLayout, name: str, inset: int) -> DayRow:
        line = QWidget()
        row = QHBoxLayout(line)
        row.setContentsMargins(inset, METRICS.space_2, inset, METRICS.space_2)
        row.setSpacing(METRICS.space_3)

        label = PlainLabel(name.capitalize())
        label.setMinimumWidth(METRICS.weekday_label_width)
        open_switch = Switch(f"{name}{t('hours.open_suffix')}")

        opens, closes = QTimeEdit(), QTimeEdit()
        for field, role in ((opens, t("wizard.from")), (closes, t("hours.close_label"))):
            field.setDisplayFormat(TIME_FORMAT)
            field.setAccessibleName(f"{name} {role}")
            field.setFixedWidth(METRICS.time_field_width)
        separator = PlainLabel("–")
        separator.setObjectName("mutedText")
        closed = PlainLabel(t("grid.closed"))
        closed.setObjectName("mutedText")

        # A closed day says so in words; empty, greyed time fields only look broken.
        for widget in (opens, separator, closes):
            open_switch.toggled.connect(widget.setEnabled)
            open_switch.toggled.connect(widget.setVisible)
        open_switch.toggled.connect(lambda on: closed.setVisible(not on))

        row.addWidget(label)
        row.addWidget(open_switch, alignment=Qt.AlignmentFlag.AlignVCenter)
        row.addStretch(1)
        row.addWidget(closed)
        row.addWidget(opens)
        row.addWidget(separator)
        row.addWidget(closes)
        # Holds its height when the fields hide, so closing a day does not shift the rows.
        line.setMinimumHeight(opens.sizeHint().height() + 2 * METRICS.space_2)
        layout.addWidget(line)
        self._hour_parts.append((opens, separator, closes))
        return DayRow(open_switch, opens, closes, closed)

    def set_week(self, week: list[DayHours]) -> None:
        for day in sorted(week, key=lambda day: day.weekday):
            row = self.rows[day.weekday]
            row.open_switch.setChecked(not day.closed)
            # toggled does not fire when the state is already right; sync explicitly.
            for widget in self._hour_parts[day.weekday]:
                widget.setEnabled(not day.closed)
                widget.setVisible(not day.closed)
            row.closed_label.setVisible(day.closed)
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
            return t("hours.closed_all_week")

        hours = {(day.opens, day.closes) for day in open_days}
        if len(hours) == 1:
            opens, closes = next(iter(hours))
            return t("hours.summary", days=len(open_days), hours=f"{opens:%H:%M}–{closes:%H:%M}")
        return t("hours.summary_varied", days=len(open_days))
