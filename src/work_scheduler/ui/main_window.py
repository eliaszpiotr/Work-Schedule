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
from work_scheduler.services import EmployeeService
from work_scheduler.ui.components import EmptyState
from work_scheduler.ui.employees import EmployeesView
from work_scheduler.ui.icons import load_icon
from work_scheduler.ui.theme import METRICS, ThemeManager

PAGES = (
    ("Grafik", "calendar-days"),
    ("Pracownicy", "users"),
    ("Raporty", "chart-column"),
    ("Ustawienia", "settings"),
)
EMPLOYEES_PAGE = 1


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

        self._employees = EmployeesView(EmployeeService(session_factory), self._theme.palette)
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

        self._pages.addWidget(EmptyState("Grafik", "Edytor grafiku powstanie w kolejnym etapie."))
        self._pages.addWidget(self._employees)
        self._pages.addWidget(
            EmptyState("Raporty", "Zestawienia godzin pojawią się po zbudowaniu grafiku.")
        )
        self._pages.addWidget(EmptyState("Ustawienia", "Na razie nie ma czego ustawiać."))

        self._navigation.currentRowChanged.connect(self._pages.setCurrentIndex)
        # Employees is the only finished screen, so the application opens on it.
        self._navigation.setCurrentRow(EMPLOYEES_PAGE)

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

    def _refresh_icons(self) -> None:
        colour = self._theme.palette.text_secondary
        for row, (_, icon) in enumerate(PAGES):
            self._navigation.item(row).setIcon(load_icon(icon, colour))

    def database_summary(self) -> str:
        return f"Baza: {self._config.database_path}"
