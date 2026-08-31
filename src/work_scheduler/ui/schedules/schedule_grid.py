from datetime import date, time

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    QPoint,
    QRectF,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemDelegate,
    QAbstractItemView,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMenu,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from work_scheduler.i18n import profession_name, t
from work_scheduler.services import (
    EmployeeService,
    ScheduleData,
    ScheduleService,
    ServiceError,
    ShiftService,
)
from work_scheduler.services.audit import Audit, audit
from work_scheduler.services.coverage import Uncovered, uncovered_days
from work_scheduler.services.schedule_service import DayInfo
from work_scheduler.services.time_text import (
    format_hours,
    format_range,
    minutes_between,
    parse_range,
)
from work_scheduler.ui.components import (
    Badge,
    PlainLabel,
    confirm_destructive,
    icon_button,
    primary_button,
    restyle,
    secondary_button,
    set_button_icon,
)
from work_scheduler.ui.schedules.finalize_dialog import FinalizeDialog, Outcome
from work_scheduler.ui.schedules.schedule_card import status_badge
from work_scheduler.ui.schedules.schedule_edit_dialog import DayHoursDialog, ScheduleTeamDialog
from work_scheduler.ui.theme import METRICS, Palette


def totals_label() -> str:
    return t("grid.total_hours")


def trade_name(profession: object) -> str:
    return profession_name(profession)


STATUS_LINGER_MS = 5000


class ScheduleGridModel(QAbstractTableModel):
    """Rows are days of the period; people run across the columns."""

    rejected = Signal(str)
    reopened = Signal()
    totals_changed = Signal()

    def __init__(
        self,
        schedule: ScheduleData,
        shifts: ShiftService,
        palette: Palette,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._shifts = shifts
        self._palette = palette
        self._schedule = schedule
        self._timeline = schedule.timeline()
        self._cells = shifts.grid(schedule.id)
        self._uncovered: dict[date, Uncovered] = {}
        self._recheck_coverage()

    def set_schedule(self, schedule: ScheduleData) -> None:
        """After a day is opened or closed by hand the whole shape can change."""
        self.beginResetModel()
        self._schedule = schedule
        self._timeline = schedule.timeline()
        self._cells = self._shifts.grid(schedule.id)
        self._recheck_coverage()
        self.endResetModel()
        self.totals_changed.emit()

    def _recheck_coverage(self) -> None:
        self._uncovered = uncovered_days(self._schedule, self._cells)

    @property
    def schedule(self) -> ScheduleData:
        return self._schedule

    @property
    def cells(self) -> dict[tuple[int, date], tuple[time, time]]:
        """The grid as plain values, for the pre-closing check and the printout."""
        return dict(self._cells)

    def day_at(self, row: int) -> DayInfo:
        return self._timeline[row]

    # Shape ------------------------------------------------------------------

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802 - Qt API
        return 0 if parent and parent.isValid() else len(self._timeline)

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802 - Qt API
        return 0 if parent and parent.isValid() else len(self._schedule.lanes)

    def headerData(  # noqa: N802 - Qt API
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> str | None:
        if orientation is Qt.Orientation.Horizontal:
            if role == Qt.ItemDataRole.DisplayRole:
                return self._schedule.lanes[section].name
            return None

        info = self._timeline[section]
        if role == Qt.ItemDataRole.DisplayRole:
            return self._day_label(info)
        return None

    def _day_label(self, info: DayInfo) -> str:
        # Row colours and the legend communicate exceptional days without hover text.
        return info.label

    # Contents ---------------------------------------------------------------

    def _hours_at(self, index: QModelIndex) -> tuple[time, time] | None:
        lane = self._schedule.lanes[index.column()].id
        return self._cells.get((lane, self._timeline[index.row()].day))

    @staticmethod
    def _outside_opening(info: DayInfo, hours: tuple[time, time]) -> bool:
        if info.closed:
            return True
        return hours[0] < info.opens or hours[1] > info.closes

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):  # noqa: ANN201
        if not index.isValid():
            return None

        info = self._timeline[index.row()]
        hours = self._hours_at(index)

        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return format_range(*hours) if hours else ""

        if role == Qt.ItemDataRole.BackgroundRole:
            # A breach of the opening hours belongs to one cell, so it wins there; a day
            # with no pharmacist colours its whole row; then holidays; grey last.
            if hours and self._outside_opening(info, hours):
                return QColor(self._palette.warning_surface)
            if info.day in self._uncovered:
                return QColor(self._palette.danger_surface)
            if info.holiday:
                return QColor(self._palette.holiday_surface)
            if info.closed:
                return QColor(self._palette.surface_active)
            return None

        if role == Qt.ItemDataRole.TextAlignmentRole:
            return int(Qt.AlignmentFlag.AlignCenter)
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        flags = super().flags(index)
        if self._timeline[index.row()].closed:
            return flags & ~Qt.ItemFlag.ItemIsEditable
        return flags | Qt.ItemFlag.ItemIsEditable

    def setData(  # noqa: N802 - Qt API
        self, index: QModelIndex, value: object, role: int = Qt.ItemDataRole.EditRole
    ) -> bool:
        if not index.isValid() or role != Qt.ItemDataRole.EditRole:
            return False

        info = self._timeline[index.row()]
        if info.closed:
            self.rejected.emit(
                t("grid.closed_that_day", holiday=info.holiday)
                if info.holiday
                else t("grid.closed_plain")
            )
            return False

        day = info.day
        lane = self._schedule.lanes[index.column()].id
        text = str(value).strip()

        if not text:
            return self._write(index, lane, day, None)

        hours = parse_range(text)
        if hours is None:
            self.rejected.emit(t("grid.unparsed", text=text))
            return False
        return self._write(index, lane, day, hours)

    def _write(
        self, index: QModelIndex, lane: int, day: date, hours: tuple[time, time] | None
    ) -> bool:
        """One edited cell, one transaction. Nothing is held back in memory."""
        try:
            if hours is None:
                fell_back = self._shifts.clear_shift(lane, day)
                self._cells.pop((lane, day), None)
            else:
                fell_back = self._shifts.set_shift(lane, day, *hours)
                self._cells[lane, day] = hours
        except ServiceError as error:
            self.rejected.emit(str(error))
            return False

        if fell_back:
            self.reopened.emit()

        # One cell changing can settle or break the cover for the whole row, and the
        # row header carries that verdict, so both have to be repainted.
        self._recheck_coverage()
        self.dataChanged.emit(
            index.siblingAtColumn(0), index.siblingAtColumn(self.columnCount() - 1)
        )
        self.headerDataChanged.emit(Qt.Orientation.Vertical, index.row(), index.row())
        self.totals_changed.emit()
        return True

    # Totals -----------------------------------------------------------------

    def totals(self) -> list[int]:
        """Minutes per column, in column order."""
        summed = dict.fromkeys((lane.id for lane in self._schedule.lanes), 0)
        for (lane, _), (start, end) in self._cells.items():
            summed[lane] += minutes_between(start, end)
        return [summed[lane.id] for lane in self._schedule.lanes]

    def suggestions(self, row: int) -> list[str]:
        """Opening hours of that day first, then whatever is already used elsewhere."""
        info = self._timeline[row]
        used = {format_range(*hours) for hours in self._cells.values()}
        if not info.closed:
            used.add(format_range(info.opens, info.closes))
        return sorted(used)

    def uncovered(self) -> list[Uncovered]:
        return [self._uncovered[day] for day in sorted(self._uncovered)]

    def apply_palette(self, palette: Palette) -> None:
        self._palette = palette
        if self.rowCount() and self.columnCount():
            self.dataChanged.emit(
                self.index(0, 0), self.index(self.rowCount() - 1, self.columnCount() - 1)
            )


class ShiftDelegate(QStyledItemDelegate):
    """Draws a cell from end to end: fill, rule, text, and the cursor outline.

    Nothing is left to the stylesheet. Qt's own grid lines and a stylesheet border react
    to state — selected, hovered, first, last — and the table ended up ruled unevenly.
    Painting every cell the same way here is what makes the table look identical
    whatever is in it.
    """

    def __init__(
        self,
        model: ScheduleGridModel,
        view: QTableView,
        palette: Palette,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._view = view
        self._palette = palette

    def set_palette(self, palette: Palette) -> None:
        self._palette = palette

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        painter.save()
        painter.setClipRect(option.rect)

        colour = index.data(Qt.ItemDataRole.BackgroundRole)
        painter.fillRect(option.rect, QColor(colour or self._palette.background))

        self._draw_rules(painter, option, index)
        self._draw_text(painter, option, index)
        if index == self._view.currentIndex():
            self._draw_cursor(painter, option)

        painter.restore()

    def _draw_rules(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        """Internal rules only; the card supplies the outside edge."""
        painter.setPen(QPen(QColor(self._palette.border), 1))
        right, bottom = option.rect.right(), option.rect.bottom()
        if index.column() < self._model.columnCount() - 1:
            painter.drawLine(right, option.rect.top(), right, bottom)
        painter.drawLine(option.rect.left(), bottom, right, bottom)

    def _draw_text(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        text = index.data(Qt.ItemDataRole.DisplayRole)
        if not text:
            return
        painter.setPen(QColor(self._palette.text_primary))
        painter.drawText(option.rect, Qt.AlignmentFlag.AlignCenter, text)

    def _draw_cursor(self, painter: QPainter, option: QStyleOptionViewItem) -> None:
        """The cell you are on, outlined inside its own bounds so the rules stay put."""
        pen = QPen(QColor(self._palette.accent), 2)
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        painter.setPen(pen)
        painter.drawRect(option.rect.adjusted(1, 1, -2, -2))

    def createEditor(  # noqa: N802 - Qt API
        self, parent: QWidget, option: object, index: QModelIndex
    ) -> QWidget:
        editor = QLineEdit(parent)
        editor.setAlignment(Qt.AlignmentFlag.AlignCenter)
        editor.setFrame(False)
        return editor

    def updateEditorGeometry(  # noqa: N802 - Qt API
        self, editor: QWidget, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        # Fills the cell exactly; a smaller editor made the row jump while typing.
        editor.setGeometry(option.rect)


class LaneHeader(QHeaderView):
    """The column headings, painted rather than styled.

    A header section takes one string, so the trade under a name has to be drawn by
    hand — and it belongs here, because cover is checked against it.
    """

    def __init__(self, model: "ScheduleGridModel", palette: Palette, parent=None) -> None:  # noqa: ANN001
        super().__init__(Qt.Orientation.Horizontal, parent)
        self._model = model
        self._palette = palette
        self.setHighlightSections(False)
        self.setSectionsClickable(False)

    def set_palette(self, palette: Palette) -> None:
        self._palette = palette
        self.viewport().update()

    def sizeHint(self):  # noqa: N802, ANN201 - Qt API
        hint = super().sizeHint()
        hint.setHeight(METRICS.lane_header_height)
        return hint

    def paintSection(self, painter: QPainter, rect, index: int) -> None:  # noqa: N802, ANN001
        lanes = self._model.schedule.lanes
        if not 0 <= index < len(lanes):
            return

        painter.save()
        painter.fillRect(rect, QColor(self._palette.surface))

        painter.setPen(QPen(QColor(self._palette.border), 1))
        if index < len(lanes) - 1:
            painter.drawLine(rect.topRight(), rect.bottomRight())
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())

        lane = lanes[index]
        box = QRectF(rect)
        name = QRectF(box.x(), box.y() + 8, box.width(), box.height() * 0.44)
        trade = QRectF(box.x(), box.center().y() + 1, box.width(), box.height() * 0.4)

        painter.setPen(QPen(QColor(self._palette.text_primary)))
        painter.setFont(self._font(12.5, QFont.Weight.DemiBold))
        painter.drawText(name, Qt.AlignmentFlag.AlignCenter, lane.name)

        painter.setPen(QPen(QColor(self._palette.text_muted)))
        painter.setFont(self._font(10, QFont.Weight.Normal))
        painter.drawText(trade, Qt.AlignmentFlag.AlignCenter, trade_name(lane.profession))
        painter.restore()

    @staticmethod
    def _font(size: float, weight: QFont.Weight) -> QFont:
        font = QFont()
        font.setPointSizeF(size)
        font.setWeight(weight)
        return font


class TotalsBar(QWidget):
    """A fixed footer painted from the table's live column geometry.

    It is deliberately not another QTableView. A second view has its own frame,
    viewport and scrollbar allowance, so its columns can never be guaranteed to land
    on precisely the same pixels as the schedule above it.
    """

    def __init__(
        self,
        model: ScheduleGridModel,
        table: QTableView,
        palette: Palette,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._table = table
        self._palette = palette
        self.setFixedHeight(METRICS.table_row_height)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        model.totals_changed.connect(self.update)
        model.modelReset.connect(self.update)
        table.horizontalHeader().sectionResized.connect(lambda *_: self.update())
        table.horizontalHeader().geometriesChanged.connect(self.update)
        table.horizontalScrollBar().valueChanged.connect(lambda *_: self.update())

    def set_palette(self, palette: Palette) -> None:
        self._palette = palette
        self.update()

    def column_rect(self, column: int) -> QRectF:
        """The employee cell in footer coordinates, derived from the real viewport."""
        left = self._table.viewport().geometry().left()
        return QRectF(
            left + self._table.columnViewportPosition(column),
            0,
            self._table.columnWidth(column) - 1,
            self.height() - 1,
        )

    def paintEvent(self, event) -> None:  # noqa: N802, ANN001 - Qt API
        painter = QPainter(self)
        painter.setClipRect(event.rect())
        painter.fillRect(self.rect(), QColor(self._palette.surface))

        painter.setPen(QPen(QColor(self._palette.border_strong), 1))
        painter.drawLine(self.rect().topLeft(), self.rect().topRight())

        viewport_left = self._table.viewport().geometry().left()
        painter.setPen(QPen(QColor(self._palette.border), 1))
        painter.drawLine(viewport_left - 1, 0, viewport_left - 1, self.height() - 1)

        label = QRectF(0, 0, viewport_left - 1, self.height())
        font = QFont(self.font())
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(QColor(self._palette.text_muted))
        painter.drawText(
            label.adjusted(METRICS.space_3, 0, -METRICS.space_2, 0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            totals_label(),
        )

        totals = self._model.totals()
        painter.setPen(QColor(self._palette.text_primary))
        for column, minutes in enumerate(totals):
            cell = self.column_rect(column)
            painter.drawText(cell, Qt.AlignmentFlag.AlignCenter, format_hours(minutes))
            if column < len(totals) - 1:
                painter.setPen(QPen(QColor(self._palette.border), 1))
                painter.drawLine(cell.right(), 0, cell.right(), self.height() - 1)
                painter.setPen(QColor(self._palette.text_primary))


class ScheduleGridView(QWidget):
    """The schedule itself: days down the side, people across the top, hours in between."""

    closed = Signal()
    finalized = Signal(int, bool)

    def __init__(
        self,
        schedule: ScheduleData,
        schedules: ScheduleService,
        shifts: ShiftService,
        palette: Palette,
        employees: EmployeeService | None = None,
    ) -> None:
        super().__init__()
        self.setObjectName("workspace")
        self._schedule = schedule
        self._schedules = schedules
        self._palette = palette
        self._employees = employees

        self._model = ScheduleGridModel(schedule, shifts, palette, self)
        self._table = QTableView()
        # Built here rather than in the body: the table is configured first and asks
        # the card for its height cap while doing it.
        self._card = QFrame()
        self._back = icon_button("chevron-left", t("grid.back_to_list"), palette)
        self._title = PlainLabel()
        self._status = PlainLabel()
        self._finish = primary_button(t("grid.finish"), "check", palette)
        self._edit_team = secondary_button(t("grid.edit_team"))
        self._edit_team.setEnabled(employees is not None)

        self._build()

    # Construction -----------------------------------------------------------

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._toolbar())

        self._configure_table()
        self._totals_bar = TotalsBar(self._model, self._table, self._palette, self._card)

        panel = QFrame()
        panel.setObjectName("workspaceBody")
        body = QVBoxLayout(panel)
        body.setContentsMargins(METRICS.space_6, METRICS.space_4, METRICS.space_6, METRICS.space_6)
        body.setSpacing(METRICS.space_3)
        body.addWidget(self._legend())

        # One outer frame, with the scrollable days and the fixed totals bar inside it.
        card = self._card
        card.setObjectName("gridCard")
        inside = QVBoxLayout(card)
        inside.setContentsMargins(0, 0, 0, 0)
        inside.setSpacing(0)
        inside.addWidget(self._table, stretch=1)
        inside.addWidget(self._totals_bar)
        self._fit_to_rows()

        body.addWidget(card, stretch=1)
        body.addWidget(self._status)
        # Holds the table against the top when the period is short.
        body.addStretch()
        layout.addWidget(panel, stretch=1)

        self._status.setWordWrap(True)
        self._status.hide()
        self._model.rejected.connect(self._complain)
        self._model.reopened.connect(self._note_reopened)

    def _toolbar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("toolbar")
        # Two lines of heading need more than a single-line toolbar.
        bar.setFixedHeight(METRICS.toolbar_height + METRICS.space_6)

        self._back.clicked.connect(self.closed.emit)
        self._title.setObjectName("sectionTitle")
        self._title.setText(self._schedule.name)

        self._badge = Badge(*status_badge(self._schedule.status))

        self._period = PlainLabel()
        self._period.setObjectName("mutedText")
        self._refresh_heading()

        # Name and state on one line, the period quietly under it: the toolbar is read
        # once on arrival and then ignored, so it may not take a whole line of chrome.
        heading = QHBoxLayout()
        heading.setSpacing(METRICS.space_2)
        heading.addWidget(self._title)
        heading.addWidget(self._badge)
        heading.addStretch()

        # Stretched top and bottom, or the lower label swells to fill the toolbar and
        # shoves the title off the top edge.
        stack = QVBoxLayout()
        stack.setContentsMargins(0, 0, 0, 0)
        stack.setSpacing(0)
        stack.addStretch()
        stack.addLayout(heading)
        stack.addWidget(self._period)
        stack.addStretch()

        row = QHBoxLayout(bar)
        row.setContentsMargins(METRICS.space_4, 0, METRICS.space_6, 0)
        row.setSpacing(METRICS.space_3)
        self._finish.clicked.connect(self.finish_schedule)
        self._edit_team.clicked.connect(self.edit_team)

        row.addWidget(self._back)
        row.addLayout(stack)
        row.addStretch()
        row.addWidget(self._edit_team)
        row.addWidget(self._finish)
        return bar

    def _refresh_heading(self) -> None:
        self._title.setText(self._schedule.name)
        self._period.setText(
            f"{self._schedule.start_date:%d.%m.%Y} – {self._schedule.end_date:%d.%m.%Y}"
            f"  ·  {t('count.days', count=len(self._schedule.days()))}"
            f"  ·  {t('count.people', count=len(self._schedule.lanes))}"
        )
        if hasattr(self, "_badge"):
            self._badge.set_text(*status_badge(self._schedule.status))

    def _legend(self) -> QWidget:
        """What the colours mean, spelled out.

        The grid says everything with colour and nothing with words, so without this
        the first red row is a puzzle rather than a warning.
        """
        strip = QWidget()
        row = QHBoxLayout(strip)
        row.setContentsMargins(2, 0, 2, 0)
        row.setSpacing(METRICS.space_4)

        for colour, text in (
            (self._palette.danger_surface, t("grid.legend.no_pharmacist")),
            (self._palette.warning_surface, t("grid.legend.outside")),
            (self._palette.holiday_surface, t("grid.legend.holiday")),
            (self._palette.surface_active, t("grid.closed")),
        ):
            row.addLayout(self._legend_entry(colour, text))

        row.addStretch()
        hint = PlainLabel(t("grid.hint"))
        hint.setObjectName("mutedText")
        row.addWidget(hint)
        self._legend_strip = strip
        return strip

    def _legend_entry(self, colour: str, text: str) -> QHBoxLayout:
        swatch = PlainLabel()
        swatch.setFixedSize(11, 11)
        swatch.setStyleSheet(
            f"background: {colour};"
            f"border: 1px solid {self._palette.border_strong};"
            "border-radius: 3px;"
        )
        label = PlainLabel(text)
        label.setObjectName("mutedText")

        entry = QHBoxLayout()
        entry.setSpacing(METRICS.space_1 + 2)
        entry.addWidget(swatch)
        entry.addWidget(label)
        return entry

    def _configure_table(self) -> None:
        # No "data" property here: the shared table styling reacts to state, and the grid
        # needs every cell to look the same. Its delegate draws the lot instead.
        self._table.setProperty("role", "grid")
        self._table.setModel(self._model)
        self._delegate = ShiftDelegate(self._model, self._table, self._palette, self)
        self._table.setItemDelegate(self._delegate)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self._table.setShowGrid(False)
        self._table.setCornerButtonEnabled(False)
        self._table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.AnyKeyPressed
        )
        self._table.verticalHeader().setFixedWidth(METRICS.grid_date_width)
        self._table.verticalHeader().setDefaultSectionSize(METRICS.table_row_height)
        self._table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)

        self._lane_header = LaneHeader(self._model, self._palette, self._table)
        self._table.setHorizontalHeader(self._lane_header)
        header = self._table.horizontalHeader()
        header.setMinimumSectionSize(METRICS.grid_column_width)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)

        dates = self._table.verticalHeader()
        dates.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        dates.customContextMenuRequested.connect(self._open_day_menu)

        self._model.modelReset.connect(self._fit_to_rows)
        header.geometriesChanged.connect(self._fit_to_rows)
        self._fit_to_rows()

    def _fit_to_rows(self) -> None:
        """Stop at the last row instead of stretching to the bottom of the window.

        The cap sits on the card, not on the table: the table has to be free to fill
        whatever the card is given, or a month collapses to its smallest size and
        leaves the rest of the window empty.
        """
        table_content = (
            self._table.horizontalHeader().height()
            + self._model.rowCount() * METRICS.table_row_height
            + 2 * self._table.frameWidth()
        )
        footer = self._totals_bar.height() if hasattr(self, "_totals_bar") else 0
        self._card.setMaximumHeight(table_content + footer + 2 * self._card.frameWidth())

    # Behaviour --------------------------------------------------------------

    def apply_palette(self, palette: Palette) -> None:
        self._palette = palette
        self._delegate.set_palette(palette)
        self._model.apply_palette(palette)
        self._lane_header.set_palette(palette)
        self._totals_bar.set_palette(palette)
        self._back.setIcon(self._back.icon())
        set_button_icon(self._finish, "check", palette.on_accent)

    def _complain(self, message: str) -> None:
        """Shown briefly and then gone, so nothing is left standing under the grid."""
        self._announce(message, "danger")

    def _clear_status(self) -> None:
        self._status.clear()
        self._status.hide()

    def _note_reopened(self) -> None:
        """Said plainly, because the status in the list has just changed underfoot."""
        self._announce(t("grid.back_to_draft"), "warning")

    def _announce(self, message: str, tone: str) -> None:
        self._status.setText(message)
        self._status.setProperty("tone", tone)
        restyle(self._status)
        self._status.show()
        QTimer.singleShot(STATUS_LINGER_MS, self._clear_status)

    # Closing the schedule ---------------------------------------------------

    def commit_open_editor(self) -> None:
        """Write out a cell somebody is still typing in.

        Qt keeps the editor alive until the view is destroyed and only then hands its
        value to the model. Closing a schedule with an editor open therefore wrote a
        shift *after* the schedule was marked ready, which pulled it straight back to
        draft — and the pre-closing check never saw what had just been typed.
        """
        editor = self._table.findChild(QLineEdit)
        if editor is None:
            return
        self._table.commitData(editor)
        self._table.closeEditor(editor, QAbstractItemDelegate.EndEditHint.NoHint)

    def check(self) -> Audit:
        """What the pre-closing check finds right now. Public so tests can ask."""
        self.commit_open_editor()
        return audit(self._model.schedule, self._model.cells)

    def finish_schedule(self) -> None:
        dialog = FinalizeDialog(self, self.check(), self._palette)
        if dialog.exec() != FinalizeDialog.DialogCode.Accepted:
            return
        if dialog.outcome is Outcome.CANCEL:
            return

        try:
            self._schedules.finalize(self._schedule.id)
        except ServiceError as error:
            self._complain(str(error))
            return

        self.finalized.emit(self._schedule.id, dialog.outcome is Outcome.CLOSE_AND_SAVE)

    # Opening and closing single days ----------------------------------------

    def _open_day_menu(self, position: QPoint) -> None:
        row = self._table.verticalHeader().logicalIndexAt(position)
        if row < 0 or row >= self._model.rowCount():
            return

        info = self._model.day_at(row)
        menu = QMenu(self)
        menu.addAction(t("grid.edit_day_hours"), lambda: self.edit_day_hours(row))
        menu.addSeparator()

        if info.closed:
            weekly = self._schedule.week[info.day.weekday()]
            label = (
                t("grid.work_this_day", hours=f"{weekly.opens:%H:%M}–{weekly.closes:%H:%M}")
                if not weekly.closed
                else t("grid.work_this_day", hours="8:00–20:00")
            )
            menu.addAction(label, lambda: self.set_day_working(row))
        else:
            menu.addAction(t("grid.close_day"), lambda: self.set_day_closed(row))

        if info.overridden:
            menu.addAction(t("grid.restore_default"), lambda: self.clear_day_override(row))

        menu.exec(self._table.verticalHeader().mapToGlobal(position))

    def edit_day_hours(self, row: int) -> None:
        """Set an opening-hours exception for one concrete calendar date."""
        if not 0 <= row < self._model.rowCount():
            return
        info = self._model.day_at(row)
        weekly = self._schedule.week[info.day.weekday()]
        suggested = (weekly.opens, weekly.closes) if not weekly.closed else (time(8), time(20))
        dialog = DayHoursDialog(self, info.day, info.opens, info.closes, suggested)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._override(info.day, *dialog.hours)
        self._announce(t("grid.day_hours.saved"), "success")

    def edit_team(self) -> None:
        """Replace schedule columns while preserving every retained person's shifts."""
        if self._employees is None:
            return
        selected = [lane.employee_id for lane in self._schedule.lanes]
        available = self._employees.list_employees(include_inactive=True)
        by_id = {employee.id: employee for employee in available}
        # Keep the existing column order stable. New candidates follow afterwards in
        # the employee list's normal order, so merely opening and saving the dialog
        # cannot unexpectedly shuffle an established schedule.
        employees = [by_id[employee_id] for employee_id in selected if employee_id in by_id]
        employees.extend(employee for employee in available if employee.id not in selected)
        dialog = ScheduleTeamDialog(
            self,
            employees,
            selected,
            self._palette,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        employee_ids = dialog.employee_ids
        if employee_ids == selected:
            return

        removed = [lane for lane in self._schedule.lanes if lane.employee_id not in employee_ids]
        shifted_lanes = {lane_id for lane_id, _day in self._model.cells}
        destructive = [lane.name for lane in removed if lane.id in shifted_lanes]
        if destructive and not confirm_destructive(
            self,
            t("grid.team.remove_title"),
            t("grid.team.remove_warning", names=", ".join(destructive)),
            t("grid.team.remove_action"),
            palette=self._palette,
            icon="user-round-x",
        ):
            return

        try:
            self._schedules.update_employees(self._schedule.id, employee_ids)
        except ServiceError as error:
            self._complain(str(error))
            return
        self._reload_schedule()
        self._announce(t("grid.team.saved"), "success")

    def set_day_working(self, row: int) -> None:
        """Open a day the calendar closed — a holiday the pharmacy decides to work."""
        info = self._model.day_at(row)
        weekly = self._schedule.week[info.day.weekday()]
        opens, closes = (weekly.opens, weekly.closes) if not weekly.closed else (time(8), time(20))
        self._override(info.day, opens, closes)

    def set_day_closed(self, row: int) -> None:
        self._override(self._model.day_at(row).day, None, None)

    def clear_day_override(self, row: int) -> None:
        day = self._model.day_at(row).day
        try:
            self._schedules.clear_override(self._schedule.id, day)
        except ServiceError as error:
            self._complain(str(error))
            return
        self._reload_schedule()

    def _override(self, day: date, opens: time | None, closes: time | None) -> None:
        try:
            self._schedules.override_day(self._schedule.id, day, opens, closes)
        except ServiceError as error:
            self._complain(str(error))
            return
        self._reload_schedule()

    def _reload_schedule(self) -> None:
        self._schedule = self._schedules.open_schedule(self._schedule.id)
        self._model.set_schedule(self._schedule)
        self._refresh_heading()
        self._clear_status()
