import pytest
from PySide6.QtGui import QImage

from work_scheduler.ui.icons import IconNotFoundError, available_icons, load_icon
from work_scheduler.ui.resources import APP_ICON
from work_scheduler.ui.theme import DARK, LIGHT, METRICS, ThemeManager, stylesheet


class TestTokens:
    def test_both_palettes_define_every_colour(self) -> None:
        assert LIGHT.__slots__ == DARK.__slots__
        assert all(getattr(LIGHT, name).startswith("#") for name in LIGHT.__slots__)
        assert all(getattr(DARK, name).startswith("#") for name in DARK.__slots__)

    def test_spacing_follows_the_scale(self) -> None:
        spacing = [METRICS.space_1, METRICS.space_2, METRICS.space_3, METRICS.space_4]
        assert all(value % 4 == 0 for value in spacing)

    @pytest.mark.parametrize("palette", [LIGHT, DARK], ids=["light", "dark"])
    def test_stylesheet_uses_the_palette(self, palette) -> None:
        sheet = stylesheet(palette, "Inter")

        assert palette.background in sheet
        assert palette.accent in sheet
        assert "{" in sheet


class TestIcons:
    def test_icons_are_bundled(self) -> None:
        assert "users" in available_icons()

    def test_renders_in_the_requested_colour(self, application) -> None:
        icon = load_icon("users", LIGHT.text_secondary)

        assert not icon.isNull()

    def test_unknown_icon_is_reported(self, application) -> None:
        with pytest.raises(IconNotFoundError):
            load_icon("nie-ma-takiej", LIGHT.text_primary)


def test_theme_manager_picks_a_palette(application) -> None:
    app, _ = application
    theme = ThemeManager()
    theme.apply(app)

    assert theme.palette in (LIGHT, DARK)
    assert app.styleSheet()


class TestApplicationIcon:
    def test_every_format_is_present(self) -> None:
        for path in (APP_ICON, APP_ICON.with_suffix(".ico"), APP_ICON.with_suffix(".icns")):
            assert path.is_file(), f"brakuje {path.name}"

    def test_icon_loads_with_transparency(self, application) -> None:
        image = QImage(str(APP_ICON))

        assert not image.isNull()
        assert image.hasAlphaChannel(), "bez alfy tło byłoby białym prostokątem w doku"
        assert image.width() == image.height() == 1024

    def test_the_window_uses_it(self, application) -> None:
        app, _ = application

        assert not app.windowIcon().isNull()
