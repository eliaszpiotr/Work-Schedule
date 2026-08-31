from datetime import date, time

from PySide6.QtCore import Qt, QTime
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from work_scheduler.database.models import Employee
from work_scheduler.i18n import profession_name, t
from work_scheduler.ui.components import PlainLabel, primary_button, secondary_button
from work_scheduler.ui.schedules.people_picker import (
    NAME_ROLE,
    PROFESSION_ROLE,
    TRADE_ROLE,
    PersonDelegate,
)
from work_scheduler.ui.theme import METRICS, Palette

TIME_FORMAT = "HH:mm"


def _to_qtime(value: time) -> QTime:
    return QTime(value.hour, value.minute)


def _from_qtime(value: QTime) -> time:
    return time(value.hour(), value.minute())


class ScheduleTeamDialog(QDialog):
    """Change the columns of an existing schedule without rebuilding it."""

    def __init__(
        self,
        parent: QWidget | None,
        employees: list[Employee],
        selected_ids: list[int],
        palette: Palette,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("grid.team.title"))
        self.setMinimumWidth(METRICS.dialog_width)
        self._selected = set(selected_ids)

        title = PlainLabel(t("grid.team.title"))
        title.setObjectName("dialogTitle")
        hint = PlainLabel(t("grid.team.hint"))
        hint.setObjectName("mutedText")
        hint.setWordWrap(True)

        self._people = QListWidget()
        self._people.setProperty("role", "picker")
        self._people.setItemDelegate(PersonDelegate(palette, self._people))
        self._people.setFixedHeight(METRICS.people_list_height)
        self._people.setSpacing(0)
        self._fill(employees)

        self._summary = PlainLabel()
        self._summary.setObjectName("mutedText")
        self._save = primary_button(t("common.save"))
        cancel = secondary_button(t("common.cancel"))
        cancel.clicked.connect(self.reject)
        self._save.clicked.connect(self.accept)
        self._save.setDefault(True)

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(cancel)
        buttons.addWidget(self._save)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*(METRICS.space_6,) * 4)
        layout.setSpacing(METRICS.space_4)
        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addWidget(self._people)
        layout.addWidget(self._summary)
        layout.addLayout(buttons)

        self._people.itemChanged.connect(self._refresh)
        self._people.itemClicked.connect(self._toggle_row)
        self._refresh()

    def _fill(self, employees: list[Employee]) -> None:
        for employee in employees:
            name = f"{employee.last_name} {employee.first_name}"
            if not employee.active:
                name += f" · {t('common.inactive').lower()}"
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, employee.id)
            item.setData(NAME_ROLE, name)
            item.setData(TRADE_ROLE, profession_name(employee.profession))
            item.setData(PROFESSION_ROLE, employee.profession)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if employee.id in self._selected else Qt.CheckState.Unchecked
            )
            # An inactive person already present may be retained or removed, but cannot
            # be newly assigned to another schedule.
            if not employee.active and employee.id not in self._selected:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self._people.addItem(item)

    @staticmethod
    def _toggle_row(item: QListWidgetItem) -> None:
        if not item.flags() & Qt.ItemFlag.ItemIsEnabled:
            return
        state = (
            Qt.CheckState.Unchecked
            if item.checkState() == Qt.CheckState.Checked
            else Qt.CheckState.Checked
        )
        item.setCheckState(state)

    @property
    def employee_ids(self) -> list[int]:
        return [
            int(item.data(Qt.ItemDataRole.UserRole))
            for index in range(self._people.count())
            if (item := self._people.item(index)).checkState() == Qt.CheckState.Checked
        ]

    def _refresh(self) -> None:
        count = len(self.employee_ids)
        self._summary.setText(t("grid.team.selected", count=count))
        self._save.setEnabled(count > 0)


class DayHoursDialog(QDialog):
    """One date-specific exception to the schedule's weekly opening hours."""

    def __init__(
        self,
        parent: QWidget | None,
        day: date,
        opens: time | None,
        closes: time | None,
        suggested: tuple[time, time],
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("grid.day_hours.title"))
        self.setMinimumWidth(METRICS.dialog_width)

        title = PlainLabel(t("grid.day_hours.heading", date=f"{day:%d.%m.%Y}"))
        title.setObjectName("dialogTitle")
        hint = PlainLabel(t("grid.day_hours.hint"))
        hint.setObjectName("mutedText")
        hint.setWordWrap(True)

        self._open = QCheckBox(t("grid.day_hours.open"))
        self._open.setChecked(opens is not None and closes is not None)
        self._opens = QTimeEdit()
        self._closes = QTimeEdit()
        start = opens or suggested[0]
        end = closes or suggested[1]
        for field, value in ((self._opens, start), (self._closes, end)):
            field.setDisplayFormat(TIME_FORMAT)
            field.setTime(_to_qtime(value))
            field.setFixedWidth(METRICS.time_field_width)

        fields = QGridLayout()
        fields.setHorizontalSpacing(METRICS.space_3)
        fields.setVerticalSpacing(METRICS.space_3)
        fields.addWidget(self._open, 0, 0, 1, 4)
        fields.addWidget(PlainLabel(t("wizard.from")), 1, 0)
        fields.addWidget(self._opens, 1, 1)
        fields.addWidget(PlainLabel(t("wizard.to")), 1, 2)
        fields.addWidget(self._closes, 1, 3)
        fields.setColumnStretch(4, 1)

        self._error = PlainLabel()
        self._error.setProperty("tone", "danger")
        self._save = primary_button(t("common.save"))
        cancel = secondary_button(t("common.cancel"))
        cancel.clicked.connect(self.reject)
        self._save.clicked.connect(self.accept)
        self._save.setDefault(True)

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(cancel)
        buttons.addWidget(self._save)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*(METRICS.space_6,) * 4)
        layout.setSpacing(METRICS.space_4)
        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addLayout(fields)
        layout.addWidget(self._error)
        layout.addLayout(buttons)

        self._open.toggled.connect(self._refresh)
        self._open.toggled.connect(self._opens.setEnabled)
        self._open.toggled.connect(self._closes.setEnabled)
        self._opens.timeChanged.connect(self._refresh)
        self._closes.timeChanged.connect(self._refresh)
        self._refresh()

    @property
    def hours(self) -> tuple[time | None, time | None]:
        if not self._open.isChecked():
            return None, None
        return _from_qtime(self._opens.time()), _from_qtime(self._closes.time())

    def _refresh(self) -> None:
        opened = self._open.isChecked()
        self._opens.setEnabled(opened)
        self._closes.setEnabled(opened)
        valid = not opened or self._closes.time() > self._opens.time()
        self._error.setText("" if valid else t("schedule.error.close_after_open"))
        self._save.setEnabled(valid)
