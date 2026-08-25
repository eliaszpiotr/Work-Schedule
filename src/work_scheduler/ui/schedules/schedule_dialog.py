from calendar import monthrange
from datetime import date

from PySide6.QtCore import QDate, QLocale, Qt
from PySide6.QtGui import QColor, QTextCharFormat
from PySide6.QtWidgets import (
    QCalendarWidget,
    QDateEdit,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from work_scheduler.database.models import Employee
from work_scheduler.services import DayHours
from work_scheduler.services.holidays import holidays_in, holidays_within
from work_scheduler.services.schedule_service import MAX_PERIOD_DAYS
from work_scheduler.ui.components import (
    PROFESSION_LABELS,
    primary_button,
    restyle,
    secondary_button,
)
from work_scheduler.ui.settings.opening_hours_editor import OpeningHoursEditor
from work_scheduler.ui.text import days as count_days
from work_scheduler.ui.text import people as count_people
from work_scheduler.ui.text import plural, word
from work_scheduler.ui.theme import LIGHT, METRICS, Palette

MONTHS = (
    "Styczeń",
    "Luty",
    "Marzec",
    "Kwiecień",
    "Maj",
    "Czerwiec",
    "Lipiec",
    "Sierpień",
    "Wrzesień",
    "Październik",
    "Listopad",
    "Grudzień",
)


def suggested_name(today: date) -> str:
    return f"{MONTHS[today.month - 1]} {today.year}"


def end_of_month(day: date) -> date:
    """Schedules are usually made for the rest of a month, so that is the starting guess."""
    return day.replace(day=monthrange(day.year, day.month)[1])


def _to_qdate(value: date) -> QDate:
    return QDate(value.year, value.month, value.day)


def _polish_calendar(field: QDateEdit, palette: Palette) -> None:
    """Month names in Polish, weeks from Monday, no week numbers, holidays in blue."""
    calendar = field.calendarWidget()
    calendar.setLocale(QLocale(QLocale.Language.Polish, QLocale.Country.Poland))
    calendar.setFirstDayOfWeek(Qt.DayOfWeek.Monday)
    calendar.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
    calendar.setGridVisible(False)

    marked = QTextCharFormat()
    marked.setBackground(QColor(palette.holiday_surface))
    today = date.today()
    # Enough years around today that scrolling the popup keeps showing them.
    for year in range(today.year - 1, today.year + 3):
        for day, name in holidays_in(year).items():
            marked.setToolTip(name)
            calendar.setDateTextFormat(_to_qdate(day), marked)


class ScheduleDialog(QDialog):
    """Everything a new schedule needs, in one window: too few fields to justify steps."""

    def __init__(
        self,
        parent: QWidget | None,
        employees: list[Employee],
        week: list[DayHours],
        today: date | None = None,
        palette: Palette = LIGHT,
    ) -> None:
        super().__init__(parent)
        today = today or date.today()
        self._palette = palette

        self.setWindowTitle("Nowy grafik")
        self.setModal(True)
        self.setMinimumWidth(METRICS.dialog_width)

        self._name = QLineEdit(suggested_name(today))
        self._start = QDateEdit(_to_qdate(today))
        self._end = QDateEdit(_to_qdate(end_of_month(today)))
        self._people = QListWidget()
        self._hours = OpeningHoursEditor(week)
        self._hours_summary = QLabel()
        self._customise = secondary_button("Dostosuj…")
        self._folded_height = 0
        self._summary = QLabel()
        self._save = primary_button("Utwórz grafik")

        self._fill_people(employees)
        self._build()
        self._refresh()

    # Construction -----------------------------------------------------------

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*(METRICS.space_6,) * 4)
        layout.setSpacing(METRICS.space_4)

        layout.addLayout(self._field("Nazwa", self._name))
        layout.addLayout(self._period_row())
        layout.addLayout(self._field("Kto pracuje w tym okresie", self._people))
        layout.addLayout(self._hours_row())

        self._summary.setObjectName("mutedText")
        layout.addWidget(self._summary)
        layout.addLayout(self._buttons())

        self._name.textChanged.connect(self._refresh)
        for field in (self._start, self._end):
            field.setDisplayFormat("dd.MM.yyyy")
            field.setCalendarPopup(True)
            field.dateChanged.connect(self._refresh)
            _polish_calendar(field, self._palette)
        self._people.itemChanged.connect(self._refresh)

    def _period_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(METRICS.space_3)
        row.addLayout(self._field("Od", self._start))
        row.addLayout(self._field("Do", self._end))
        row.addStretch()
        return row

    def _hours_row(self) -> QVBoxLayout:
        self._hours.setVisible(False)
        self._hours_summary.setObjectName("secondaryText")
        self._customise.setCheckable(True)
        self._customise.toggled.connect(self._show_hours)

        head = QHBoxLayout()
        head.setSpacing(METRICS.space_3)
        head.addWidget(self._hours_summary)
        head.addStretch()
        head.addWidget(self._customise)

        column = self._field("Godziny otwarcia", None)
        column.addLayout(head)
        column.addWidget(self._hours)
        return column

    def _buttons(self) -> QHBoxLayout:
        cancel = secondary_button("Anuluj")
        cancel.clicked.connect(self.reject)
        self._save.setDefault(True)
        self._save.clicked.connect(self.accept)

        row = QHBoxLayout()
        row.setSpacing(METRICS.space_2)
        row.addStretch()
        row.addWidget(cancel)
        row.addWidget(self._save)
        return row

    @staticmethod
    def _field(text: str, widget: QWidget | None) -> QVBoxLayout:
        column = QVBoxLayout()
        column.setSpacing(METRICS.space_2)

        label = QLabel(text)
        label.setObjectName("fieldLabel")
        column.addWidget(label)

        if widget is not None:
            label.setBuddy(widget)
            widget.setAccessibleName(text)
            column.addWidget(widget)
        return column

    def _fill_people(self, employees: list[Employee]) -> None:
        self._people.setMaximumHeight(METRICS.people_list_height)
        for employee in employees:
            item = QListWidgetItem(
                f"{employee.last_name} {employee.first_name}"
                f"  ·  {PROFESSION_LABELS[employee.profession]}"
            )
            item.setData(Qt.ItemDataRole.UserRole, employee.id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self._people.addItem(item)

    # State ------------------------------------------------------------------

    def _show_hours(self, shown: bool) -> None:
        """Qt grows a window to fit a revealed child but never shrinks it back.

        The height from before unfolding is remembered rather than recomputed, because
        the natural size hint is not what the window was actually sitting at.
        """
        if shown:
            self._folded_height = self.height()

        self._customise.setText("Zwiń" if shown else "Dostosuj…")
        self._hours.setVisible(shown)
        self.layout().activate()

        target = self.sizeHint().height() if shown else self._folded_height
        self.resize(self.width(), target)

    def select_all(self) -> None:
        for row in range(self._people.count()):
            self._people.item(row).setCheckState(Qt.CheckState.Checked)

    @property
    def name(self) -> str:
        return self._name.text()

    @property
    def start_date(self) -> date:
        return self._start.date().toPython()

    @property
    def end_date(self) -> date:
        return self._end.date().toPython()

    @property
    def employee_ids(self) -> list[int]:
        """In list order, so the columns of the grid follow the same order as the list."""
        return [
            self._people.item(row).data(Qt.ItemDataRole.UserRole)
            for row in range(self._people.count())
            if self._people.item(row).checkState() is Qt.CheckState.Checked
        ]

    @property
    def week(self) -> list[DayHours]:
        return self._hours.week()

    def _refresh(self) -> None:
        """Says what will be built, and refuses to build something impossible."""
        self._hours_summary.setText(self._hours.summary())

        days = (self.end_date - self.start_date).days + 1
        people = len(self.employee_ids)

        if days < 1:
            message, tone, allowed = "Data końca jest wcześniejsza niż początku.", "danger", False
        elif days > MAX_PERIOD_DAYS:
            message = f"Okres nie może być dłuższy niż {MAX_PERIOD_DAYS} dni."
            tone, allowed = "danger", False
        elif people == 0:
            message, tone, allowed = "Zaznacz co najmniej jedną osobę.", "", False
        else:
            message = f"{count_days(days)} × {count_people(people)} — tyle będzie miała siatka."
            holidays = len(holidays_within(self.start_date, self.end_date))
            if holidays:
                verb = word(holidays, "wypada", "wypadają", "wypada")
                message += (
                    f" W okresie {verb} {plural(holidays, 'święto', 'święta', 'świąt')}"
                    " — te dni będą zamknięte, dopóki ich nie otworzysz."
                )
            tone, allowed = "", True

        self._summary.setText(message)
        self._summary.setObjectName("" if tone else "mutedText")
        self._summary.setProperty("tone", tone)
        restyle(self._summary)
        self._save.setEnabled(allowed and bool(self.name.strip()))
