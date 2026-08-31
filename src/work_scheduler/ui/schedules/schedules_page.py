from PySide6.QtWidgets import QMessageBox, QStackedWidget, QVBoxLayout, QWidget

from work_scheduler.i18n import t
from work_scheduler.services import (
    EmployeeService,
    OpeningHoursService,
    ScheduleService,
    ServiceError,
    ShiftService,
)
from work_scheduler.ui.schedules.export_actions import save_as_pdf
from work_scheduler.ui.schedules.schedule_grid import ScheduleGridView
from work_scheduler.ui.schedules.schedules_view import SchedulesView
from work_scheduler.ui.theme import Palette

LIST_PAGE = 0


class SchedulesPage(QWidget):
    """The "Grafiki" screen: the list, or one open schedule, never both."""

    def __init__(
        self,
        schedules: ScheduleService,
        employees: EmployeeService,
        hours: OpeningHoursService,
        shifts: ShiftService,
        palette: Palette,
    ) -> None:
        super().__init__()
        self._schedules = schedules
        self._employees = employees
        self._shifts = shifts
        self._palette = palette
        self._grid: ScheduleGridView | None = None

        self._stack = QStackedWidget()
        self._list = SchedulesView(schedules, employees, hours, shifts, palette)
        self._list.schedule_opened.connect(self.open_schedule)
        self._stack.addWidget(self._list)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._stack)

    def open_schedule(self, schedule_id: int) -> None:
        try:
            schedule = self._schedules.open_schedule(schedule_id)
        except ServiceError as error:
            QMessageBox.warning(self, t("schedules.open_failed"), str(error))
            self._list.reload()
            return

        self._drop_grid()
        self._grid = ScheduleGridView(
            schedule,
            self._schedules,
            self._shifts,
            self._palette,
            employees=self._employees,
        )
        self._grid.closed.connect(self.close_grid)
        self._grid.finalized.connect(self._after_finalize)
        self._stack.addWidget(self._grid)
        self._stack.setCurrentWidget(self._grid)

    def _after_finalize(self, schedule_id: int, save: bool) -> None:
        """Closing always returns to the list; the file dialog opens on top of it."""
        self.close_grid()
        if save:
            save_as_pdf(self, self._schedules, self._shifts, schedule_id)

    def close_grid(self) -> None:
        self._drop_grid()
        self._stack.setCurrentIndex(LIST_PAGE)
        self._list.reload()

    def _drop_grid(self) -> None:
        """A grid is built for one schedule; keeping the old one would leak its data."""
        if self._grid is None:
            return
        self._stack.removeWidget(self._grid)
        self._grid.deleteLater()
        self._grid = None

    def apply_palette(self, palette: Palette) -> None:
        self._palette = palette
        self._list.apply_palette(palette)
        if self._grid is not None:
            self._grid.apply_palette(palette)

    def reload(self) -> None:
        self._list.reload()
