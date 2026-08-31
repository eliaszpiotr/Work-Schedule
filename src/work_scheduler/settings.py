import logging
from enum import StrEnum

from PySide6.QtCore import QSettings

from work_scheduler.i18n import Language

logger = logging.getLogger(__name__)

LANGUAGE_KEY = "interface/language"
THEME_KEY = "interface/theme"
PRINT_LANGUAGE_KEY = "interface/print_language"


class ThemeMode(StrEnum):
    SYSTEM = "SYSTEM"
    LIGHT = "LIGHT"
    DARK = "DARK"


class PrintLanguage(StrEnum):
    """``UI`` means whatever the interface is set to when the sheet is printed."""

    UI = "UI"
    PL = "PL"
    EN = "EN"


def _read(settings: QSettings, key: str, enum: type[StrEnum], fallback: StrEnum) -> StrEnum:
    """A value written by a newer version, or edited by hand, must not stop the app."""
    stored = settings.value(key)
    try:
        return enum(str(stored))
    except ValueError:
        if stored is not None:
            logger.warning("Ignoring unusable %s setting %r", key, stored)
        return fallback


class Settings:
    """Language and theme, kept where the operating system keeps such things.

    Opening hours live in the database because they belong to the pharmacy and travel
    with it. These belong to whoever is sitting at this machine, so they stay here.
    """

    def __init__(self, settings: QSettings | None = None) -> None:
        self._settings = settings if settings is not None else QSettings()

    @property
    def language(self) -> Language:
        return _read(self._settings, LANGUAGE_KEY, Language, Language.PL)

    @language.setter
    def language(self, value: Language) -> None:
        self._settings.setValue(LANGUAGE_KEY, str(Language(value)))

    @property
    def theme(self) -> ThemeMode:
        return _read(self._settings, THEME_KEY, ThemeMode, ThemeMode.SYSTEM)

    @theme.setter
    def theme(self, value: ThemeMode) -> None:
        self._settings.setValue(THEME_KEY, str(ThemeMode(value)))

    @property
    def print_language(self) -> PrintLanguage:
        return _read(self._settings, PRINT_LANGUAGE_KEY, PrintLanguage, PrintLanguage.UI)

    @print_language.setter
    def print_language(self, value: PrintLanguage) -> None:
        self._settings.setValue(PRINT_LANGUAGE_KEY, str(PrintLanguage(value)))

    def language_for_print(self) -> Language:
        """What the printed sheet is written in, once "same as interface" is resolved."""
        chosen = self.print_language
        return self.language if chosen is PrintLanguage.UI else Language(str(chosen))
