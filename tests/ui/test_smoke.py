from PySide6.QtCore import Qt

from work_scheduler import __version__
from work_scheduler.config import AppConfig
from work_scheduler.ui.theme import DARK, LIGHT, METRICS, stylesheet


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

    assert window._pages.currentWidget() is window._settings_view


def test_the_database_path_is_not_exposed_in_the_main_interface(application) -> None:
    """An implementation detail must not appear as a tooltip over the whole sidebar."""
    _, window = application

    assert window.statusBar().currentMessage() == ""
    assert window._sidebar_frame.toolTip() == ""


def test_both_themes_build_a_stylesheet_with_every_new_token(application) -> None:
    for palette in (LIGHT, DARK):
        sheet = stylesheet(palette, "Inter")

        for colour in (palette.success_surface, palette.holiday_ink):
            assert colour in sheet


def test_every_screen_survives_a_theme_change(application) -> None:
    """The delegates paint from a palette they hold, so a flip has to reach them."""
    _, window = application
    before = window._theme.palette

    window._employees.apply_palette(DARK if before is LIGHT else LIGHT)
    window._schedules.apply_palette(DARK if before is LIGHT else LIGHT)
    window._settings_view.apply_palette(DARK if before is LIGHT else LIGHT)

    assert window._employees._delegate._palette is not before


class TestSidebar:
    def test_it_starts_open(self, application) -> None:
        _, window = application

        assert not window.collapsed

    def test_collapsing_narrows_it_to_the_icons(self, application) -> None:
        _, window = application
        window.set_sidebar_collapsed(True)

        assert window._sidebar_frame.width() == METRICS.sidebar_collapsed
        window.set_sidebar_collapsed(False)

    def test_the_words_go_away_with_it(self, application) -> None:
        _, window = application
        window.set_sidebar_collapsed(True)

        assert not window._brand_name.isVisible()
        assert window._navigation.item(0).text() == ""
        window.set_sidebar_collapsed(False)

    def test_a_collapsed_entry_keeps_an_accessible_name_without_a_tooltip(
        self, application
    ) -> None:
        _, window = application
        window.set_sidebar_collapsed(True)

        item = window._navigation.item(0)
        assert item.toolTip() == ""
        assert item.data(Qt.ItemDataRole.AccessibleTextRole) == "Grafiki"
        window.set_sidebar_collapsed(False)

    def test_the_chosen_screen_survives_the_toggle(self, application) -> None:
        _, window = application
        window._navigation.setCurrentRow(1)

        window.toggle_sidebar()
        window.toggle_sidebar()

        assert window._navigation.currentRow() == 1
        assert window._pages.currentWidget() is window._employees

    def test_toggling_twice_puts_it_back(self, application) -> None:
        _, window = application
        width = window._sidebar_frame.width()

        window.toggle_sidebar()
        window.toggle_sidebar()

        assert window._sidebar_frame.width() == width

    def test_the_collapsed_controls_share_one_axis(self, application) -> None:
        """Two spacers, both spelled out: addStretch() alone has a factor of zero."""
        app, window = application
        window.show()
        window.set_sidebar_collapsed(True)
        # The layout settles on the next turn of the loop, not on the call above.
        app.processEvents()

        button = window._collapse
        toggle = button.geometry().center().x() + button.parent().geometry().x()
        item = window._navigation.visualItemRect(window._navigation.item(0))
        icon = item.center().x() + window._navigation.geometry().x()

        assert abs(toggle - icon) <= 1
        window.set_sidebar_collapsed(False)
