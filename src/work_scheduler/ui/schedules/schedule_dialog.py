from calendar import monthrange
from datetime import date

from PySide6.QtCore import QDate, QLocale, Qt
from PySide6.QtGui import QColor, QTextCharFormat
from PySide6.QtWidgets import (
    QCalendarWidget,
    QDateEdit,
    QDialog,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from work_scheduler.database.models import Employee
from work_scheduler.i18n import Language, current_language, profession_name, t, translate
from work_scheduler.services import DayHours
from work_scheduler.services.holidays import holidays_in, holidays_within
from work_scheduler.services.schedule_service import MAX_PERIOD_DAYS
from work_scheduler.ui.components import (
    PlainLabel,
    primary_button,
    restyle,
    secondary_button,
)
from work_scheduler.ui.schedules.people_picker import (
    NAME_ROLE,
    PROFESSION_ROLE,
    TRADE_ROLE,
    PersonDelegate,
)
from work_scheduler.ui.settings.opening_hours_editor import OpeningHoursEditor
from work_scheduler.ui.theme import LIGHT, METRICS, Palette


def suggested_name(start: date, end: date | None = None) -> str:
    """The name the period would be given by whoever is reading it.

    Within one month that is the month; across a boundary the two dates, because
    "Sierpień" on a schedule that runs into September would be a small lie.
    """
    if end is None or (start.year, start.month) == (end.year, end.month):
        return f"{translate(f'month.name.{start.month}')} {start.year}"
    if start.year == end.year:
        return f"{start:%d.%m} – {end:%d.%m.%Y}"
    return f"{start:%d.%m.%Y} – {end:%d.%m.%Y}"


def start_of_month(day: date) -> date:
    return day.replace(day=1)


def end_of_month(day: date) -> date:
    """A schedule covers a month, so the whole of the current one is the opening guess.

    Starting from today instead would offer a period whose name — the month — covers
    more than the period does.
    """
    return day.replace(day=monthrange(day.year, day.month)[1])


def _to_qdate(value: date) -> QDate:
    return QDate(value.year, value.month, value.day)


def _localised_calendar(field: QDateEdit, palette: Palette) -> None:
    """Month names in the interface language, weeks from Monday, holidays in blue."""
    calendar = field.calendarWidget()
    calendar.setLocale(_calendar_locale())
    calendar.setFirstDayOfWeek(Qt.DayOfWeek.Monday)
    calendar.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
    calendar.setGridVisible(False)

    marked = QTextCharFormat()
    marked.setBackground(QColor(palette.holiday_surface))
    today = date.today()
    # Enough years around today that scrolling the popup keeps showing them.
    for year in range(today.year - 1, today.year + 3):
        for day in holidays_in(year):
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

        self.setWindowTitle(t("wizard.title"))
        self.setModal(True)
        self.setMinimumWidth(METRICS.dialog_width)

        self._name = QLineEdit(suggested_name(start_of_month(today), end_of_month(today)))
        # Set by hand once, and the dates stop rewriting it: a name somebody typed is
        # theirs, not a field the calendar may overwrite behind their back.
        self._name_is_mine = False
        self._start = QDateEdit(_to_qdate(start_of_month(today)))
        self._end = QDateEdit(_to_qdate(end_of_month(today)))
        self._people = QListWidget()
        self._hours = OpeningHoursEditor(week)
        self._hours_summary = PlainLabel()
        self._customise = secondary_button(t("wizard.customise"))
        self._folded_height = 0
        self._summary = PlainLabel()
        self._save = primary_button(t("wizard.create"))

        self._fill_people(employees)
        self._build()
        self._refresh()

    # Construction -----------------------------------------------------------

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*(METRICS.space_6,) * 4)
        layout.setSpacing(METRICS.space_4)

        layout.addLayout(self._field(t("wizard.name"), self._name))
        layout.addLayout(self._period_row())
        layout.addLayout(self._field(t("wizard.who_works"), self._people))
        layout.addLayout(self._hours_row())

        self._summary.setObjectName("mutedText")
        # Two sentences in Polish, and longer still in English. Without wrapping the
        # tail of the line simply leaves the window.
        self._summary.setWordWrap(True)
        layout.addWidget(self._summary)
        layout.addLayout(self._buttons())

        self._name.textChanged.connect(self._refresh)
        self._name.textEdited.connect(self._claim_name)
        for field in (self._start, self._end):
            field.setDisplayFormat("dd.MM.yyyy")
            field.setCalendarPopup(True)
            field.dateChanged.connect(self._rename_for_period)
            field.dateChanged.connect(self._refresh)
            _localised_calendar(field, self._palette)
        self._people.itemChanged.connect(self._refresh)

    def _period_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(METRICS.space_3)
        row.addLayout(self._field(t("wizard.from"), self._start))
        row.addLayout(self._field(t("wizard.to"), self._end))
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

        column = self._field(t("wizard.opening_hours"), None)
        column.addLayout(head)
        column.addWidget(self._hours)
        return column

    def _buttons(self) -> QHBoxLayout:
        cancel = secondary_button(t("common.cancel"))
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

        label = PlainLabel(text)
        label.setObjectName("fieldLabel")
        column.addWidget(label)

        if widget is not None:
            label.setBuddy(widget)
            widget.setAccessibleName(text)
            column.addWidget(widget)
        return column

    def _fill_people(self, employees: list[Employee]) -> None:
        # Exactly five full rows. A flexible height used to leave half a person cut
        # off at the lower border when the dialog was laid out on macOS.
        self._people.setFixedHeight(METRICS.people_list_height)
        self._people.setProperty("role", "picker")
        self._people.setItemDelegate(PersonDelegate(self._palette, self._people))
        self._people.setSpacing(0)
        # The real indicator is hidden — the delegate draws the box — so the row has to
        # do the toggling. Clicking anywhere on it is the easier target anyway.
        self._people.itemClicked.connect(self._toggle_person)

        for employee in employees:
            name = f"{employee.last_name} {employee.first_name}"
            # The row is painted, so the pieces travel as data rather than as one
            # string the delegate would have to take apart again.
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, employee.id)
            item.setData(NAME_ROLE, name)
            item.setData(TRADE_ROLE, profession_name(employee.profession))
            item.setData(PROFESSION_ROLE, employee.profession)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self._people.addItem(item)

    @staticmethod
    def _toggle_person(item: QListWidgetItem) -> None:
        checked = item.checkState() == Qt.CheckState.Checked
        item.setCheckState(Qt.CheckState.Unchecked if checked else Qt.CheckState.Checked)

    # State ------------------------------------------------------------------

    def _show_hours(self, shown: bool) -> None:
        """Qt grows a window to fit a revealed child but never shrinks it back.

        The height from before unfolding is remembered rather than recomputed, because
        the natural size hint is not what the window was actually sitting at.
        """
        if shown:
            self._folded_height = self.height()

        self._customise.setText(t("common.collapse") if shown else t("wizard.customise"))
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

    def _claim_name(self, text: str) -> None:
        """Only typing counts. ``setText`` fires textChanged, never textEdited."""
        self._name_is_mine = bool(text.strip())

    def _rename_for_period(self) -> None:
        if self._name_is_mine:
            return
        self._name.setText(suggested_name(self.start_date, self.end_date))

    def _refresh(self) -> None:
        """Says what will be built, and refuses to build something impossible."""
        self._hours_summary.setText(self._hours.summary())

        days = (self.end_date - self.start_date).days + 1
        people = len(self.employee_ids)

        if days < 1:
            message, tone, allowed = t("wizard.end_before_start"), "danger", False
        elif days > MAX_PERIOD_DAYS:
            message = t("wizard.period_too_long", max=MAX_PERIOD_DAYS)
            tone, allowed = "danger", False
        elif people == 0:
            message, tone, allowed = t("schedule.error.no_people"), "", False
        else:
            message = t(
                "wizard.grid_size",
                days=t("count.days", count=days),
                people=t("count.people", count=people),
            )
            holidays = len(holidays_within(self.start_date, self.end_date))
            if holidays:
                message += (
                    " "
                    + t("schedule.wizard.holidays_in_period", count=holidays)
                    + t("wizard.holidays_suffix")
                )
            tone, allowed = "", True

        self._summary.setText(message)
        # QLabel reports the wrapped height correctly, but a visible QDialog does not
        # necessarily grow when the text changes after somebody ticks a person. Reserve
        # the height needed at the dialog's narrowest supported width so neither the
        # Polish nor the longer English summary is clipped behind the button row.
        summary_width = METRICS.dialog_width - 2 * METRICS.space_6
        self._summary.setMinimumHeight(self._summary.heightForWidth(summary_width))
        self._summary.setObjectName("" if tone else "mutedText")
        self._summary.setProperty("tone", tone)
        restyle(self._summary)
        self._save.setEnabled(allowed and bool(self.name.strip()))


def _calendar_locale() -> QLocale:
    """The calendar popup takes its month and day names from Qt, not from us."""
    if current_language() is Language.EN:
        return QLocale(QLocale.Language.English, QLocale.Country.UnitedKingdom)
    return QLocale(QLocale.Language.Polish, QLocale.Country.Poland)
