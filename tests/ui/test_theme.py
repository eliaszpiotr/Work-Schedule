import sys

import pytest
from PySide6.QtGui import QImage

from work_scheduler.services.absence import ABSENCE_LABELS
from work_scheduler.ui.icons import IconNotFoundError, available_icons, load_icon
from work_scheduler.ui.resources import APP_ICON
from work_scheduler.ui.theme import (
    DARK,
    LIGHT,
    METRICS,
    ThemeManager,
    pill_colours,
    stylesheet,
    ui_font_family,
)


def _luminance(colour: str) -> float:
    channels = [int(colour[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(a: str, b: str) -> float:
    high, low = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


class TestTokens:
    def test_both_palettes_define_every_colour(self) -> None:
        assert LIGHT.__slots__ == DARK.__slots__
        for palette in (LIGHT, DARK):
            assert all(
                getattr(palette, name).startswith(("#", "rgba(")) for name in palette.__slots__
            )

    def test_spacing_follows_the_scale(self) -> None:
        spacing = [METRICS.space_1, METRICS.space_2, METRICS.space_3, METRICS.space_4]
        assert all(value % 4 == 0 for value in spacing)

    @pytest.mark.parametrize("palette", [LIGHT, DARK], ids=["light", "dark"])
    def test_stylesheet_uses_the_palette(self, palette) -> None:
        sheet = stylesheet(palette, "Inter")

        assert palette.background in sheet
        assert palette.accent in sheet
        assert "{" in sheet


@pytest.mark.parametrize("palette", [LIGHT, DARK], ids=["light", "dark"])
@pytest.mark.parametrize("kind", ["work", "U", "ZCh", "WN", "OD"])
def test_every_pill_reads_at_aa(palette, kind) -> None:
    fill, ink = pill_colours(kind, palette)

    assert contrast(fill, ink) >= 4.5


def test_every_absence_code_has_a_pill() -> None:
    for code in ["work", *ABSENCE_LABELS]:
        assert pill_colours(code, LIGHT) is not None
        assert pill_colours(code, DARK) is not None


def test_cards_answer_the_pointer_but_selection_wins() -> None:
    sheet = stylesheet(LIGHT, "x")
    hover = sheet.split("QFrame#card:hover {")[1].split("}")[0]
    assert LIGHT.border_strong in hover
    assert sheet.index("QFrame#card:hover") < sheet.index('QFrame#card[selected="true"]')


def test_the_grid_editor_is_rounded_like_the_cursor_ring() -> None:
    sheet = stylesheet(LIGHT, "x")
    block = sheet.split('QTableView[role="grid"] QLineEdit {')[1].split("}")[0]
    assert f"border-radius: {METRICS.pill_radius + 2}px" in block


def test_the_grid_date_column_and_corner_are_card_white() -> None:
    sheet = stylesheet(LIGHT, "x")
    for selector in (
        'QTableView[role="grid"] QHeaderView::section {',
        'QTableView[role="grid"] QTableCornerButton::section {',
    ):
        block = sheet.split(selector)[1].split("}")[0]
        assert f"background: {LIGHT.elevated}" in block


def test_no_kind_means_no_pill() -> None:
    assert pill_colours(None, LIGHT) is None


def test_the_accent_is_system_blue() -> None:
    assert (LIGHT.accent, DARK.accent) == ("#007AFF", "#0A84FF")
    assert LIGHT.on_accent == DARK.on_accent == "#FFFFFF"


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


def test_the_interface_font_is_never_blank(application, monkeypatch) -> None:
    assert ui_font_family().strip()

    monkeypatch.setattr(sys, "platform", "win32")

    assert ui_font_family() != ".AppleSystemUIFont"


@pytest.mark.parametrize("palette", [LIGHT, DARK], ids=["light", "dark"])
def test_the_round_button_keeps_its_blue_when_hovered_or_pressed(palette) -> None:
    sheet = stylesheet(palette, "Inter")

    for state in ("hover", "pressed"):
        selector = f'QToolButton[variant="roundPrimary"]:{state}'
        rule = f"{selector} {{ background: {palette.accent_hover}; }}"
        assert rule in sheet
