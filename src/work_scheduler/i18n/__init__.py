import logging
from enum import StrEnum

logger = logging.getLogger(__name__)


class Language(StrEnum):
    PL = "PL"
    EN = "EN"


DEFAULT_LANGUAGE = Language.PL

# The form a counted word takes. English uses two of them, Polish three, so the catalogue
# stores every counted entry under all three keys and each language picks.
ONE, FEW, MANY = "one", "few", "many"


def _polish_form(count: int) -> str:
    """1 osoba, 2 osoby, 5 osób. The teens take the "many" form despite ending in 2-4."""
    if count == 1:
        return ONE
    last, last_two = count % 10, count % 100
    return FEW if 2 <= last <= 4 and not 12 <= last_two <= 14 else MANY


def _english_form(count: int) -> str:
    return ONE if count == 1 else MANY


_FORMS = {Language.PL: _polish_form, Language.EN: _english_form}

_current = DEFAULT_LANGUAGE


def current_language() -> Language:
    return _current


def set_language(language: Language) -> None:
    global _current
    _current = Language(language)


def _catalogue(language: Language) -> dict[str, object]:
    # Imported here rather than at module level: the catalogues import nothing from this
    # module, and this keeps the import graph a straight line.
    from work_scheduler.i18n import en, pl

    return pl.TEXT if language is Language.PL else en.TEXT


def translate(key: str, language: Language | None = None, **params: object) -> str:
    """One piece of user-facing text, in the language asked for or the current one.

    A missing key returns the key itself. A screen with a stray dotted word on it is a
    bug worth seeing; a screen that will not open because of one absent string is worse.
    The catalogue tests are what actually keep keys from going missing.
    """
    language = Language(language) if language is not None else _current
    entry = _catalogue(language).get(key)

    if entry is None:
        logger.warning("Missing %s translation for %r", language, key)
        return key

    if isinstance(entry, dict):
        count = params.get("count")
        if not isinstance(count, int):
            logger.warning("Counted entry %r used without a count", key)
            return key
        entry = entry[_FORMS[language](count)]

    text = str(entry)
    return text.format(**params) if params else text


def t(key: str, **params: object) -> str:
    """Shorthand for the current language, which is what nearly every caller wants."""
    return translate(key, None, **params)


def weekday_name(weekday: int, language: Language | None = None) -> str:
    """Monday is 0, the same numbering date.weekday() uses."""
    return translate(f"weekday.{weekday}", language)


def weekday_short(weekday: int, language: Language | None = None) -> str:
    return translate(f"weekday.short.{weekday}", language)


def month_name(month: int, language: Language | None = None) -> str:
    """The form a date is read in: "25 sierpnia 2026", "25 August 2026"."""
    return translate(f"month.in.{month}", language)


def month_short(month: int, language: Language | None = None) -> str:
    return translate(f"month.short.{month}", language)


def profession_name(profession: object, language: Language | None = None) -> str:
    """Lower case, for running text and for the printed sheet."""
    return translate(f"profession.{str(profession).split('.')[-1].lower()}", language)


def profession_label(profession: object, language: Language | None = None) -> str:
    """Capitalised, for a column, a badge or a radio button."""
    return translate(f"profession.{str(profession).split('.')[-1].lower()}.label", language)
