from PySide6.QtCore import QModelIndex, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem

from work_scheduler.ui.components import initials, trade_colours
from work_scheduler.ui.theme import METRICS, Palette

NAME_ROLE = Qt.ItemDataRole.UserRole + 1
TRADE_ROLE = Qt.ItemDataRole.UserRole + 2
PROFESSION_ROLE = Qt.ItemDataRole.UserRole + 3

AVATAR = 28
BADGE_HEIGHT = 20
BADGE_PADDING = 8
CHECKBOX = 18
GAP = METRICS.space_3


class PersonDelegate(QStyledItemDelegate):
    """Rows in the picker drawn the way the employees screen draws them.

    Without this the wizard is the one place in the application where a person is a
    line of plain text — the same list, told two different ways.
    """

    def __init__(self, palette: Palette, parent=None) -> None:  # noqa: ANN001 - QObject
        super().__init__(parent)
        self._palette = palette

    def set_palette(self, palette: Palette) -> None:
        self._palette = palette

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        box = QRectF(option.rect)
        checked = index.data(Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Checked

        if option.state & QStyle.StateFlag.State_MouseOver:
            painter.fillRect(option.rect, QColor(self._palette.surface_hover))

        left = self._draw_check(painter, box, checked)
        left = self._draw_avatar(painter, box, left, index.data(NAME_ROLE) or "")
        self._draw_name(painter, box, left, index)

        painter.setPen(QPen(QColor(self._palette.border), 1))
        painter.drawLine(box.bottomLeft(), box.bottomRight())
        painter.restore()

    # Pieces -----------------------------------------------------------------

    def _draw_check(self, painter: QPainter, box: QRectF, checked: bool) -> float:
        mark = QRectF(box.x() + GAP, box.center().y() - CHECKBOX / 2, CHECKBOX, CHECKBOX)
        edge = self._palette.accent if checked else self._palette.border_strong
        painter.setPen(QPen(QColor(edge)))
        painter.setBrush(QColor(self._palette.accent) if checked else Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(mark, METRICS.radius_sm, METRICS.radius_sm)

        if checked:
            painter.setPen(QPen(QColor(self._palette.on_accent), 2))
            painter.drawLine(
                mark.x() + 4.5, mark.center().y(), mark.center().x() - 0.5, mark.bottom() - 5
            )
            painter.drawLine(
                mark.center().x() - 0.5, mark.bottom() - 5, mark.right() - 4, mark.y() + 5.5
            )
        return mark.right()

    def _draw_avatar(self, painter: QPainter, box: QRectF, left: float, name: str) -> float:
        circle = QRectF(left + GAP, box.center().y() - AVATAR / 2, AVATAR, AVATAR)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self._palette.surface_active))
        painter.drawEllipse(circle)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(self._palette.text_secondary)))
        painter.setFont(self._font(10, QFont.Weight.DemiBold))
        painter.drawText(circle, Qt.AlignmentFlag.AlignCenter, initials(name))
        return circle.right()

    def _draw_name(self, painter: QPainter, box: QRectF, left: float, index: QModelIndex) -> None:
        name = index.data(NAME_ROLE) or ""
        trade = index.data(TRADE_ROLE) or ""
        fill, ink = trade_colours(index.data(PROFESSION_ROLE), self._palette)

        painter.setFont(self._font(13, QFont.Weight.Medium))
        painter.setPen(QPen(QColor(self._palette.text_primary)))
        width = painter.fontMetrics().horizontalAdvance(name)
        painter.drawText(
            QRectF(left + METRICS.space_3, box.y(), width + 2, box.height()),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            name,
        )

        painter.setFont(self._font(10.5, QFont.Weight.Medium))
        pill_width = painter.fontMetrics().horizontalAdvance(trade) + 2 * BADGE_PADDING
        pill = QRectF(
            left + METRICS.space_3 + width + METRICS.space_3,
            box.center().y() - BADGE_HEIGHT / 2,
            pill_width,
            BADGE_HEIGHT,
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(fill))
        painter.drawRoundedRect(pill, BADGE_HEIGHT / 2, BADGE_HEIGHT / 2)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(ink)))
        painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, trade)

    @staticmethod
    def _font(size: float, weight: QFont.Weight) -> QFont:
        font = QFont()
        font.setPointSizeF(size)
        font.setWeight(weight)
        return font

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex):  # noqa: N802, ANN201
        hint = super().sizeHint(option, index)
        hint.setHeight(METRICS.picker_row_height)
        return hint
