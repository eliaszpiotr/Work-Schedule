from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from work_scheduler.i18n import Language, t
from work_scheduler.services import OpeningHoursService, RuleSetService, ServiceError
from work_scheduler.settings import PrintLanguage, Settings, ThemeMode
from work_scheduler.ui.components import (
    Card,
    PageHeader,
    PlainLabel,
    SegmentedControl,
    inset_divider,
    primary_button,
    restyle,
    set_button_icon,
    settings_row,
)
from work_scheduler.ui.settings.opening_hours_editor import OpeningHoursEditor
from work_scheduler.ui.settings.rule_sets_panel import RuleSetsPanel
from work_scheduler.ui.theme import METRICS, Palette

# A week of time fields does not get wider by being given the whole window.
SETTINGS_CARD_WIDTH = 680
ROW_INSET = METRICS.space_4


class SettingsView(QWidget):
    """One section at a time, picked from tabs: everything at once was a long scroll."""

    language_changed = Signal(object)
    theme_changed = Signal(object)

    def __init__(
        self,
        service: OpeningHoursService,
        palette: Palette,
        settings: Settings | None = None,
        rule_sets: RuleSetService | None = None,
    ) -> None:
        super().__init__()
        self.setObjectName("workspace")
        self._service = service
        self._palette = palette
        self._settings = settings if settings is not None else Settings()
        self._rule_sets = rule_sets

        self._editor = OpeningHoursEditor(service.week(), inset=ROW_INSET)
        self._save = primary_button(t("settings.hours.save"))
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
        self._pages: dict[str, QWidget] = {}
        self._order: list[str] = []
        self._current = ""
        # Plain pages that hide, not a QStackedWidget: a stack is as tall as its tallest
        # page, which stretched the three appearance rows to the height of the week.
        self._stack = QWidget()
        self._stack_layout = QVBoxLayout(self._stack)
        self._stack_layout.setContentsMargins(0, 0, 0, 0)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        header = PageHeader(t("settings.title"))
        layout.addWidget(header)

        sections = [
            ("appearance", t("settings.appearance.title"), self._appearance_page()),
            ("hours", t("settings.hours.tab"), self._hours_page()),
        ]
        if self._rule_sets is not None:
            sections.append(("rules", t("rules.title"), self._rules_page()))
        for key, _, page in sections:
            self._pages[key] = page
            self._order.append(key)
            self._stack_layout.addWidget(page)

        # The add for rule sets sits where every screen keeps its add: top right. It is
        # shown only while that tab is, so the header never offers what is not on screen.
        self._new_set = primary_button(t("rules.add_set"), "plus", self._palette)
        if self._rule_sets is not None:
            self._new_set.clicked.connect(self._rule_sets_panel.add_set)
            header.add_action(self._new_set)
        self._tabs = SegmentedControl([(title, key) for key, title, _ in sections])
        self._tabs.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self._tabs.changed.connect(lambda key: self.show_section(str(key)))

        panel = QFrame()
        panel.setObjectName("workspaceBody")
        body = QVBoxLayout(panel)
        body.setContentsMargins(METRICS.space_6, METRICS.space_2, METRICS.space_6, METRICS.space_6)
        body.setSpacing(METRICS.space_4)
        body.addWidget(self._tabs, alignment=Qt.AlignmentFlag.AlignLeft)
        # The pages column takes the rest of the height and packs its page to the top,
        # so a page always gets its full height instead of a cached guess at it.
        self._stack_layout.addStretch(1)
        body.addWidget(self._stack, stretch=1)
        self._panel, self._body = panel, body

        # At the window's minimum height the week needs more room than the page.
        # Scroll the content instead of squeezing the seven time fields over one another.
        scroller = QScrollArea()
        scroller.setObjectName("settingsScroll")
        scroller.setFrameShape(QFrame.Shape.NoFrame)
        scroller.setWidgetResizable(True)
        scroller.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroller.setWidget(panel)
        layout.addWidget(scroller, stretch=1)
        self.show_section(self._order[0])

    # Sections ---------------------------------------------------------------

    def section(self) -> str:
        return self._current

    def show_section(self, key: str) -> None:
        if key not in self._pages:
            return
        self._current = key
        self._tabs.select(key)
        for name, page in self._pages.items():
            page.setVisible(name == key)
        self._new_set.setVisible(key == "rules")
        # The scroll area only scrolls as far as the panel says it is tall; tell it the
        # height of the section now showing, not of the tallest one.
        if hasattr(self, "_panel"):
            self._panel.setMinimumHeight(self._body.sizeHint().height())

    @staticmethod
    def _page(hint: str, card: Card) -> tuple[QWidget, QVBoxLayout]:
        """A muted line saying what the section is for, then its card."""
        page = QWidget()
        # Capped as a whole, not per child: the layout works out a wrapped hint's height
        # from the page's width, and a wider page than the hint underestimated it.
        page.setMaximumWidth(SETTINGS_CARD_WIDTH)
        column = QVBoxLayout(page)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(METRICS.space_2)
        note = PlainLabel(hint)
        note.setObjectName("mutedText")
        note.setWordWrap(True)
        column.addWidget(note)
        column.addWidget(card)
        return page, column

    def _appearance_page(self) -> QWidget:
        """Language and theme belong to this machine, so they sit apart from the hours."""
        self._language.select(self._settings.language)
        self._theme.select(self._settings.theme)
        self._print_language.select(self._settings.print_language)
        self._language.changed.connect(self._pick_language)
        self._theme.changed.connect(self._pick_theme)
        self._print_language.changed.connect(self._pick_print_language)

        card = Card(padding=0)
        card.body().setSpacing(0)
        rows = (
            (t("settings.language"), self._language),
            (t("settings.theme"), self._theme),
            (t("settings.print_language"), self._print_language),
        )
        for index, (label, control) in enumerate(rows):
            if index:
                card.body().addWidget(inset_divider(ROW_INSET))
            control.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
            card.body().addWidget(settings_row(label, control, ROW_INSET))
        page, _ = self._page(t("settings.appearance.hint"), card)
        return page

    def _hours_page(self) -> QWidget:
        card = Card(padding=0)
        card.body().setSpacing(0)
        card.body().setContentsMargins(0, METRICS.space_1, 0, METRICS.space_1)
        card.body().addWidget(self._editor)
        page, column = self._page(t("settings.hours.hint"), card)

        # Save belongs to the hours: nothing else on this screen waits for it.
        self._save.clicked.connect(self.save)
        footer = QWidget()
        row = QHBoxLayout(footer)
        row.setContentsMargins(0, METRICS.space_1, 0, 0)
        self._status.setWordWrap(True)
        row.addWidget(self._status, stretch=1)
        row.addWidget(self._save)
        column.addWidget(footer)
        return page

    def _rules_page(self) -> QWidget:
        """The sets themselves, listed at once: the tab exists to show them."""
        self._rule_sets_panel = RuleSetsPanel(self._rule_sets, self._palette)
        page = QWidget()
        page.setMaximumWidth(SETTINGS_CARD_WIDTH)
        column = QVBoxLayout(page)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(METRICS.space_2)
        note = PlainLabel(t("rules.settings_hint"))
        note.setObjectName("mutedText")
        note.setWordWrap(True)
        column.addWidget(note)
        column.addWidget(self._rule_sets_panel)
        return page

    def _pick_language(self, value: object) -> None:
        self.language_changed.emit(Language(str(value)))

    def _pick_theme(self, value: object) -> None:
        self._settings.theme = ThemeMode(str(value))
        self.theme_changed.emit(ThemeMode(str(value)))

    def _pick_print_language(self, value: object) -> None:
        self._settings.print_language = PrintLanguage(str(value))

    def apply_palette(self, palette: Palette) -> None:
        self._palette = palette
        set_button_icon(self._new_set, "plus", palette.on_accent)
        if self._rule_sets is not None:
            self._rule_sets_panel.apply_palette(palette)

    def reload(self) -> None:
        self._editor.set_week(self._service.week())
        # People named in the rules may have been renamed on the employees screen.
        if self._rule_sets is not None:
            self._rule_sets_panel.reload()
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
