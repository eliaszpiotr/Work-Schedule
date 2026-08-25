from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    QPoint,
    Qt,
    Signal,
)
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QMenu,
    QMessageBox,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from work_scheduler.database.models import ScheduleStatus
from work_scheduler.services import (
    EmployeeService,
    OpeningHoursService,
    ScheduleService,
    ScheduleSummary,
    ServiceError,
    ShiftService,
)
from work_scheduler.ui.components import (
    EmptyState,
    PageHeader,
    confirm_destructive,
    primary_button,
    set_button_icon,
)
from work_scheduler.ui.schedules.export_actions import save_as_pdf, send_to_printer
from work_scheduler.ui.schedules.schedule_dialog import ScheduleDialog
from work_scheduler.ui.theme import METRICS, Palette

STATUS_LABELS = {
    ScheduleStatus.DRAFT: "Roboczy",
    ScheduleStatus.FINAL: "Gotowy",
    ScheduleStatus.ARCHIVED: "Archiwalny",
}
# One tab with a filter, rather than a separate archive tab.
STATUS_FILTERS = (
    ("Wszystkie", None),
    *((label, status) for status, label in STATUS_LABELS.items()),
)


class ScheduleTableModel(QAbstractTableModel):
    HEADERS = ("Nazwa", "Okres", "Osób", "Status")

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._schedules: list[ScheduleSummary] = []

    def set_schedules(self, schedules: list[ScheduleSummary]) -> None:
        self.beginResetModel()
        self._schedules = list(schedules)
        self.endResetModel()

    def schedule_at(self, row: int) -> ScheduleSummary | None:
        if 0 <= row < len(self._schedules):
            return self._schedules[row]
        return None

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802 - Qt API
        return 0 if parent and parent.isValid() else len(self._schedules)

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802 - Qt API
        return 0 if parent and parent.isValid() else len(self.HEADERS)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> str | None:
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None

        schedule = self._schedules[index.row()]
        return (
            schedule.name,
            schedule.period,
            str(schedule.employee_count),
            STATUS_LABELS[schedule.status],
        )[index.column()]

    def headerData(  # noqa: N802 - Qt API
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> str | None:
        if orientation is Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.HEADERS[section]
        return None


class SchedulesView(QWidget):
    """The list of schedules. Opening one is announced; the parent swaps in the grid."""

    schedule_opened = Signal(int)

    def __init__(
        self,
        schedules: ScheduleService,
        employees: EmployeeService,
        hours: OpeningHoursService,
        shifts: ShiftService,
        palette: Palette,
    ) -> None:
        super().__init__()
        self.setObjectName("workspace")
        self._schedules = schedules
        self._employees = employees
        self._hours = hours
        self._shifts = shifts
        self._palette = palette

        self._model = ScheduleTableModel(self)
        self._status = QComboBox()
        self._table = QTableView()
        self._stack = QStackedWidget()
        self._add = primary_button("Nowy grafik", "plus", palette)

        self._build()
        self.reload()

    # Construction -----------------------------------------------------------

    def _build(self) -> None:
        header = PageHeader("Grafiki")
        self._add.clicked.connect(self.new_schedule)
        header.add_action(self._add)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(header)

        body = QVBoxLayout()
        body.setContentsMargins(METRICS.space_6, METRICS.space_5, METRICS.space_6, METRICS.space_6)
        body.setSpacing(METRICS.space_4)
        body.addLayout(self._filter_row())

        self._configure_table()
        self._stack.addWidget(self._table)
        self._stack.addWidget(
            EmptyState(
                "Brak grafików",
                "Utwórz pierwszy grafik, żeby zacząć układać godziny.",
                ("Nowy grafik", self.new_schedule),
            )
        )
        body.addWidget(self._stack, stretch=1)
        layout.addLayout(body)

    def _filter_row(self) -> QHBoxLayout:
        for label, status in STATUS_FILTERS:
            self._status.addItem(label, status)
        self._status.setAccessibleName("Filtr statusu")
        self._status.setFixedWidth(METRICS.status_filter_width)
        self._status.currentIndexChanged.connect(self.reload)

        row = QHBoxLayout()
        row.setSpacing(METRICS.space_3)
        row.addWidget(self._status)
        row.addStretch()
        return row

    def _configure_table(self) -> None:
        self._table.setProperty("data", "true")
        self._table.setModel(self._model)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(METRICS.table_row_height)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2, 3):
            self._table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        self._table.horizontalHeader().setHighlightSections(False)
        self._table.horizontalHeader().setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._open_context_menu)
        self._table.doubleClicked.connect(lambda _: self.open_selected())

        remove = QShortcut(QKeySequence.StandardKey.Delete, self._table)
        remove.setContext(Qt.ShortcutContext.WidgetShortcut)
        remove.activated.connect(self.delete_selected)

    # Appearance -------------------------------------------------------------

    def apply_palette(self, palette: Palette) -> None:
        self._palette = palette
        set_button_icon(self._add, "plus", palette.on_accent)

    # Data -------------------------------------------------------------------

    def reload(self) -> None:
        schedules = self._schedules.list_schedules(status=self._status.currentData())
        self._model.set_schedules(schedules)
        # The empty state belongs to an empty database, not to an empty filter result.
        self._stack.setCurrentIndex(0 if schedules or self._status.currentData() else 1)

    def selected_schedule(self) -> ScheduleSummary | None:
        indexes = self._table.selectionModel().selectedRows()
        if not indexes:
            return None
        return self._model.schedule_at(indexes[0].row())

    # Actions ----------------------------------------------------------------

    def new_schedule(self) -> None:
        people = self._employees.list_employees(include_inactive=False)
        if not people:
            QMessageBox.information(
                self,
                "Najpierw pracownicy",
                "Dodaj pracowników na ekranie „Pracownicy”, zanim utworzysz grafik.",
            )
            return

        dialog = ScheduleDialog(self, people, self._hours.week(), palette=self._palette)
        if dialog.exec() != ScheduleDialog.DialogCode.Accepted:
            return

        try:
            created = self._schedules.create(
                dialog.name,
                dialog.start_date,
                dialog.end_date,
                dialog.employee_ids,
                dialog.week,
            )
        except ServiceError as error:
            QMessageBox.warning(self, "Nie udało się", str(error))
            return

        self.reload()
        self.schedule_opened.emit(created.id)

    def open_selected(self) -> None:
        schedule = self.selected_schedule()
        if schedule is not None:
            self.schedule_opened.emit(schedule.id)

    def delete_selected(self, *, confirmed: bool | None = None) -> None:
        schedule = self.selected_schedule()
        if schedule is None:
            return

        if confirmed is None:
            confirmed = confirm_destructive(
                self,
                "Usunąć grafik?",
                f"„{schedule.name}” zniknie razem ze wszystkimi wpisanymi godzinami. "
                "Tego nie da się cofnąć.",
                "Usuń grafik",
            )
        if not confirmed:
            return

        try:
            self._schedules.delete(schedule.id)
        except ServiceError as error:
            QMessageBox.warning(self, "Nie udało się", str(error))
            return
        self.reload()

    def pick_row_at(self, position: QPoint) -> None:
        """Qt does not move the selection on a right-click, so the menu has to."""
        index = self._table.indexAt(position)
        if index.isValid():
            self._table.selectRow(index.row())

    def _open_context_menu(self, position: QPoint) -> None:
        self.pick_row_at(position)
        if self.selected_schedule() is None:
            return

        menu = QMenu(self)
        menu.addAction("Otwórz", self.open_selected)
        menu.addSeparator()
        self._add_export_actions(menu)
        menu.addSeparator()
        menu.addAction("Usuń", self.delete_selected)
        menu.exec(self._table.viewport().mapToGlobal(position))

    def _add_export_actions(self, menu: QMenu) -> None:
        """Printing is offered only for a checked schedule, and says so when it is not."""
        schedule = self.selected_schedule()
        ready = schedule is not None and schedule.status is not ScheduleStatus.DRAFT

        save = menu.addAction("Zapisz PDF…", self.save_selected_pdf)
        printout = menu.addAction("Drukuj…", self.print_selected)
        for action in (save, printout):
            action.setEnabled(ready)
            if not ready:
                action.setToolTip("Najpierw zakończ grafik")

        if ready:
            menu.addAction("Wróć do roboczego", self.reopen_selected)

    def save_selected_pdf(self) -> None:
        schedule = self.selected_schedule()
        if schedule is not None:
            save_as_pdf(self, self._schedules, self._shifts, schedule.id)

    def print_selected(self) -> None:
        schedule = self.selected_schedule()
        if schedule is not None:
            send_to_printer(self, self._schedules, self._shifts, schedule.id)

    def reopen_selected(self) -> None:
        schedule = self.selected_schedule()
        if schedule is None:
            return
        try:
            self._schedules.reopen(schedule.id)
        except ServiceError as error:
            QMessageBox.warning(self, "Nie udało się", str(error))
            return
        self.reload()
