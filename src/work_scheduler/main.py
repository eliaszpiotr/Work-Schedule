import logging
import sys

from PySide6.QtWidgets import QApplication

from work_scheduler.config import AppConfig
from work_scheduler.logging_config import setup_logging
from work_scheduler.ui.main_window import MainWindow

logger = logging.getLogger(__name__)


def create_application(argv: list[str] | None = None) -> tuple[QApplication, MainWindow]:
    config = AppConfig()
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(config.app_name)
    app.setApplicationVersion(config.version)
    app.setOrganizationName(config.organization_name)

    window = MainWindow(config)
    return app, window


def main() -> int:
    setup_logging()
    app, window = create_application()
    logger.info("Starting %s %s", app.applicationName(), app.applicationVersion())

    window.show()
    exit_code = app.exec()

    logger.info("Shutting down with exit code %s", exit_code)
    return exit_code
