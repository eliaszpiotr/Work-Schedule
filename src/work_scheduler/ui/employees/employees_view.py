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
    QFrame,
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
from work_scheduler.i18n import profession_label, t
from work_scheduler.services import EmployeeService, ServiceError
from work_scheduler.ui.components import (
    EmptyState,
    PageHeader,
    confirm_destructive,
    primary_button,
    set_button_icon,
)
from work_scheduler.ui.employees.employee_delegate import PROFESSION_ROLE, EmployeeDelegate
from work_scheduler.ui.employees.employee_dialog import EmployeeDialog
from work_scheduler.ui.theme import METRICS, Palette


def active_label(active: bool) -> str:
    return t("common.active" if active else "common.inactive")


# The first column reads "Imię Nazwisko" but has to sort by surname, so the proxy is
# given a separate key instead of the text on screen.
SORT_ROLE = Qt.ItemDataRole.UserRole + 1

# A fixed alphabet keeps sorting identical on macOS, Windows and headless Linux.
# QSortFilterProxyModel's locale-aware mode follows the host locale; CI commonly
# runs in the C locale, where upper- and lower-case names can end up in different
# groups. Q, V and X are included in their usual international positions so names
# outside the Polish alphabet still sort naturally.
_SORT_ALPHABET = "aąbcćdeęfghijklłmnńoópqrsśtuvwxyzźż"
_SORT_RANK = {character: rank for rank, character in enumerate(_SORT_ALPHABET)}


def polish_sort_key(value: str) -> tuple[tuple[int, str], ...]:
    folded = value.casefold()
    return tuple((_SORT_RANK.get(character, len(_SORT_RANK)), character) for character in folded)


class EmployeeSortProxyModel(QSortFilterProxyModel):
    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:  # noqa: N802 - Qt API
        left_value = str(left.data(self.sortRole()) or "")
        right_value = str(right.data(self.sortRole()) or "")
        return polish_sort_key(left_value) < polish_sort_key(right_value)


class EmployeeTableModel(QAbstractTableModel):
    @property
    def HEADERS(self) -> tuple[str, ...]:  # noqa: N802 - kept as the model's own name
        return (
            t("employees.column.person"),
            t("employees.column.profession"),
            t("employees.column.status"),
        )

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
        if not index.isValid():
            return None

        employee = self._employees[index.row()]
        if role == PROFESSION_ROLE:
            return employee.profession
        if role == SORT_ROLE and index.column() == 0:
            return f"{employee.last_name} {employee.first_name}"
        if role not in (Qt.ItemDataRole.DisplayRole, SORT_ROLE):
            return None

        return (
            employee.full_name,
            profession_label(employee.profession),
            active_label(employee.active),
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
        self._proxy = EmployeeSortProxyModel(self)
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._proxy.setFilterKeyColumn(-1)
        self._proxy.setSortRole(SORT_ROLE)

        self._add = primary_button(t("employees.add"), "plus", palette)
        self._search = QLineEdit()
        self._show_inactive = QCheckBox(t("employees.show_inactive"))
        self._table = QTableView()
        self._stack = QStackedWidget()

        self._build()
        self.reload()

    # Construction -----------------------------------------------------------

    def _build(self) -> None:
        header = PageHeader(t("employees.title"))
        self._add.clicked.connect(self.add_employee)
        header.add_action(self._add)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(header)

        panel = QFrame()
        panel.setObjectName("workspaceBody")
        body = QVBoxLayout(panel)
        body.setContentsMargins(METRICS.space_6, METRICS.space_5, METRICS.space_6, METRICS.space_6)
        body.setSpacing(METRICS.space_4)
        body.addLayout(self._filter_row())

        self._configure_table()
        self._stack.addWidget(self._table)
        self._stack.addWidget(
            EmptyState(
                t("employees.empty.title"),
                t("employees.empty.body"),
                (t("employees.add"), self.add_employee),
            )
        )
        # Stretch, with the cap on the stack: without it the stack hands the table its
        # own sizeHint, which is a couple of hundred pixels whatever the table holds,
        # and the rest of the people end up behind a scrollbar with the window half
        # empty below them.
        body.addWidget(self._stack, stretch=1)
        body.addStretch(0)
        layout.addWidget(panel, stretch=1)

    def _filter_row(self) -> QHBoxLayout:
        self._search.setPlaceholderText(t("employees.search.placeholder"))
        self._search.setClearButtonEnabled(True)
        self._search.setAccessibleName(t("employees.search.label"))
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

    def _fit_to_rows(self) -> None:
        """Stop at the last person, and start scrolling only when they stop fitting."""
        frame = 2 * self._table.frameWidth()
        content = (
            max(self._table.horizontalHeader().height(), METRICS.table_row_height)
            + self._proxy.rowCount() * METRICS.employee_row_height
            + frame
        )
        self._stack.setMaximumHeight(content)

    def _configure_table(self) -> None:
        self._table.setProperty("data", "true")
        self._table.setModel(self._proxy)
        self._delegate = EmployeeDelegate(self._palette, self)
        self._table.setItemDelegate(self._delegate)
        self._proxy.layoutChanged.connect(self._fit_to_rows)
        self._proxy.modelReset.connect(self._fit_to_rows)
        self._fit_to_rows()
        self._table.setSortingEnabled(True)
        self._table.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(False)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setVisible(False)
        # Taller than a plain row: an avatar has to fit without touching the rules.
        self._table.verticalHeader().setDefaultSectionSize(METRICS.employee_row_height)
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

    # Appearance -------------------------------------------------------------

    def apply_palette(self, palette: Palette) -> None:
        """Icons are painted, not styled, so they need repainting when the theme flips."""
        self._palette = palette
        set_button_icon(self._add, "plus", palette.on_accent)
        self._delegate.set_palette(palette)
        self._table.viewport().update()

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

        if confirm_destructive(
            self,
            t("employees.delete.title"),
            t("employees.delete.body", name=employee.full_name),
            t("employees.delete.action"),
            palette=self._palette,
        ):
            self._run(lambda: self._service.delete(employee.id))

    def _run(self, operation) -> None:
        """Every service call funnels through here so failures become messages."""
        try:
            operation()
        except ServiceError as error:
            QMessageBox.warning(self, t("common.failed"), str(error))
            return
        self.reload()

    def pick_row_at(self, position: QPoint) -> None:
        """Qt does not move the selection on a right-click, so the menu has to."""
        index = self._table.indexAt(position)
        if index.isValid():
            self._table.selectRow(index.row())

    def _open_context_menu(self, position: QPoint) -> None:
        self.pick_row_at(position)
        employee = self.selected_employee()
        if employee is None:
            return

        menu = QMenu(self)
        menu.addAction(t("common.edit"), self.edit_selected)
        menu.addAction(
            t("employees.mark_inactive") if employee.active else t("employees.mark_active"),
            self.toggle_selected,
        )
        menu.addSeparator()
        menu.addAction(t("common.delete"), self.delete_selected)
        menu.exec(self._table.viewport().mapToGlobal(position))
