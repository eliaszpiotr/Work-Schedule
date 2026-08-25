from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.orm import Session, sessionmaker

from work_scheduler.config import AppConfig
from work_scheduler.services import (
    EmployeeService,
    OpeningHoursService,
    ScheduleService,
    ShiftService,
)
from work_scheduler.ui.employees import EmployeesView
from work_scheduler.ui.icons import load_icon
from work_scheduler.ui.schedules.schedules_page import SchedulesPage
from work_scheduler.ui.settings import SettingsView
from work_scheduler.ui.theme import METRICS, ThemeManager

PAGES = (
    ("Grafiki", "calendar-days"),
    ("Pracownicy", "users"),
    ("Ustawienia", "settings"),
)
SCHEDULES_PAGE = 0


class MainWindow(QMainWindow):
    def __init__(
        self,
        config: AppConfig,
        session_factory: sessionmaker[Session],
        theme: ThemeManager | None = None,
    ) -> None:
        super().__init__()
        self._config = config
        self._theme = theme or ThemeManager()
        self._navigation = QListWidget()
        self._pages = QStackedWidget()

        self.setWindowTitle(config.app_name)
        self.resize(1180, 760)
        self.setMinimumSize(880, 560)

        palette = self._theme.palette
        self._schedules = SchedulesPage(
            ScheduleService(session_factory),
            EmployeeService(session_factory),
            OpeningHoursService(session_factory),
            ShiftService(session_factory),
            palette,
        )
        self._employees = EmployeesView(EmployeeService(session_factory), palette)
        self._settings = SettingsView(OpeningHoursService(session_factory), palette)

        self._build()
        self._theme.changed.connect(self._refresh_icons)

    def _build(self) -> None:
        root = QWidget()
        root.setObjectName("window")
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._sidebar())
        layout.addWidget(self._pages, stretch=1)

        self._pages.addWidget(self._schedules)
        self._pages.addWidget(self._employees)
        self._pages.addWidget(self._settings)

        self._navigation.currentRowChanged.connect(self._show_page)
        self._navigation.setCurrentRow(SCHEDULES_PAGE)

        self.setCentralWidget(root)
        self.statusBar().showMessage(self.database_summary())

    def _sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(METRICS.sidebar_width)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(
            METRICS.space_3, METRICS.space_5, METRICS.space_3, METRICS.space_4
        )
        layout.setSpacing(METRICS.space_2)

        brand = QLabel(self._config.app_name)
        brand.setObjectName("brand")
        brand.setContentsMargins(METRICS.space_2, 0, 0, METRICS.space_2)

        section = QLabel("WIDOKI")
        section.setObjectName("sectionLabel")

        self._navigation.setObjectName("navigation")
        self._navigation.setFrameShape(QFrame.Shape.NoFrame)
        self._navigation.setIconSize(QSize(18, 18))
        self._navigation.setSpacing(2)
        self._navigation.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._fill_navigation()

        layout.addWidget(brand)
        layout.addWidget(section)
        layout.addWidget(self._navigation, stretch=1)
        return sidebar

    def _fill_navigation(self) -> None:
        colour = self._theme.palette.text_secondary
        for name, icon in PAGES:
            item = QListWidgetItem(load_icon(icon, colour), name)
            item.setSizeHint(QSize(0, METRICS.nav_item_height + METRICS.space_1))
            self._navigation.addItem(item)

    def _show_page(self, row: int) -> None:
        """Screens read from the database on arrival, so edits elsewhere are never stale."""
        self._pages.setCurrentIndex(row)
        page = self._pages.widget(row)
        if hasattr(page, "reload"):
            page.reload()

    def _refresh_icons(self) -> None:
        palette = self._theme.palette
        for row, (_, icon) in enumerate(PAGES):
            self._navigation.item(row).setIcon(load_icon(icon, palette.text_secondary))
        for page in (self._schedules, self._employees, self._settings):
            page.apply_palette(palette)

    def database_summary(self) -> str:
        return f"Baza: {self._config.database_path}"
