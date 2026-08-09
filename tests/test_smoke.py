from work_scheduler import __version__
from work_scheduler.config import AppConfig


def test_default_configuration() -> None:
    config = AppConfig()

    assert config.app_name == "Work Scheduler"
    assert config.version == __version__


def test_application_is_configured(application) -> None:
    app, _ = application

    assert app.applicationName() == "Work Scheduler"
    assert app.applicationVersion() == __version__


def test_main_window_opens(application) -> None:
    _, window = application
    window.show()

    assert window.isVisible()
    assert window.windowTitle() == "Work Scheduler"
    assert window.centralWidget() is not None
