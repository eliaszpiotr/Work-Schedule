from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from work_scheduler.database.models import ScheduleStatus
from work_scheduler.services import ScheduleSummary
from work_scheduler.ui.components import Badge, Card, PlainLabel, icon_button, restyle
from work_scheduler.ui.text import days as count_days
from work_scheduler.ui.text import people as count_people
from work_scheduler.ui.theme import METRICS, Palette

STATUS_LABELS = {
    ScheduleStatus.DRAFT: "Roboczy",
    ScheduleStatus.FINAL: "Gotowy",
    ScheduleStatus.ARCHIVED: "Archiwalny",
}
STATUS_TONES = {
    ScheduleStatus.DRAFT: "neutral",
    ScheduleStatus.FINAL: "success",
    ScheduleStatus.ARCHIVED: "muted",
}


def status_badge(status: ScheduleStatus) -> tuple[str, str]:
    """The word and the tone for a schedule's state, in one place for every screen."""
    return STATUS_LABELS[status], STATUS_TONES[status]


class ScheduleCard(Card):
    """One schedule on the list.

    A card rather than a table row: the table stretched empty over half the window
    whatever it held, and a row of four columns had nowhere to put the state.
    """

    picked = Signal(int)
    opened = Signal(int)
    menu_requested = Signal(int, QPoint)

    def __init__(self, summary: ScheduleSummary, palette: Palette) -> None:
        super().__init__()
        self.schedule = summary
        self._palette = palette
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)

        self._menu = icon_button("ellipsis", "Więcej", palette)
        self._menu.clicked.connect(self._open_menu)

        self.body().setSpacing(METRICS.space_2)
        self.body().addLayout(self._heading(summary))
        self.body().addWidget(self._meta(summary))

    # Construction -----------------------------------------------------------

    def _heading(self, summary: ScheduleSummary) -> QHBoxLayout:
        title = PlainLabel(summary.name)
        title.setObjectName("cardTitle")

        row = QHBoxLayout()
        row.setSpacing(METRICS.space_2)
        row.addWidget(title)
        row.addWidget(Badge(*status_badge(summary.status)))
        row.addStretch()
        row.addWidget(self._menu)
        return row

    @staticmethod
    def _meta(summary: ScheduleSummary) -> QWidget:
        parts = [
            summary.period,
            count_days(summary.day_count),
            count_people(summary.employee_count),
        ]
        label = PlainLabel("  ·  ".join(parts))
        label.setObjectName("secondaryText")
        return label

    # Appearance -------------------------------------------------------------

    def apply_palette(self, palette: Palette) -> None:
        self._palette = palette
        self._menu.setIcon(self._menu.icon())

    def set_picked(self, picked: bool) -> None:
        self.setProperty("selected", "true" if picked else None)
        restyle(self)

    # Behaviour --------------------------------------------------------------

    def _open_menu(self) -> None:
        self.picked.emit(self.schedule.id)
        corner = self._menu.mapToGlobal(QPoint(0, self._menu.height()))
        self.menu_requested.emit(self.schedule.id, corner)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        self.picked.emit(self.schedule.id)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        self.opened.emit(self.schedule.id)
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event) -> None:  # noqa: N802, ANN001 - Qt API
        # Qt does not move the selection on a right-click, so the card has to.
        self.picked.emit(self.schedule.id)
        self.menu_requested.emit(self.schedule.id, event.globalPos())


class CardList(QWidget):
    """The cards stacked with room to breathe, and nothing where there are none."""

    def __init__(self) -> None:
        super().__init__()
        self._column = QVBoxLayout(self)
        self._column.setContentsMargins(0, 0, 0, 0)
        self._column.setSpacing(METRICS.space_3)
        self._column.addStretch()

    def cards(self) -> list[ScheduleCard]:
        return self.findChildren(ScheduleCard)

    def add(self, card: ScheduleCard) -> None:
        # Before the stretch, or every card lands at the bottom of the panel.
        self._column.insertWidget(self._column.count() - 1, card)

    def clear(self) -> None:
        """Unparented at once, not just scheduled for deletion.

        ``deleteLater`` leaves the widget a child until the event loop turns, so a
        rebuilt list would keep answering with the cards it had just thrown away.
        """
        for card in self.cards():
            self._column.removeWidget(card)
            card.setParent(None)
            card.deleteLater()
