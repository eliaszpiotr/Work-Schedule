from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon

from work_scheduler import __version__
from work_scheduler.config import AppConfig
from work_scheduler.ui.theme import DARK, LIGHT, METRICS, ThemeMode, stylesheet


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


def test_no_focus_ring_on_open(application) -> None:
    app, window = application
    window.show()
    app.processEvents()

    assert window.focusWidget() is not window._collapse
    assert window._collapse.focusPolicy() == Qt.FocusPolicy.TabFocus


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


def _bounds(image, colour: str, inside=None) -> tuple[int, int, int, int] | None:
    """Box around every pixel within 8 of a colour, optionally inside another box."""
    target = QColor(colour)
    left, top, right, bottom = inside or (0, 0, image.width() - 1, image.height() - 1)
    hits = [
        (x, y)
        for y in range(top, bottom + 1)
        for x in range(left, right + 1)
        if all(
            abs(a - b) <= 8
            for a, b in zip(
                image.pixelColor(x, y).getRgb()[:3], target.getRgb()[:3], strict=True
            )
        )
    ]
    if not hits:
        return None
    xs, ys = [x for x, _ in hits], [y for _, y in hits]
    return min(xs), min(ys), max(xs), max(ys)


def test_the_collapsed_highlight_is_a_centred_square(application) -> None:
    app, window = application
    window.show()
    window.set_sidebar_collapsed(True)
    window._navigation.setCurrentRow(2)
    app.processEvents()
    try:
        navigation = window._navigation
        image = navigation.viewport().grab().toImage()
        scale = image.devicePixelRatio()
        palette = window._theme.palette
        rect = navigation.visualItemRect(navigation.item(2))
        edges = (0, rect.top(), image.width() / scale - 1, rect.bottom())
        row = tuple(round(v * scale) for v in edges)

        square = _bounds(image, palette.accent, row)
        assert square is not None
        left, top, right, bottom = square
        centre = image.width() / 2
        assert abs((left + right + 1) / 2 - centre) <= scale
        assert abs((right - left) - (bottom - top)) <= scale

        glyph = _bounds(image, palette.on_accent, square)
        assert glyph is not None
        assert abs((glyph[0] + glyph[2] + 1) / 2 - centre) <= scale
    finally:
        window._navigation.setCurrentRow(0)
        window.set_sidebar_collapsed(False)


def test_the_sidebar_floats(application) -> None:
    _, window = application
    inset = METRICS.window_inset
    margins = window.centralWidget().layout().contentsMargins()

    assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (inset,) * 4
    block = stylesheet(LIGHT, "x").split("QFrame#sidebar {")[1].split("}")[0]
    assert "border-radius: 16px" in block
    assert "border-right" not in block


def test_nav_icons_follow_the_theme(application) -> None:
    app, window = application
    original = window._theme.mode
    window._theme.set_mode(ThemeMode.DARK, app)
    try:
        image = window._navigation.item(0).icon().pixmap(18, mode=QIcon.Mode.Normal).toImage()
    finally:
        window._theme.set_mode(original, app)
    ratio = image.devicePixelRatio()
    # The stroke has holes, so look for the accent anywhere rather than at one pixel.
    seen = [
        image.pixelColor(x, y)
        for x in range(image.width())
        for y in range(image.height())
        if image.pixelColor(x, y).alpha() > 240
    ]
    target = DARK.accent.lstrip("#")
    want = tuple(int(target[i : i + 2], 16) for i in (0, 2, 4))
    assert ratio >= 1
    assert any(
        all(abs(c - w) <= 8 for c, w in zip((q.red(), q.green(), q.blue()), want, strict=True))
        for q in seen
    )


def test_expanded_nav_labels_sit_beside_their_icons(application) -> None:
    _, window = application
    window.set_sidebar_collapsed(False)
    assert window._navigation.item(0).textAlignment() & Qt.AlignmentFlag.AlignLeft

    window.set_sidebar_collapsed(True)
    try:
        assert window._navigation.item(0).textAlignment() & Qt.AlignmentFlag.AlignHCenter
    finally:
        window.set_sidebar_collapsed(False)
