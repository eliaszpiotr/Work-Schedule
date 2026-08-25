from work_scheduler import __version__
from work_scheduler.config import AppConfig
from work_scheduler.ui.theme import DARK, LIGHT


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


def test_main_window_shows_the_database_location(application) -> None:
    _, window = application

    assert "Baza:" in window.database_summary()


def test_a_theme_change_reaches_the_employees_screen(application) -> None:
    _, window = application
    window._employees.apply_palette(DARK if window._theme.palette is LIGHT else LIGHT)

    window._refresh_icons()

    assert window._employees._palette is window._theme.palette


def test_every_sidebar_entry_has_a_page(application) -> None:
    """The two lists are matched by position, so one growing alone silently misroutes."""
    _, window = application

    assert window._navigation.count() == window._pages.count()


def test_the_sidebar_offers_only_screens_that_do_something(application) -> None:
    _, window = application
    names = [window._navigation.item(row).text() for row in range(window._navigation.count())]

    assert names == ["Grafiki", "Pracownicy", "Ustawienia"]


def test_the_last_entry_opens_the_settings_screen(application) -> None:
    _, window = application
    last = window._navigation.count() - 1
    window._navigation.setCurrentRow(last)

    assert window._pages.currentWidget() is window._settings
