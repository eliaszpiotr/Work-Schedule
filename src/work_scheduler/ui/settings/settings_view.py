from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFormLayout, QFrame, QSizePolicy, QVBoxLayout, QWidget

from work_scheduler.i18n import Language, t
from work_scheduler.services import OpeningHoursService, ServiceError
from work_scheduler.settings import PrintLanguage, Settings, ThemeMode
from work_scheduler.ui.components import (
    Card,
    PageHeader,
    PlainLabel,
    SegmentedControl,
    primary_button,
    restyle,
)
from work_scheduler.ui.settings.opening_hours_editor import OpeningHoursEditor
from work_scheduler.ui.theme import METRICS, Palette

# A week of time fields does not get wider by being given the whole window.
SETTINGS_CARD_WIDTH = 680


class SettingsView(QWidget):
    language_changed = Signal(object)
    theme_changed = Signal(object)

    def __init__(
        self,
        service: OpeningHoursService,
        palette: Palette,
        settings: Settings | None = None,
    ) -> None:
        super().__init__()
        self.setObjectName("workspace")
        self._service = service
        self._palette = palette
        self._settings = settings if settings is not None else Settings()

        self._editor = OpeningHoursEditor(service.week())
        self._save = primary_button(t("common.save"))
        self._status = PlainLabel()
        self._language = SegmentedControl(
            [(t("settings.language.pl"), Language.PL), (t("settings.language.en"), Language.EN)]
        )
        self._theme = SegmentedControl(
            [
                (t("settings.theme.system"), ThemeMode.SYSTEM),
                (t("settings.theme.light"), ThemeMode.LIGHT),
                (t("settings.theme.dark"), ThemeMode.DARK),
            ]
        )
        self._print_language = SegmentedControl(
            [
                (t("settings.print_language.ui"), PrintLanguage.UI),
                (t("settings.language.pl"), PrintLanguage.PL),
                (t("settings.language.en"), PrintLanguage.EN),
            ]
        )
        self._build()

    def _build(self) -> None:
        header = PageHeader(t("settings.title"))
        self._save.clicked.connect(self.save)
        header.add_action(self._save)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(header)

        section = PlainLabel(t("settings.hours.title"))
        section.setObjectName("sectionTitle")
        hint = PlainLabel(t("settings.hours.hint"))
        hint.setObjectName("mutedText")
        hint.setWordWrap(True)

        # The week sits in a card of its own: on a screen holding one thing, the panel
        # is what tells the reader where that thing begins and ends.
        card = Card()
        card.body().setSpacing(METRICS.space_2)
        card.body().addWidget(section)
        card.body().addWidget(hint)
        card.body().addSpacing(METRICS.space_2)
        card.body().addWidget(self._editor)
        card.setMaximumWidth(SETTINGS_CARD_WIDTH)

        panel = QFrame()
        panel.setObjectName("workspaceBody")
        body = QVBoxLayout(panel)
        body.setContentsMargins(METRICS.space_6, METRICS.space_5, METRICS.space_6, METRICS.space_6)
        body.setSpacing(METRICS.space_3)
        body.addWidget(self._appearance_card())
        body.addWidget(card)
        body.addWidget(self._status)
        body.addStretch()
        layout.addWidget(panel, stretch=1)

    def _appearance_card(self) -> Card:
        """Language and theme belong to this machine, so they sit apart from the hours."""
        section = PlainLabel(t("settings.appearance.title"))
        section.setObjectName("sectionTitle")
        hint = PlainLabel(t("settings.appearance.hint"))
        hint.setObjectName("mutedText")
        hint.setWordWrap(True)

        self._language.select(self._settings.language)
        self._theme.select(self._settings.theme)
        self._print_language.select(self._settings.print_language)

        self._language.changed.connect(self._pick_language)
        self._theme.changed.connect(self._pick_theme)
        self._print_language.changed.connect(self._pick_print_language)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(METRICS.space_2)
        for label, control in (
            (t("settings.language"), self._language),
            (t("settings.theme"), self._theme),
            (t("settings.print_language"), self._print_language),
        ):
            caption = PlainLabel(label)
            caption.setObjectName("fieldLabel")
            # Segments sized to their words. Stretched across the form they read as
            # three separate buttons rather than one control with a choice made in it.
            control.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
            form.addRow(caption, control)

        card = Card()
        card.body().setSpacing(METRICS.space_2)
        card.body().addWidget(section)
        card.body().addWidget(hint)
        card.body().addSpacing(METRICS.space_2)
        card.body().addLayout(form)
        card.setMaximumWidth(SETTINGS_CARD_WIDTH)
        return card

    def _pick_language(self, value: object) -> None:
        self.language_changed.emit(Language(str(value)))

    def _pick_theme(self, value: object) -> None:
        self._settings.theme = ThemeMode(str(value))
        self.theme_changed.emit(ThemeMode(str(value)))

    def _pick_print_language(self, value: object) -> None:
        self._settings.print_language = PrintLanguage(str(value))

    def apply_palette(self, palette: Palette) -> None:
        self._palette = palette

    def reload(self) -> None:
        self._editor.set_week(self._service.week())
        self._say("", tone="")

    def save(self) -> None:
        try:
            self._service.save(self._editor.week())
        except ServiceError as error:
            self._say(str(error), tone="danger")
            return

        self._say(t("settings.hours.saved"), tone="success")

    def _say(self, message: str, *, tone: str) -> None:
        """A line under the form rather than a modal box; saving is not worth a click."""
        self._status.setText(message)
        self._status.setProperty("tone", tone)
        restyle(self._status)
