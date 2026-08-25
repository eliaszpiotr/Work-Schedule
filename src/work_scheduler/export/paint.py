from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QFontMetricsF, QPainter, QPen

from work_scheduler.ui.resources import FONT_FILE

# Print has its own palette. The screen theme may be dark; paper never is.
INK = QColor("#1A1A1A")
MUTED = QColor("#6E6E6E")
HAIRLINE = QColor("#DCDCDA")
HEADER_FILL = QColor("#F1F1EF")
SATURDAY_FILL = QColor("#ECECEC")
SUNDAY_FILL = QColor("#D9D9D9")
CLOSED_FILL = QColor("#C7C7C7")
HOLIDAY_FILL = QColor("#E4EEFA")
HOLIDAY_INK = QColor("#3F6295")

POINTS_PER_INCH = 72
FALLBACK_FAMILY = "Helvetica"

LEFT = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
RIGHT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
CENTRE = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter

_family: str | None = None


def font_family() -> str:
    """The application's own face, so paper and screen say things the same way."""
    global _family
    if _family is None:
        loaded = QFontDatabase.addApplicationFont(str(FONT_FILE))
        families = QFontDatabase.applicationFontFamilies(loaded) if loaded != -1 else []
        _family = families[0] if families else FALLBACK_FAMILY
    return _family


@dataclass(frozen=True, slots=True)
class Sheet:
    """One page, measured in points, whatever resolution the device happens to have.

    A painter on a printer works in device pixels, so the page is scaled to points once
    and every size below is a point. Font sizes have to be divided back out: Qt resolves
    a point size against the device's own dpi, which under the scale would apply the
    same factor a second time and print a heading half a page tall.
    """

    painter: QPainter
    width: float
    height: float
    scale: float

    @classmethod
    def open(cls, painter: QPainter, device) -> "Sheet":  # noqa: ANN001 - QPagedPaintDevice
        scale = device.logicalDpiX() / POINTS_PER_INCH
        painter.save()
        painter.scale(scale, scale)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        return cls(painter, device.width() / scale, device.height() / scale, scale)

    def close(self) -> None:
        self.painter.restore()

    def font(self, size: float, bold: bool = False) -> QFont:
        face = QFont(font_family())
        face.setPointSizeF(size / self.scale)
        face.setWeight(QFont.Weight.DemiBold if bold else QFont.Weight.Normal)
        return face

    def fit(self, font: QFont, text: str, width: float, padding: float = 6) -> QFont:
        """Shrink a font until the string fits the box. Nothing is ever cut in half."""
        size = font.pointSizeF()
        while size > 1 and self.advance(font, text) > width - padding:
            size *= 0.94
            font.setPointSizeF(size)
        return font

    def advance(self, font: QFont, text: str) -> float:
        # Measured against the device: without it the metrics assume 96 dpi and every
        # width comes out wrong by the scale factor.
        return QFontMetricsF(font, self.painter.device()).horizontalAdvance(text)

    def text(
        self,
        rect: QRectF,
        value: str,
        font: QFont,
        colour: QColor = INK,
        align: Qt.AlignmentFlag = CENTRE,
    ) -> None:
        self.painter.setFont(font)
        self.painter.setPen(QPen(colour))
        self.painter.drawText(rect, align, value)

    def shrunk_text(
        self,
        rect: QRectF,
        value: str,
        font: QFont,
        colour: QColor = INK,
        align: Qt.AlignmentFlag = CENTRE,
    ) -> None:
        self.text(rect, value, self.fit(font, value, rect.width()), colour, align)

    def fill(self, rect: QRectF, colour: QColor) -> None:
        self.painter.fillRect(rect, colour)

    def rule(self, y: float, colour: QColor = HAIRLINE, thickness: float = 1) -> None:
        self.painter.setPen(QPen(colour, thickness))
        self.painter.drawLine(QPointF(0, y), QPointF(self.width, y))

    def outline(self, rect: QRectF, colour: QColor = HAIRLINE) -> None:
        self.painter.setPen(QPen(colour, 1))
        self.painter.setBrush(Qt.BrushStyle.NoBrush)
        self.painter.drawRect(rect)

    # Page furniture ---------------------------------------------------------

    def heading(self, title: str, subtitle: str, aside: str = "") -> float:
        """Title block at the top. Returns the y where the content may start."""
        self.shrunk_text(
            QRectF(0, 0, self.width * 0.68, 40), title, self.font(22, bold=True), INK, LEFT
        )
        self.text(QRectF(0, 44, self.width, 20), subtitle, self.font(10.5), MUTED, LEFT)
        if aside:
            self.text(QRectF(0, 4, self.width, 20), aside, self.font(9), MUTED, RIGHT)
        self.rule(74, INK, 2)
        return 92
