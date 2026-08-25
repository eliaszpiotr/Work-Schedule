from PySide6.QtWidgets import QMessageBox

from work_scheduler.ui.components import destructive_question


class TestDestructiveQuestion:
    """Qt's standard buttons come out in English on macOS, with Cancel as the default,
    so a Polish question was answered with 'Cancel' and 'Yes'."""

    def test_the_buttons_speak_polish(self, application) -> None:
        box, confirm = destructive_question(None, "Usunąć?", "Zniknie.", "Usuń")

        assert confirm.text() == "Usuń"
        # Order is the platform's business; the wording is ours.
        assert {button.text() for button in box.buttons()} == {"Usuń", "Anuluj"}

    def test_cancelling_is_what_happens_by_default(self, application) -> None:
        box, confirm = destructive_question(None, "Usunąć?", "Zniknie.", "Usuń")

        assert box.defaultButton() is not confirm
        assert box.escapeButton() is not confirm

    def test_the_confirming_button_is_marked_destructive(self, application) -> None:
        box, confirm = destructive_question(None, "Usunąć?", "Zniknie.", "Usuń")

        assert box.buttonRole(confirm) is QMessageBox.ButtonRole.DestructiveRole
