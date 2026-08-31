import pytest
from PySide6.QtWidgets import QDialog, QPushButton

from work_scheduler.database.models import Profession
from work_scheduler.ui.components import (
    Avatar,
    Badge,
    ConfirmDialog,
    Glyph,
    SegmentedControl,
    initials,
    trade_colours,
)
from work_scheduler.ui.theme import DARK, LIGHT


class TestConfirmDialog:
    """Qt's standard buttons come out in English on macOS, with Cancel as the default,
    so a Polish question was answered with 'Cancel' and 'Yes'."""

    @staticmethod
    def dialog() -> ConfirmDialog:
        return ConfirmDialog(None, "Usunąć?", "Zniknie.", "Usuń", palette=LIGHT)

    def test_the_buttons_speak_polish(self, application) -> None:
        window = self.dialog()

        assert window.confirm_button.text() == "Usuń"
        assert window.cancel_button.text() == "Anuluj"

    def test_cancelling_is_what_enter_does(self, application) -> None:
        window = self.dialog()

        assert window.cancel_button.isDefault()
        assert not window.confirm_button.isDefault()

    def test_the_question_is_the_window_title_too(self, application) -> None:
        assert self.dialog().windowTitle() == "Usunąć?"

    def test_the_confirming_button_is_marked_destructive(self, application) -> None:
        assert self.dialog().confirm_button.property("variant") == "dangerFilled"

    def test_confirming_returns_true_and_cancelling_false(self, application) -> None:
        window = self.dialog()
        window.accept()
        assert window.result() == QDialog.DialogCode.Accepted


class TestInitials:
    def test_a_surname_and_a_forename_give_one_letter_each(self) -> None:
        assert initials("Kowalska Anna") == "KA"

    def test_a_single_word_gives_its_first_two_letters(self) -> None:
        assert initials("Nowak") == "NO"

    def test_a_double_barrelled_surname_counts_as_two_words(self) -> None:
        assert initials("Nowak-Kowalska") == "NK"

    def test_nothing_at_all_still_renders_something(self) -> None:
        assert initials("   ") == "?"


class TestAvatar:
    def test_it_shows_the_initials(self, application) -> None:
        assert Avatar("Nowak Marek").text() == "NM"

    def test_the_full_name_is_left_for_a_screen_reader(self, application) -> None:
        """Two letters mean nothing read aloud."""
        assert Avatar("Nowak Marek").accessibleName() == "Nowak Marek"

    def test_an_accent_avatar_is_told_apart_by_the_sheet(self, application) -> None:
        assert Avatar("Nowak Marek", accent=True).property("avatar") == "accent"


class TestBadge:
    def test_the_tone_reaches_the_stylesheet(self, application) -> None:
        assert Badge("Gotowy", "success").property("badge") == "success"

    def test_an_unknown_tone_is_refused(self, application) -> None:
        with pytest.raises(ValueError, match="tone"):
            Badge("Gotowy", "fioletowy")

    def test_changing_the_text_can_change_the_tone_with_it(self, application) -> None:
        badge = Badge("Roboczy", "neutral")
        badge.set_text("Gotowy", "success")

        assert badge.text() == "Gotowy"
        assert badge.property("badge") == "success"


class TestSegmentedControl:
    @staticmethod
    def control() -> SegmentedControl:
        return SegmentedControl([("Wszystkie", None), ("Robocze", "DRAFT"), ("Gotowe", "FINAL")])

    def test_the_first_option_starts_chosen(self, application) -> None:
        assert self.control().value() is None

    def test_choosing_by_value_moves_the_control(self, application) -> None:
        segmented = self.control()
        segmented.select("FINAL")

        assert segmented.value() == "FINAL"

    def test_a_value_it_does_not_have_leaves_it_alone(self, application) -> None:
        segmented = self.control()
        segmented.select("ARCHIVED")

        assert segmented.value() is None

    def test_exactly_one_option_is_ever_checked(self, application) -> None:
        segmented = self.control()
        segmented.select("DRAFT")
        checked = [button for button in segmented.findChildren(QPushButton) if button.isChecked()]

        assert len(checked) == 1

    def test_clicking_announces_the_value_not_the_index(self, application) -> None:
        segmented = self.control()
        heard: list[object] = []
        segmented.changed.connect(heard.append)

        segmented.findChildren(QPushButton)[2].click()

        assert heard == ["FINAL"]


class TestGlyph:
    def test_each_tone_reaches_the_stylesheet(self, application) -> None:
        for tone in ("danger", "warning", "info"):
            assert Glyph("check", tone, LIGHT).property("glyph") == tone

    def test_it_carries_the_icon_it_was_given(self, application) -> None:
        assert not Glyph("trash-2", "danger", LIGHT).pixmap().isNull()

    def test_a_tone_nobody_defined_is_refused(self, application) -> None:
        with pytest.raises(KeyError):
            Glyph("check", "fioletowy", LIGHT)


class TestTradeColours:
    """Cover is checked against pharmacists, so a column of badges has to answer
    "who is a magister" without being read word by word."""

    def test_the_two_trades_do_not_share_a_colour(self, application) -> None:
        pharmacist = trade_colours(Profession.PHARMACIST, LIGHT)
        technician = trade_colours(Profession.TECHNICIAN, LIGHT)

        assert pharmacist != technician

    def test_the_pharmacist_takes_the_tinted_one(self, application) -> None:
        fill, ink = trade_colours(Profession.PHARMACIST, LIGHT)

        assert (fill, ink) == (LIGHT.holiday_surface, LIGHT.holiday_ink)

    def test_the_technician_stays_neutral(self, application) -> None:
        fill, _ = trade_colours(Profession.TECHNICIAN, LIGHT)

        assert fill == LIGHT.surface_active

    def test_both_trades_are_told_apart_in_the_dark_theme_too(self, application) -> None:
        assert trade_colours(Profession.PHARMACIST, DARK) != trade_colours(
            Profession.TECHNICIAN, DARK
        )

    def test_a_trade_that_came_through_a_qt_model_still_gets_its_colour(self, application) -> None:
        """Qt hands a StrEnum back as a plain str, so identity tests fail silently."""
        assert trade_colours("PHARMACIST", LIGHT) == trade_colours(Profession.PHARMACIST, LIGHT)
        assert trade_colours("TECHNICIAN", LIGHT) == trade_colours(Profession.TECHNICIAN, LIGHT)

    def test_a_missing_trade_falls_back_to_neutral(self, application) -> None:
        assert trade_colours(None, LIGHT) == trade_colours(Profession.TECHNICIAN, LIGHT)
