from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMainWindow
from sqlalchemy.orm import Session, sessionmaker

from work_scheduler.config import AppConfig
from work_scheduler.database.models import Employee


class MainWindow(QMainWindow):
    """Application shell. Real views are added in later phases."""

    def __init__(self, config: AppConfig, session_factory: sessionmaker[Session]) -> None:
        super().__init__()
        self._config = config
        self._session_factory = session_factory

        self.setWindowTitle(config.app_name)
        self.resize(1024, 720)

        placeholder = QLabel(config.app_name)
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(placeholder)
        self.statusBar().showMessage(self.database_summary())

    def database_summary(self) -> str:
        with self._session_factory() as session:
            employees = session.query(Employee).count()
        return f"Baza: {self._config.database_path}   |   pracownicy: {employees}"
