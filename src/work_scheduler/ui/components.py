from collections.abc import Callable

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from work_scheduler.database.models import Profession
from work_scheduler.ui.icons import load_icon
from work_scheduler.ui.theme import METRICS, Palette

BUTTON_ICON_SIZE = 16

PROFESSION_LABELS: dict[Profession, str] = {
    Profession.PHARMACIST: "Magister",
    Profession.TECHNICIAN: "Technik",
}


def _with_variant(button: QPushButton, variant: str) -> QPushButton:
    button.setProperty("variant", variant)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


def restyle(widget: QWidget) -> None:
    """Qt only re-reads the stylesheet for a widget whose property changed if asked to."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def set_button_icon(button: QPushButton, name: str, colour: str) -> None:
    """Also used to repaint an existing button after the theme changes."""
    button.setIcon(load_icon(name, colour, BUTTON_ICON_SIZE))
    button.setIconSize(QSize(BUTTON_ICON_SIZE, BUTTON_ICON_SIZE))


def primary_button(
    text: str, icon: str | None = None, palette: Palette | None = None
) -> QPushButton:
    button = _with_variant(QPushButton(text), "primary")
    if icon and palette:
        set_button_icon(button, icon, palette.on_accent)
    return button


def secondary_button(text: str) -> QPushButton:
    return _with_variant(QPushButton(text), "secondary")


def danger_button(text: str) -> QPushButton:
    return _with_variant(QPushButton(text), "danger")


def destructive_question(
    parent: QWidget | None, title: str, message: str, action: str
) -> tuple[QMessageBox, QPushButton]:
    """A yes/no question with its own buttons.

    Qt's standard buttons arrive in English on macOS ("Cancel", "Yes") with Cancel as
    the default, so a Polish question ended up answered in another language — and Enter
    quietly cancelled. These are spelled out instead, with cancelling still the default.
    """
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle(title)
    box.setText(title)
    box.setInformativeText(message)

    confirm = box.addButton(action, QMessageBox.ButtonRole.DestructiveRole)
    cancel = box.addButton("Anuluj", QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(cancel)
    box.setEscapeButton(cancel)
    return box, confirm


def confirm_destructive(parent: QWidget | None, title: str, message: str, action: str) -> bool:
    box, confirm = destructive_question(parent, title, message, action)
    box.exec()
    return box.clickedButton() is confirm


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
