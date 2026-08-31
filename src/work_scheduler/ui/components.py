from collections.abc import Callable

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
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


def trade_colours(profession: Profession | str | None, palette: Palette) -> tuple[str, str]:
    """Background and ink for a trade badge, as one rule for every screen.

    The two trades are told apart by colour, not only by the word: cover is checked
    against pharmacists, so a column of badges has to answer "who is a magister"
    without being read. The pharmacist takes the tinted one; the technician stays
    neutral, because it is the absence of a pharmacist that matters.

    Compared by value, never by identity. ``Profession`` is a ``StrEnum``, and a value
    carried through a Qt model arrives back as a plain ``str`` — an ``is`` test against
    the enum is then quietly false for everybody, and every badge comes out the same
    colour with nothing to show that anything went wrong.
    """
    if profession == Profession.PHARMACIST:
        return palette.holiday_surface, palette.holiday_ink
    return palette.surface_active, palette.text_secondary


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


class PlainLabel(QLabel):
    """A label that shows exactly the characters it was handed.

    Qt guesses whether a string is HTML and renders it as markup when it looks like it.
    Every name on these screens is typed into the kartoteka by somebody, so a surname
    with an angle bracket in it would rearrange a dialog instead of appearing in it.
    """

    def __init__(self, text: str = "") -> None:
        super().__init__(text)
        self.setTextFormat(Qt.TextFormat.PlainText)


class Glyph(PlainLabel):
    """A tinted square holding one icon: what is about to happen, before it is read."""

    def __init__(self, icon: str, tone: str, palette: Palette) -> None:
        super().__init__()
        self.setProperty("glyph", tone)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        colour = {
            "danger": palette.danger,
            "warning": palette.warning,
            "info": palette.holiday_ink,
        }[tone]
        self.setPixmap(load_icon(icon, colour, 19).pixmap(19, 19))


class ConfirmDialog(QDialog):
    """A question with its own window rather than the platform's.

    Qt's standard buttons arrive in English on macOS ("Cancel", "Yes") with Cancel as
    the default, so a Polish question ended up answered in another language — and Enter
    quietly cancelled. These are spelled out, cancelling is still what Enter does, and
    the window is built from the same parts as the rest of the application.
    """

    def __init__(
        self,
        parent: QWidget | None,
        title: str,
        message: str,
        action: str,
        *,
        palette: Palette,
        icon: str = "trash-2",
        tone: str = "danger",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(METRICS.dialog_width)

        heading = PlainLabel(title)
        heading.setObjectName("dialogTitle")
        heading.setWordWrap(True)

        body = PlainLabel(message)
        body.setObjectName("dialogBody")
        body.setWordWrap(True)

        words = QVBoxLayout()
        words.setContentsMargins(0, 0, 0, 0)
        words.setSpacing(METRICS.space_1 + 1)
        words.addWidget(heading)
        words.addWidget(body)
        words.addStretch()

        top = QHBoxLayout()
        top.setSpacing(METRICS.space_3)
        top.addWidget(Glyph(icon, tone, palette), alignment=Qt.AlignmentFlag.AlignTop)
        top.addLayout(words, stretch=1)

        self._confirm = _with_variant(QPushButton(action), "dangerFilled")
        self._cancel = secondary_button("Anuluj")
        self._confirm.clicked.connect(self.accept)
        self._cancel.clicked.connect(self.reject)
        # Enter must not delete anything: the safe answer keeps the focus.
        self._cancel.setDefault(True)

        buttons = QHBoxLayout()
        buttons.setSpacing(METRICS.space_2)
        buttons.addStretch()
        buttons.addWidget(self._cancel)
        buttons.addWidget(self._confirm)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            METRICS.space_6, METRICS.space_5, METRICS.space_6, METRICS.space_5
        )
        layout.setSpacing(METRICS.space_5)
        layout.addLayout(top)
        layout.addLayout(buttons)

    @property
    def confirm_button(self) -> QPushButton:
        return self._confirm

    @property
    def cancel_button(self) -> QPushButton:
        return self._cancel


def confirm_destructive(
    parent: QWidget | None,
    title: str,
    message: str,
    action: str,
    *,
    palette: Palette,
    icon: str = "trash-2",
) -> bool:
    dialog = ConfirmDialog(parent, title, message, action, palette=palette, icon=icon)
    return dialog.exec() == QDialog.DialogCode.Accepted


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

        heading = PlainLabel(title)
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

        heading = PlainLabel(title)
        heading.setObjectName("emptyTitle")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle = PlainLabel(description)
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


def initials(name: str) -> str:
    """Two letters for the avatar. "Kowalska Anna" reads as KA, not as KO."""
    parts = [part for part in name.replace("-", " ").split() if part]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[1][0]).upper()


class Avatar(PlainLabel):
    """A circle with someone's initials, where a photograph would be if we had one."""

    def __init__(self, name: str, *, accent: bool = False) -> None:
        super().__init__(initials(name))
        self.setProperty("avatar", "accent" if accent else "plain")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAccessibleName(name)


class Badge(PlainLabel):
    """A state said in one glance. The tone chooses the colour; the word carries it."""

    TONES = ("neutral", "success", "info", "muted")

    def __init__(self, text: str, tone: str = "neutral") -> None:
        super().__init__(text)
        self.set_tone(tone)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def set_tone(self, tone: str) -> None:
        if tone not in self.TONES:
            raise ValueError(f"Unknown badge tone: {tone}")
        self.setProperty("badge", tone)
        restyle(self)

    def set_text(self, text: str, tone: str | None = None) -> None:
        self.setText(text)
        if tone is not None:
            self.set_tone(tone)


class Card(QFrame):
    """A panel that holds one thing. Padding and radius come from the sheet."""

    def __init__(self, *, padding: int | None = None) -> None:
        super().__init__()
        self.setObjectName("card")
        inner = METRICS.card_padding if padding is None else padding
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(inner, inner, inner, inner)
        self.layout_.setSpacing(METRICS.space_3)

    def body(self) -> QVBoxLayout:
        return self.layout_


class SegmentedControl(QWidget):
    """One row of choices, all of them visible.

    Replaces a dropdown for short, fixed lists: a filter nobody can see is a filter
    nobody uses, and three options do not earn a popup.
    """

    changed = Signal(object)

    def __init__(self, options: list[tuple[str, object]]) -> None:
        super().__init__()
        self.setObjectName("segmented")
        self._values: list[object] = []

        row = QHBoxLayout(self)
        row.setContentsMargins(3, 3, 3, 3)
        row.setSpacing(2)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        for index, (label, value) in enumerate(options):
            button = QPushButton(label)
            button.setProperty("segment", "true")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setChecked(index == 0)
            self._group.addButton(button, index)
            self._values.append(value)
            row.addWidget(button)

        self._group.idClicked.connect(lambda index: self.changed.emit(self._values[index]))

    def value(self) -> object:
        return self._values[self._group.checkedId()]

    def select(self, value: object) -> None:
        if value not in self._values:
            return
        self._group.button(self._values.index(value)).setChecked(True)


class BrandMark(PlainLabel):
    """The filled square in the sidebar holding the application's icon."""

    def __init__(self, palette: Palette) -> None:
        super().__init__()
        self.setObjectName("brandMark")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.apply_palette(palette)

    def apply_palette(self, palette: Palette) -> None:
        self.setPixmap(load_icon("calendar-days", palette.on_accent, 16).pixmap(16, 16))
