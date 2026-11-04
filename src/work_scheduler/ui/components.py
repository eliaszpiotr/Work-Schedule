from collections.abc import Callable

from PySide6.QtCore import Property, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListView,
    QPushButton,
    QSizePolicy,
    QStyleFactory,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from work_scheduler.database.models import Profession
from work_scheduler.i18n import profession_label, t
from work_scheduler.ui.icons import load_icon
from work_scheduler.ui.theme import METRICS, Palette

BUTTON_ICON_SIZE = 16


def profession_labels() -> dict[Profession, str]:
    """Looked up on each call, so a language switch reaches every screen using it."""
    return {profession: profession_label(profession) for profession in Profession}


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
        return palette.work_surface, palette.work_ink
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


class StyledComboBox(QComboBox):
    """Use the same inset menu and selection colours on macOS and other platforms."""

    def __init__(self, palette: Palette, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # The macOS style replaces a non-editable combo popup with a native menu.
        # Fusion keeps the list view and its app colours visible everywhere.
        self.setStyle(QStyleFactory.create("Fusion"))
        view = QListView(self)
        view.setSpacing(METRICS.space_1)
        view.setUniformItemSizes(True)
        self.setView(view)
        self.setMaxVisibleItems(10)
        view.setStyleSheet(f"""
            QListView {{
                background: {palette.elevated};
                border: 1px solid {palette.border_strong};
                padding: {METRICS.space_1}px;
                outline: none;
            }}
            QListView::item {{
                min-height: {METRICS.control_height}px;
                padding: 0 {METRICS.space_3}px;
                border-radius: {METRICS.radius_sm}px;
                color: {palette.text_primary};
            }}
            QListView::item:hover, QListView::item:selected {{
                background: {palette.surface_active};
                color: {palette.text_primary};
            }}
        """)


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
        self._cancel = secondary_button(t("common.cancel"))
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


def icon_button(name: str, accessible_name: str, palette: Palette) -> QToolButton:
    button = QToolButton()
    button.setIcon(load_icon(name, palette.text_secondary))
    button.setIconSize(QSize(18, 18))
    button.setFixedSize(METRICS.icon_button, METRICS.icon_button)
    # Icon-only controls need a name for screen readers.
    button.setAccessibleName(accessible_name)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


def round_icon_button(name: str, accessible_name: str, palette: Palette) -> QToolButton:
    button = QToolButton()
    button.setProperty("variant", "roundPrimary")
    button.setIcon(load_icon(name, palette.on_accent))
    button.setIconSize(QSize(16, 16))
    button.setAccessibleName(accessible_name)
    button.setToolTip(accessible_name)
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
            button = secondary_button(label)
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


class Switch(QCheckBox):
    """An on/off switch, drawn rather than styled.

    Still a QCheckBox underneath, so ``setChecked`` and ``toggled`` work as they did.
    The colours come from the stylesheet through ``qproperty-``, which is what lets a
    theme change repaint it with no code of its own.
    """

    WIDTH, HEIGHT, INSET = 38, 22, 2

    def __init__(self, accessible_name: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("role", "switch")
        self.setAccessibleName(accessible_name)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(self.WIDTH, self.HEIGHT)
        self._on, self._off, self._knob = QColor("#007AFF"), QColor("#E8E8ED"), QColor("#FFFFFF")

    def _get_on(self) -> QColor:
        return self._on

    def _set_on(self, colour: QColor) -> None:
        self._on = QColor(colour)
        self.update()

    def _get_off(self) -> QColor:
        return self._off

    def _set_off(self, colour: QColor) -> None:
        self._off = QColor(colour)
        self.update()

    def _get_knob(self) -> QColor:
        return self._knob

    def _set_knob(self, colour: QColor) -> None:
        self._knob = QColor(colour)
        self.update()

    onColor = Property(QColor, _get_on, _set_on)  # noqa: N815 - named for qproperty-onColor
    offColor = Property(QColor, _get_off, _set_off)  # noqa: N815
    knobColor = Property(QColor, _get_knob, _set_knob)  # noqa: N815

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt API
        return QSize(self.WIDTH, self.HEIGHT)

    def hitButton(self, position) -> bool:  # noqa: N802, ANN001 - Qt API
        return self.rect().contains(position)

    def paintEvent(self, event) -> None:  # noqa: N802, ANN001 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.isEnabled():
            painter.setOpacity(0.5)
        track = QRectF(self.rect())
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._on if self.isChecked() else self._off)
        painter.drawRoundedRect(track, track.height() / 2, track.height() / 2)

        side = track.height() - 2 * self.INSET
        left = track.right() - self.INSET - side if self.isChecked() else track.left() + self.INSET
        painter.setBrush(self._knob)
        painter.drawEllipse(QRectF(left, track.top() + self.INSET, side, side))
        painter.end()


def inset_divider(inset: int) -> QWidget:
    """A hairline between rows that starts where the text does, as in System Settings."""
    holder = QWidget()
    row = QHBoxLayout(holder)
    row.setContentsMargins(inset, 0, 0, 0)
    line = QFrame()
    line.setObjectName("rowDivider")
    line.setFixedHeight(1)
    row.addWidget(line)
    return holder


def settings_row(label: str, control: QWidget, inset: int = METRICS.space_4) -> QFrame:
    """One line of a settings card: what it is on the left, the control on the right."""
    frame = QFrame()
    frame.setObjectName("settingsRow")
    row = QHBoxLayout(frame)
    row.setContentsMargins(inset, METRICS.space_3, inset, METRICS.space_3)
    row.setSpacing(METRICS.space_3)
    caption = PlainLabel(label)
    caption.setWordWrap(True)
    row.addWidget(caption, stretch=1)
    row.addWidget(control, alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    # A wrapped hint above the card must not be able to borrow this row's height.
    frame.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    return frame
