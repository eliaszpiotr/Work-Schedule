"""Short, printable labels for days when an employee is not working."""

from work_scheduler.i18n import Language, current_language

ABSENCE_LABELS = {
    "ZCh": "zwolnienie lekarskie",
    "U": "urlop",
    "WN": "wolne za nadgodziny",
    "OD": "opieka nad dzieckiem",
}

ENGLISH_CODES = {"ZCh": "SL", "U": "V", "WN": "TO", "OD": "CC"}


def display_absence(code: str, language: Language | None = None) -> str:
    """Keep stored codes stable while showing the code used in the chosen language."""
    language = Language(language) if language is not None else current_language()
    return ENGLISH_CODES[code] if language is Language.EN else code


def parse_absence(value: str) -> str | None:
    """Accept either language's code or description, ignoring case and spaces."""
    normalized = " ".join(value.casefold().split())
    aliases = {
        "zch": "ZCh",
        "zwolnienie lekarskie": "ZCh",
        "zwolnie lekarskie": "ZCh",
        "chorobowe": "ZCh",
        "u": "U",
        "urlop": "U",
        "wn": "WN",
        "wolne za nadgodziny": "WN",
        "od": "OD",
        "opieka nad dzieckiem": "OD",
        "sick leave": "ZCh",
        "vacation": "U",
        "overtime time off": "WN",
        "time off for overtime": "WN",
        "child care leave": "OD",
        "sl": "ZCh",
        "v": "U",
        "toil": "WN",
        "to": "WN",
        "time off in lieu": "WN",
        "ccl": "OD",
        "cc": "OD",
    }
    return aliases.get(normalized)
