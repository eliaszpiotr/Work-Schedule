from PySide6.QtCore import QModelIndex, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem

from work_scheduler.ui.components import initials, trade_colours
from work_scheduler.ui.theme import METRICS, Palette

NAME_COLUMN, PROFESSION_COLUMN, STATUS_COLUMN = 0, 1, 2
# Kept here rather than imported from the view, which imports this module.
PROFESSION_ROLE = Qt.ItemDataRole.UserRole + 2

AVATAR = 30
BADGE_HEIGHT = 21
BADGE_PADDING = 9
DOT = 7
GAP = METRICS.space_3


class EmployeeDelegate(QStyledItemDelegate):
    """Draws the rows itself: initials, a pill for the trade, a dot for the state.

    The stylesheet cannot do any of this — a table cell takes one string, and every
    rule with ``::item`` in it makes Qt paint the cell and ignore the model's colours.
    """

    def __init__(self, palette: Palette, parent=None) -> None:  # noqa: ANN001 - QObject
        super().__init__(parent)
        self._palette = palette

    def set_palette(self, palette: Palette) -> None:
        self._palette = palette

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        text = index.data() or ""
        box = QRectF(option.rect)

        # Painting the cell ourselves means the sheet's ``::item`` border never runs,
        # so the line under each row has to be drawn here or the table loses its rules.
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor(self._palette.surface_active))
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.fillRect(option.rect, QColor(self._palette.surface_hover))

        painter.setPen(QPen(QColor(self._palette.border), 1))
        painter.drawLine(box.bottomLeft(), box.bottomRight())

        if index.column() == NAME_COLUMN:
            self._draw_person(painter, box, text, active=self._is_active(index))
        elif index.column() == PROFESSION_COLUMN:
            self._draw_badge(painter, box, text, index)
        elif index.column() == STATUS_COLUMN:
            self._draw_status(painter, box, text, active=self._is_active(index))
        else:
            self._draw_text(painter, box.adjusted(GAP, 0, 0, 0), text, self._palette.text_primary)

        painter.restore()

    @staticmethod
    def _is_active(index: QModelIndex) -> bool:
        return index.sibling(index.row(), STATUS_COLUMN).data() == "Aktywny"

    # Pieces -----------------------------------------------------------------

    def _draw_person(self, painter: QPainter, box: QRectF, name: str, *, active: bool) -> None:
        circle = QRectF(box.x() + GAP, box.center().y() - AVATAR / 2, AVATAR, AVATAR)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self._palette.surface_active))
        painter.drawEllipse(circle)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        self._draw_text(
            painter,
            circle,
            initials(name),
            self._palette.text_secondary,
            size=10.5,
            weight=QFont.Weight.DemiBold,
            align=Qt.AlignmentFlag.AlignCenter,
        )

        # A name nobody schedules any more is still a name: greyed, never hidden.
        colour = self._palette.text_primary if active else self._palette.text_muted
        rest = QRectF(circle.right() + METRICS.space_3, box.y(), box.width(), box.height())
        self._draw_text(painter, rest, name, colour, size=13.5, weight=QFont.Weight.Medium)

    def _draw_badge(self, painter: QPainter, box: QRectF, text: str, index: QModelIndex) -> None:
        painter.setFont(self._font(11, QFont.Weight.Medium))
        width = painter.fontMetrics().horizontalAdvance(text) + 2 * BADGE_PADDING
        fill, ink = trade_colours(index.data(PROFESSION_ROLE), self._palette)

        pill = QRectF(box.x() + GAP, box.center().y() - BADGE_HEIGHT / 2, width, BADGE_HEIGHT)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(fill))
        painter.drawRoundedRect(pill, BADGE_HEIGHT / 2, BADGE_HEIGHT / 2)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(ink)))
        painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, text)

    def _draw_status(self, painter: QPainter, box: QRectF, text: str, *, active: bool) -> None:
        dot = QRectF(box.x() + GAP, box.center().y() - DOT / 2, DOT, DOT)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self._palette.success if active else self._palette.text_muted))
        painter.drawEllipse(dot)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        rest = QRectF(dot.right() + METRICS.space_2, box.y(), box.width(), box.height())
        colour = self._palette.text_primary if active else self._palette.text_muted
        self._draw_text(painter, rest, text, colour, size=13)

    # Text -------------------------------------------------------------------

    def _font(self, size: float, weight: QFont.Weight) -> QFont:
        font = QFont()
        font.setPointSizeF(size)
        font.setWeight(weight)
        return font

    def _draw_text(
        self,
        painter: QPainter,
        box: QRectF,
        text: str,
        colour: str,
        *,
        size: float = 13.5,
        weight: QFont.Weight = QFont.Weight.Normal,
        align: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignLeft,
    ) -> None:
        painter.setFont(self._font(size, weight))
        painter.setPen(QPen(QColor(colour)))
        painter.drawText(box, align | Qt.AlignmentFlag.AlignVCenter, text)

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex):  # noqa: N802, ANN201
        hint = super().sizeHint(option, index)
        hint.setHeight(METRICS.table_row_height + METRICS.space_3)
        return hint
