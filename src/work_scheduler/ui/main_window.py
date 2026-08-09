from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMainWindow

from work_scheduler.config import AppConfig


class MainWindow(QMainWindow):
    """Application shell. Real views are added in later phases."""

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.setWindowTitle(config.app_name)
        self.resize(1024, 720)

        placeholder = QLabel(config.app_name)
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(placeholder)
