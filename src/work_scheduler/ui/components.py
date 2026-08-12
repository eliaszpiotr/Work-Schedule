from collections.abc import Callable

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from work_scheduler.ui.icons import load_icon
from work_scheduler.ui.theme import METRICS, Palette


def _with_variant(button: QPushButton, variant: str) -> QPushButton:
    button.setProperty("variant", variant)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


def primary_button(
    text: str, icon: str | None = None, palette: Palette | None = None
) -> QPushButton:
    button = _with_variant(QPushButton(text), "primary")
    if icon and palette:
        button.setIcon(load_icon(icon, palette.on_accent, 16))
        button.setIconSize(QSize(16, 16))
    return button


def secondary_button(text: str) -> QPushButton:
    return _with_variant(QPushButton(text), "secondary")


def icon_button(name: str, tooltip: str, palette: Palette) -> QToolButton:
    button = QToolButton()
    button.setIcon(load_icon(name, palette.text_secondary))
    button.setIconSize(QSize(18, 18))
    button.setFixedSize(METRICS.icon_button, METRICS.icon_button)
    button.setToolTip(tooltip)
    # Icon-only controls need a name for screen readers.
    button.setAccessibleName(tooltip)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


class PageHeader(QFrame):
    """Compact application toolbar: title on the left, one primary action on the right."""

    def __init__(self, title: str) -> None:
        super().__init__()
        self.setObjectName("toolbar")
        self.setFixedHeight(METRICS.toolbar_height + METRICS.space_4)

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(METRICS.space_6, 0, METRICS.space_6, 0)
        self._layout.setSpacing(METRICS.space_2)

        heading = QLabel(title)
        heading.setObjectName("pageTitle")
        self._layout.addWidget(heading)
        self._layout.addStretch()

    def add_action(self, widget: QWidget) -> None:
        self._layout.addWidget(widget)


class EmptyState(QWidget):
    """Shown instead of content; always offers the way forward."""

    def __init__(
        self,
        title: str,
        description: str,
        action: tuple[str, Callable[[], None]] | None = None,
    ) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(METRICS.space_2)

        heading = QLabel(title)
        heading.setObjectName("emptyTitle")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle = QLabel(description)
        subtitle.setObjectName("mutedText")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(heading)
        layout.addWidget(subtitle)

        if action is not None:
            label, callback = action
            button = primary_button(label)
            button.clicked.connect(callback)
            row = QHBoxLayout()
            row.addStretch()
            row.addWidget(button)
            row.addStretch()
            layout.addSpacing(METRICS.space_2)
            layout.addLayout(row)
