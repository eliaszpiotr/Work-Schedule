from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QMenu,
    QMessageBox,
    QScrollArea,
    QStackedWidget,
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
    SegmentedControl,
    confirm_destructive,
    primary_button,
    set_button_icon,
)
from work_scheduler.ui.icons import load_icon
from work_scheduler.ui.schedules.export_actions import save_as_pdf, send_to_printer
from work_scheduler.ui.schedules.schedule_card import CardList, ScheduleCard
from work_scheduler.ui.schedules.schedule_dialog import ScheduleDialog
from work_scheduler.ui.theme import METRICS, Palette

# One row of filters, rather than a separate archive tab. The words are plural here
# and singular on a card: the filter names a set, the badge names one schedule.
# Archived is missing on purpose: nothing in the application ever sets that status,
# so the filter could only ever come back empty.
FILTER_LABELS = {
    ScheduleStatus.DRAFT: "Robocze",
    ScheduleStatus.FINAL: "Gotowe",
}
STATUS_FILTERS = (
    ("Wszystkie", None),
    *((label, status) for status, label in FILTER_LABELS.items()),
)


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

        self._filter = SegmentedControl(list(STATUS_FILTERS))
        self._cards = CardList()
        self._picked: int | None = None
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

        # The cards need something to sit on: white on white has no edge to it.
        # A QFrame, not a QWidget — a plain QWidget ignores a stylesheet background
        # unless it is told to paint one, and then does it silently.
        panel = QFrame()
        panel.setObjectName("workspaceBody")
        body = QVBoxLayout(panel)
        body.setContentsMargins(METRICS.space_6, METRICS.space_5, METRICS.space_6, METRICS.space_6)
        body.setSpacing(METRICS.space_4)
        body.addLayout(self._filter_row())

        self._stack.addWidget(self._scroller())
        self._stack.addWidget(
            EmptyState(
                "Brak grafików",
                "Utwórz pierwszy grafik, żeby zacząć układać godziny.",
                ("Nowy grafik", self.new_schedule),
            )
        )
        body.addWidget(self._stack, stretch=1)
        layout.addWidget(panel, stretch=1)

    def _filter_row(self) -> QHBoxLayout:
        self._filter.setAccessibleName("Filtr statusu")
        self._filter.changed.connect(lambda _: self.reload())

        row = QHBoxLayout()
        row.setSpacing(METRICS.space_3)
        row.addWidget(self._filter)
        row.addStretch()
        return row

    def _scroller(self) -> QScrollArea:
        area = QScrollArea()
        area.setObjectName("cardList")
        area.setWidget(self._cards)
        area.setWidgetResizable(True)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        area.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        remove = QShortcut(QKeySequence.StandardKey.Delete, area)
        remove.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        remove.activated.connect(self.delete_selected)
        return area

    # Appearance -------------------------------------------------------------

    def apply_palette(self, palette: Palette) -> None:
        self._palette = palette
        set_button_icon(self._add, "plus", palette.on_accent)
        for card in self._cards.cards():
            card.apply_palette(palette)

    # Data -------------------------------------------------------------------

    def reload(self) -> None:
        chosen = self._filter.value()
        schedules = self._schedules.list_schedules(status=chosen)

        self._cards.clear()
        for summary in schedules:
            card = ScheduleCard(summary, self._palette)
            card.picked.connect(self.pick)
            card.opened.connect(self.schedule_opened.emit)
            card.menu_requested.connect(self._open_context_menu)
            self._cards.add(card)

        # A schedule that vanished from the list cannot stay picked behind its card.
        if self._picked not in {summary.id for summary in schedules}:
            self._picked = None
        self._paint_selection()

        # The empty state belongs to an empty database, not to an empty filter result.
        self._stack.setCurrentIndex(0 if schedules or chosen else 1)

    def pick(self, schedule_id: int) -> None:
        self._picked = schedule_id
        self._paint_selection()

    def _paint_selection(self) -> None:
        for card in self._cards.cards():
            card.set_picked(card.schedule.id == self._picked)

    def selected_schedule(self) -> ScheduleSummary | None:
        for card in self._cards.cards():
            if card.schedule.id == self._picked:
                return card.schedule
        return None

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
                palette=self._palette,
            )
        if not confirmed:
            return

        try:
            self._schedules.delete(schedule.id)
        except ServiceError as error:
            QMessageBox.warning(self, "Nie udało się", str(error))
            return
        self.reload()

    def _open_context_menu(self, _schedule_id: int, position: QPoint) -> None:
        if self.selected_schedule() is None:
            return

        menu = QMenu(self)
        self._entry(menu, "square-pen", "Otwórz", self.open_selected)
        menu.addSeparator()
        self._add_export_actions(menu)
        menu.addSeparator()
        self._entry(menu, "trash-2", "Usuń", self.delete_selected)
        menu.exec(position)

    def _entry(self, menu: QMenu, icon: str, label: str, action) -> QAction:  # noqa: ANN001
        """Menu entries carry their icon, recoloured for whichever theme is on."""
        entry = menu.addAction(load_icon(icon, self._palette.text_secondary), label, action)
        return entry

    def _add_export_actions(self, menu: QMenu) -> None:
        """Printing is offered only for a checked schedule, and says so when it is not."""
        schedule = self.selected_schedule()
        ready = schedule is not None and schedule.status is not ScheduleStatus.DRAFT

        save = self._entry(menu, "file-down", "Zapisz PDF…", self.save_selected_pdf)
        printout = self._entry(menu, "printer", "Drukuj…", self.print_selected)
        for action in (save, printout):
            action.setEnabled(ready)
            if not ready:
                action.setToolTip("Najpierw zakończ grafik")

        if ready:
            self._entry(menu, "chevron-left", "Wróć do roboczego", self.reopen_selected)

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
