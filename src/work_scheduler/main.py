import logging
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox
from sqlalchemy.orm import Session, sessionmaker

from work_scheduler.config import AppConfig
from work_scheduler.database.bootstrap import DatabaseUnavailableError, prepare_database
from work_scheduler.database.session import create_session_factory
from work_scheduler.logging_config import setup_logging
from work_scheduler.ui.main_window import MainWindow
from work_scheduler.ui.resources import APP_ICON
from work_scheduler.ui.theme import ThemeManager

logger = logging.getLogger(__name__)


def create_qt_application(
    config: AppConfig, argv: list[str] | None = None
) -> tuple[QApplication, ThemeManager]:
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(config.app_name)
    app.setApplicationVersion(config.version)
    app.setOrganizationName(config.organization_name)
    if APP_ICON.is_file():
        app.setWindowIcon(QIcon(str(APP_ICON)))

    theme = ThemeManager()
    theme.follow_system(app)
    return app, theme


def create_application(
    argv: list[str] | None = None,
    *,
    session_factory: sessionmaker[Session],
    config: AppConfig | None = None,
) -> tuple[QApplication, MainWindow]:
    config = config or AppConfig()
    app, theme = create_qt_application(config, argv)
    return app, MainWindow(config, session_factory, theme)


def main() -> int:
    setup_logging()
    config = AppConfig()
    app, theme = create_qt_application(config)
    logger.info("Starting %s %s", config.app_name, config.version)

    try:
        engine = prepare_database(config.database_path)
    except DatabaseUnavailableError as error:
        logger.exception("Database could not be prepared")
        QMessageBox.critical(
            None,
            config.app_name,
            f"Nie udało się przygotować bazy danych.\n\n{error}",
        )
        return 1

    window = MainWindow(config, create_session_factory(engine), theme)
    window.show()
    exit_code = app.exec()

    engine.dispose()
    logger.info("Shutting down with exit code %s", exit_code)
    return exit_code
