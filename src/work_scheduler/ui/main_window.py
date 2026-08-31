from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.orm import Session, sessionmaker

from work_scheduler.config import AppConfig
from work_scheduler.i18n import Language, set_language, t
from work_scheduler.services import (
    EmployeeService,
    OpeningHoursService,
    ScheduleService,
    ShiftService,
)
from work_scheduler.settings import Settings, ThemeMode
from work_scheduler.ui.components import BrandMark, PlainLabel, icon_button, restyle
from work_scheduler.ui.employees import EmployeesView
from work_scheduler.ui.icons import load_icon
from work_scheduler.ui.schedules.schedules_page import SchedulesPage
from work_scheduler.ui.settings import SettingsView
from work_scheduler.ui.theme import METRICS, ThemeManager

# Names are looked up when the sidebar is built, not when the module is imported,
# so switching language rebuilds them.
PAGE_ICONS = ("calendar-days", "users", "settings")
PAGE_KEYS = ("nav.schedules", "nav.employees", "nav.settings")
SCHEDULES_PAGE = 0

# The spacers around the collapse button, by position in the brand row.
LEADING_STRETCH, TRAILING_STRETCH = 2, 4


class MainWindow(QMainWindow):
    def __init__(
        self,
        config: AppConfig,
        session_factory: sessionmaker[Session],
        theme: ThemeManager | None = None,
        settings: Settings | None = None,
    ) -> None:
        super().__init__()
        self._config = config
        self._settings = settings if settings is not None else Settings()
        self._session_factory = session_factory
        self._theme = theme or ThemeManager(self._settings.theme)
        self._navigation = QListWidget()
        self._pages = QStackedWidget()
        self._collapsed = False

        self.setWindowTitle(config.app_name)
        self.resize(1180, 760)
        self.setMinimumSize(880, 560)

        self._create_pages()
        self._build()
        self._theme.changed.connect(self._refresh_icons)

    def _create_pages(self) -> None:
        """Built here rather than inline, because a language switch builds them again."""
        palette = self._theme.palette
        factory = self._session_factory
        self._schedules = SchedulesPage(
            ScheduleService(factory),
            EmployeeService(factory),
            OpeningHoursService(factory),
            ShiftService(factory),
            palette,
        )
        self._employees = EmployeesView(EmployeeService(factory), palette)
        self._settings_view = SettingsView(OpeningHoursService(factory), palette, self._settings)
        self._settings_view.language_changed.connect(self.set_language)
        self._settings_view.theme_changed.connect(self.set_theme)

    def _pages_in_order(self) -> tuple[QWidget, ...]:
        return (self._schedules, self._employees, self._settings_view)

    def set_language(self, language: Language) -> None:
        """Rebuild every screen in the new language, the way a theme change repaints them.

        An open schedule closes back to the list: its widgets are thrown away with the
        rest, and re-opening it is one click.
        """
        self._settings.language = language
        set_language(language)

        row = self._navigation.currentRow()
        for page in self._pages_in_order():
            self._pages.removeWidget(page)
            page.setParent(None)
            page.deleteLater()

        self._create_pages()
        for page in self._pages_in_order():
            self._pages.addWidget(page)

        self._fill_navigation()
        self._section.setText(t("nav.section"))
        self._collapse.setAccessibleName(
            t("sidebar.expand") if self._collapsed else t("sidebar.collapse")
        )
        self._navigation.setCurrentRow(row)
        self._show_page(row)

    def set_theme(self, mode: ThemeMode) -> None:
        self._settings.theme = mode
        application = QApplication.instance()
        if application is not None:
            self._theme.set_mode(mode, application)

    def _build(self) -> None:
        root = QWidget()
        root.setObjectName("window")
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._sidebar())
        layout.addWidget(self._pages, stretch=1)

        for page in self._pages_in_order():
            self._pages.addWidget(page)

        self._navigation.currentRowChanged.connect(self._show_page)
        self._navigation.setCurrentRow(SCHEDULES_PAGE)

        self.set_sidebar_collapsed(self._collapsed)
        self.setCentralWidget(root)

    def _sidebar(self) -> QFrame:
        sidebar = self._sidebar_frame = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(METRICS.sidebar_width)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(
            METRICS.space_3, METRICS.space_5, METRICS.space_3, METRICS.space_4
        )
        layout.setSpacing(METRICS.space_2)

        self._mark = BrandMark(self._theme.palette)
        self._brand_name = PlainLabel(self._config.app_name)
        self._brand_name.setObjectName("brand")
        self._collapse = icon_button("panel-left", t("sidebar.collapse"), self._theme.palette)
        self._collapse.clicked.connect(self.toggle_sidebar)

        self._brand = QWidget()
        self._brand_row = QHBoxLayout(self._brand)
        self._brand_row.setContentsMargins(METRICS.space_2, 0, 0, METRICS.space_3)
        self._brand_row.setSpacing(METRICS.space_2)
        self._brand_row.addWidget(self._mark)
        self._brand_row.addWidget(self._brand_name)
        # Both spacers are spelled out: addStretch() with no argument has a factor of
        # zero and pushes nothing anywhere, which is not what the name suggests.
        self._brand_row.addStretch(1)
        self._brand_row.addWidget(self._collapse)
        self._brand_row.addStretch(0)

        self._section = PlainLabel(t("nav.section"))
        self._section.setObjectName("sectionLabel")

        self._navigation.setObjectName("navigation")
        self._navigation.setFrameShape(QFrame.Shape.NoFrame)
        self._navigation.setIconSize(QSize(18, 18))
        self._navigation.setSpacing(2)
        self._navigation.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._fill_navigation()

        shortcut = QShortcut(QKeySequence("Ctrl+B"), self)
        shortcut.activated.connect(self.toggle_sidebar)

        layout.addWidget(self._brand)
        layout.addWidget(self._section)
        layout.addWidget(self._navigation, stretch=1)
        return sidebar

    def _fill_navigation(self) -> None:
        # Refilled on a language change as well as on a collapse, so it starts empty
        # rather than appending a second set of entries underneath the first.
        self._navigation.clear()
        colour = self._theme.palette.text_secondary
        # Collapsed, the highlight is the only thing saying which screen is open, so it
        # has to be a square centred under its icon rather than a band as wide as the
        # panel happens to be.
        side = METRICS.sidebar_collapsed - 2 * METRICS.space_3
        # Width left at zero so the row spans the panel exactly; a fixed width wider
        # than the viewport pushes every icon off centre by the overflow.
        size = QSize(0, side) if self._collapsed else QSize(0, METRICS.nav_item_height + 4)

        for key, icon in zip(PAGE_KEYS, PAGE_ICONS, strict=True):
            name = t(key)
            item = QListWidgetItem(load_icon(icon, colour), "" if self._collapsed else name)
            item.setData(Qt.ItemDataRole.AccessibleTextRole, name)
            item.setSizeHint(size)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._navigation.addItem(item)

    # The sidebar ------------------------------------------------------------

    @property
    def collapsed(self) -> bool:
        return self._collapsed

    def toggle_sidebar(self) -> None:
        self.set_sidebar_collapsed(not self._collapsed)

    def set_sidebar_collapsed(self, collapsed: bool) -> None:
        """Narrow the sidebar to its icons and let every screen take the room.

        Nothing else has to be told: the pages already stretch into whatever is left,
        so widening them is a matter of the sidebar asking for less.
        """
        self._collapsed = collapsed
        self._sidebar_frame.setFixedWidth(
            METRICS.sidebar_collapsed if collapsed else METRICS.sidebar_width
        )
        self._brand_name.setVisible(not collapsed)
        self._section.setVisible(not collapsed)
        self._collapse.setAccessibleName(
            t("sidebar.expand") if collapsed else t("sidebar.collapse")
        )

        # Collapsed, the two controls do not fit side by side; the mark steps aside so
        # the one that brings the sidebar back is the one that stays reachable.
        self._mark.setVisible(not collapsed)

        self._brand_row.setContentsMargins(
            0 if collapsed else METRICS.space_2, 0, 0, METRICS.space_3
        )
        # Spacing left in place would be counted once beside the button and push it a
        # few pixels off the axis the icons below sit on.
        self._brand_row.setSpacing(0 if collapsed else METRICS.space_2)
        # Stretched on one side the button sits right; on both, it centres on the same
        # axis as the icons below it.
        self._brand_row.setStretch(LEADING_STRETCH, 1)
        self._brand_row.setStretch(TRAILING_STRETCH, 1 if collapsed else 0)

        # Icon-only entries have no room for the padding a label needs beside them.
        self._navigation.setProperty("collapsed", "true" if collapsed else None)
        restyle(self._navigation)

        row = self._navigation.currentRow()
        self._fill_navigation()
        self._navigation.setCurrentRow(row)

    def _show_page(self, row: int) -> None:
        """Screens read from the database on arrival, so edits elsewhere are never stale."""
        self._pages.setCurrentIndex(row)
        page = self._pages.widget(row)
        if hasattr(page, "reload"):
            page.reload()

    def _refresh_icons(self) -> None:
        palette = self._theme.palette
        self._mark.apply_palette(palette)
        for row, icon in enumerate(PAGE_ICONS):
            self._navigation.item(row).setIcon(load_icon(icon, palette.text_secondary))
        for page in self._pages_in_order():
            page.apply_palette(palette)
