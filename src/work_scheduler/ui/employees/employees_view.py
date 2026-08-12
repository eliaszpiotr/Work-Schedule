from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    QPoint,
    QSortFilterProxyModel,
    Qt,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMenu,
    QMessageBox,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from work_scheduler.database.models import Employee
from work_scheduler.services import EmployeeService, ServiceError
from work_scheduler.ui.components import EmptyState, PageHeader, primary_button
from work_scheduler.ui.employees.employee_dialog import PROFESSION_LABELS, EmployeeDialog
from work_scheduler.ui.theme import METRICS, Palette

ACTIVE_LABEL = {True: "Aktywny", False: "Nieaktywny"}


class EmployeeTableModel(QAbstractTableModel):
    HEADERS = ("Pracownik", "Stanowisko", "Status")

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._employees: list[Employee] = []

    def set_employees(self, employees: list[Employee]) -> None:
        self.beginResetModel()
        self._employees = list(employees)
        self.endResetModel()

    def employee_at(self, row: int) -> Employee | None:
        if 0 <= row < len(self._employees):
            return self._employees[row]
        return None

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802 - Qt API
        return 0 if parent and parent.isValid() else len(self._employees)

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802 - Qt API
        return 0 if parent and parent.isValid() else len(self.HEADERS)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> str | None:
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None

        employee = self._employees[index.row()]
        return (
            employee.full_name,
            PROFESSION_LABELS[employee.profession],
            ACTIVE_LABEL[employee.active],
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


class EmployeesView(QWidget):
    def __init__(self, service: EmployeeService, palette: Palette) -> None:
        super().__init__()
        self.setObjectName("workspace")
        self._service = service
        self._palette = palette

        self._model = EmployeeTableModel(self)
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._proxy.setFilterKeyColumn(-1)

        self._search = QLineEdit()
        self._show_inactive = QCheckBox("Pokaż nieaktywnych")
        self._table = QTableView()
        self._stack = QStackedWidget()

        self._build()
        self.reload()

    # Construction -----------------------------------------------------------

    def _build(self) -> None:
        header = PageHeader("Pracownicy")
        add = primary_button("Dodaj pracownika", "plus", self._palette)
        add.clicked.connect(self.add_employee)
        header.add_action(add)

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
                "Brak pracowników",
                "Dodaj pierwszą osobę, aby móc układać grafik.",
                ("Dodaj pracownika", self.add_employee),
            )
        )
        body.addWidget(self._stack, stretch=1)
        layout.addLayout(body)

    def _filter_row(self) -> QHBoxLayout:
        self._search.setPlaceholderText("Szukaj po nazwisku lub stanowisku…")
        self._search.setClearButtonEnabled(True)
        self._search.setAccessibleName("Szukaj pracownika")
        self._search.setMaximumWidth(320)
        self._search.textChanged.connect(self._proxy.setFilterFixedString)

        self._show_inactive.setChecked(True)
        self._show_inactive.toggled.connect(self.reload)

        row = QHBoxLayout()
        row.setSpacing(METRICS.space_3)
        row.addWidget(self._search)
        row.addStretch()
        row.addWidget(self._show_inactive)
        return row

    def _configure_table(self) -> None:
        self._table.setModel(self._proxy)
        self._table.setSortingEnabled(True)
        self._table.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(False)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(METRICS.table_row_height)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setHighlightSections(False)
        # Stylesheet text-align has no effect on header sections; Qt needs this call.
        self._table.horizontalHeader().setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._open_context_menu)
        self._table.doubleClicked.connect(lambda _: self.edit_selected())

    # Data -------------------------------------------------------------------

    def reload(self) -> None:
        employees = self._service.list_employees(include_inactive=self._show_inactive.isChecked())
        self._model.set_employees(employees)
        self._stack.setCurrentIndex(0 if employees else 1)

    def selected_employee(self) -> Employee | None:
        indexes = self._table.selectionModel().selectedRows()
        if not indexes:
            return None
        return self._model.employee_at(self._proxy.mapToSource(indexes[0]).row())

    # Actions ----------------------------------------------------------------

    def add_employee(self) -> None:
        dialog = EmployeeDialog(self)
        if dialog.exec() != EmployeeDialog.DialogCode.Accepted:
            return

        self._run(
            lambda: self._service.create(dialog.first_name, dialog.last_name, dialog.profession)
        )

    def edit_selected(self) -> None:
        employee = self.selected_employee()
        if employee is None:
            return

        dialog = EmployeeDialog(self, employee)
        if dialog.exec() != EmployeeDialog.DialogCode.Accepted:
            return

        self._run(
            lambda: self._service.update(
                employee.id,
                dialog.first_name,
                dialog.last_name,
                dialog.profession,
                active=dialog.active,
            )
        )

    def toggle_selected(self) -> None:
        employee = self.selected_employee()
        if employee is not None:
            self._run(lambda: self._service.set_active(employee.id, not employee.active))

    def delete_selected(self) -> None:
        employee = self.selected_employee()
        if employee is None:
            return

        confirmed = QMessageBox.question(
            self,
            "Usunąć pracownika?",
            f"{employee.full_name} zostanie trwale usunięty z kartoteki.",
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.Cancel,
        )
        if confirmed is QMessageBox.StandardButton.Yes:
            self._run(lambda: self._service.delete(employee.id))

    def _run(self, operation) -> None:
        """Every service call funnels through here so failures become messages."""
        try:
            operation()
        except ServiceError as error:
            QMessageBox.warning(self, "Nie udało się", str(error))
            return
        self.reload()

    def _open_context_menu(self, position: QPoint) -> None:
        employee = self.selected_employee()
        if employee is None:
            return

        menu = QMenu(self)
        menu.addAction("Edytuj", self.edit_selected)
        menu.addAction(
            "Oznacz jako nieaktywnego" if employee.active else "Oznacz jako aktywnego",
            self.toggle_selected,
        )
        menu.addSeparator()
        menu.addAction("Usuń", self.delete_selected)
        menu.exec(self._table.viewport().mapToGlobal(position))
