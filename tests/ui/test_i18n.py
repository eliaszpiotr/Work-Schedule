import ast
import pathlib

import pytest
from PySide6.QtCore import QSettings

from work_scheduler.i18n import (
    DEFAULT_LANGUAGE,
    Language,
    current_language,
    en,
    pl,
    set_language,
    t,
    translate,
    weekday_name,
)
from work_scheduler.settings import PrintLanguage, Settings, ThemeMode
from work_scheduler.ui.theme import DARK, LIGHT, ThemeManager

SOURCE = pathlib.Path(__file__).resolve().parents[2] / "src" / "work_scheduler"


@pytest.fixture(autouse=True)
def _restore_language():
    """Every test here moves the global language, and none may leak into the next."""
    before = current_language()
    yield
    set_language(before)


class TestCatalogues:
    """The two errors that actually happen with 200-odd strings, made impossible."""

    def test_both_languages_carry_exactly_the_same_keys(self) -> None:
        assert set(pl.TEXT) == set(en.TEXT)

    def test_no_entry_is_left_empty(self) -> None:
        for catalogue in (pl.TEXT, en.TEXT):
            for key, entry in catalogue.items():
                values = entry.values() if isinstance(entry, dict) else [entry]
                assert all(str(v).strip() for v in values), key

    def test_counted_entries_have_all_three_forms_in_both_languages(self) -> None:
        counted = {key for key, entry in pl.TEXT.items() if isinstance(entry, dict)}
        assert counted
        for key in counted:
            for catalogue in (pl.TEXT, en.TEXT):
                assert set(catalogue[key]) == {"one", "few", "many"}, key

    def test_every_key_the_code_asks_for_exists(self) -> None:
        """A key typed into a call and never added to the catalogue would only show up
        as a dotted word on a screen nobody opened during testing."""
        missing = sorted(key for key in _keys_used_in_source() if key not in pl.TEXT)
        assert missing == []


def _keys_used_in_source() -> set[str]:
    """Literal first arguments of t() and translate() across the package."""
    keys: set[str] = set()
    for path in SOURCE.rglob("*.py"):
        if "i18n" in path.parts or "migrations" in path.parts:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            name = node.func.id if isinstance(node.func, ast.Name) else None
            if name in ("t", "translate") and isinstance(node.args[0], ast.Constant):
                value = node.args[0].value
                if isinstance(value, str):
                    keys.add(value)
    return keys


class TestTranslate:
    def test_the_current_language_is_polish_until_told_otherwise(self) -> None:
        assert DEFAULT_LANGUAGE is Language.PL

    def test_a_language_can_be_asked_for_without_changing_the_current_one(self) -> None:
        set_language(Language.PL)

        assert translate("nav.settings", Language.EN) == "Settings"
        assert current_language() is Language.PL

    def test_switching_changes_what_t_returns(self) -> None:
        set_language(Language.EN)
        assert t("nav.schedules") == "Schedules"
        set_language(Language.PL)
        assert t("nav.schedules") == "Grafiki"

    def test_a_missing_key_comes_back_as_itself(self) -> None:
        """A stray dotted word on screen is a bug worth seeing; a screen that will not
        open because one string is absent is worse."""
        assert t("nie.ma.takiego.klucza") == "nie.ma.takiego.klucza"

    def test_parameters_are_filled_in(self) -> None:
        assert "Kowalski" in translate("employees.delete.body", Language.PL, name="Kowalski")

    def test_weekdays_number_from_monday(self) -> None:
        assert weekday_name(0, Language.EN) == "Monday"
        assert weekday_name(6, Language.PL) == "niedziela"


class TestSettings:
    @pytest.fixture
    def settings(self, tmp_path) -> Settings:
        store = QSettings(str(tmp_path / "test.ini"), QSettings.Format.IniFormat)
        return Settings(store)

    def test_it_starts_in_polish_following_the_system_theme(self, settings: Settings) -> None:
        assert settings.language is Language.PL
        assert settings.theme is ThemeMode.SYSTEM
        assert settings.print_language is PrintLanguage.UI

    def test_a_choice_survives_being_read_back(self, settings: Settings) -> None:
        settings.language = Language.EN
        settings.theme = ThemeMode.DARK
        settings.print_language = PrintLanguage.PL

        assert settings.language is Language.EN
        assert settings.theme is ThemeMode.DARK
        assert settings.print_language is PrintLanguage.PL

    def test_an_unusable_stored_value_falls_back_to_the_default(self, settings: Settings) -> None:
        """Hand-edited, or written by a version that knew a value this one does not."""
        settings._settings.setValue("interface/language", "KLINGON")

        assert settings.language is Language.PL

    def test_the_printout_follows_the_interface_by_default(self, settings: Settings) -> None:
        settings.language = Language.EN

        assert settings.language_for_print() is Language.EN

    def test_the_printout_can_stay_polish_while_the_interface_is_english(
        self, settings: Settings
    ) -> None:
        settings.language = Language.EN
        settings.print_language = PrintLanguage.PL

        assert settings.language_for_print() is Language.PL


class TestThemeModes:
    def test_an_explicit_choice_wins(self, application) -> None:  # noqa: ANN001
        assert ThemeManager(ThemeMode.LIGHT)._palette_for_mode() is LIGHT
        assert ThemeManager(ThemeMode.DARK)._palette_for_mode() is DARK

    def test_system_mode_takes_whatever_the_system_says(self, application) -> None:  # noqa: ANN001
        assert ThemeManager(ThemeMode.SYSTEM)._palette_for_mode() in (LIGHT, DARK)

    def test_a_chosen_palette_ignores_the_system_flipping(self, application) -> None:  # noqa: ANN001
        """The whole point of picking Light is that dusk does not undo it."""
        app, _ = application
        manager = ThemeManager(ThemeMode.LIGHT)
        manager.apply(app)

        manager._system_changed(app)

        assert manager.palette is LIGHT


class TestLiveLanguageSwitch:
    """Switching rebuilds the screens, the way a theme change repaints them."""

    def test_the_navigation_and_the_screens_change_language_together(self, application) -> None:  # noqa: ANN001 - the shared QApplication
        _, window = application
        try:
            window.set_language(Language.EN)

            assert window._navigation.item(0).text() == "Schedules"
            assert window._employees._add.text() == "Add an employee"
        finally:
            window.set_language(Language.PL)

        assert window._navigation.item(0).text() == "Grafiki"
        assert window._employees._add.text() == "Dodaj pracownika"

    def test_the_screen_you_were_on_is_the_screen_you_come_back_to(self, application) -> None:  # noqa: ANN001
        _, window = application
        window._navigation.setCurrentRow(1)
        try:
            window.set_language(Language.EN)

            assert window._navigation.currentRow() == 1
            assert window._pages.currentWidget() is window._employees
        finally:
            window.set_language(Language.PL)
            window._navigation.setCurrentRow(0)

    def test_the_choice_is_remembered(self, application, tmp_path) -> None:  # noqa: ANN001
        _, window = application
        store = QSettings(str(tmp_path / "remember.ini"), QSettings.Format.IniFormat)
        window._settings = Settings(store)
        try:
            window.set_language(Language.EN)

            assert Settings(store).language is Language.EN
        finally:
            window.set_language(Language.PL)
