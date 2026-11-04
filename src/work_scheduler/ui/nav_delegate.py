from PySide6.QtCore import QModelIndex, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QIcon, QPainter, QPen
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem, QWidget

from work_scheduler.ui.theme import METRICS, Palette

ICON = 18
# Space between the capsule's left edge and the icon, then between icon and label.
LEAD = 10
GAP = 10


class NavDelegate(QStyledItemDelegate):
    """Draws the sidebar entries: a capsule behind the open screen, icon, label.

    Qt's own item drawing always puts the icon at the row's left edge, whatever the
    text alignment says, so a collapsed row of icons never sat on the panel's axis.
    Painting here puts it exactly where the design wants it, in both widths.
    """

    def __init__(self, palette: Palette, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._palette = palette
        self._collapsed = False

    def set_palette(self, palette: Palette) -> None:
        self._palette = palette

    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = collapsed

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        box = self._capsule(QRectF(option.rect))

        if selected or hovered:
            fill = self._palette.accent if selected else self._palette.surface_hover
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(fill))
            painter.drawRoundedRect(box, METRICS.nav_radius, METRICS.nav_radius)

        icon = index.data(Qt.ItemDataRole.DecorationRole)
        mode = QIcon.Mode.Selected if selected else QIcon.Mode.Normal
        if self._collapsed:
            spot = QRectF(0, 0, ICON, ICON)
            spot.moveCenter(box.center())
        else:
            spot = QRectF(box.left() + LEAD, box.center().y() - ICON / 2, ICON, ICON)
        if isinstance(icon, QIcon):
            icon.paint(painter, spot.toRect(), Qt.AlignmentFlag.AlignCenter, mode)

        text = index.data(Qt.ItemDataRole.DisplayRole)
        if text and not self._collapsed:
            ink = self._palette.on_accent if selected else self._palette.text_primary
            painter.setPen(QPen(QColor(ink)))
            font = QFont(option.font)
            if selected:
                font.setWeight(QFont.Weight.Medium)
            painter.setFont(font)
            label = QRectF(
                spot.right() + GAP, box.top(), box.right() - spot.right() - GAP, box.height()
            )
            elided = QFontMetrics(font).elidedText(
                text, Qt.TextElideMode.ElideRight, int(label.width())
            )
            painter.drawText(
                label, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided
            )

        painter.restore()

    def _capsule(self, row: QRectF) -> QRectF:
        """Collapsed, a square on the row's centre; expanded, the whole row."""
        if not self._collapsed:
            return row
        side = min(row.width(), row.height())
        square = QRectF(0, 0, side, side)
        square.moveCenter(row.center())
        return square

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:  # noqa: N802
        hint = index.data(Qt.ItemDataRole.SizeHintRole)
        return hint if isinstance(hint, QSize) else super().sizeHint(option, index)
