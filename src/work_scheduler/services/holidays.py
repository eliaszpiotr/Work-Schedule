from datetime import date, timedelta

from work_scheduler.i18n import Language, translate

# Christmas Eve became a public holiday in Poland only from 2025 onwards.
CHRISTMAS_EVE_FROM = 2025

# Catalogue keys rather than words: the printed sheet may be in a different language
# than the interface that produced it.
FIXED = {
    (1, 1): "holiday.new_year",
    (1, 6): "holiday.epiphany",
    (5, 1): "holiday.labour_day",
    (5, 3): "holiday.constitution_day",
    (8, 15): "holiday.assumption",
    (11, 1): "holiday.all_saints",
    (11, 11): "holiday.independence",
    (12, 25): "holiday.christmas",
    (12, 26): "holiday.christmas_second",
}

# Days after Easter Sunday.
MOVABLE = {
    0: "holiday.easter",
    1: "holiday.easter_monday",
    49: "holiday.pentecost",
    60: "holiday.corpus_christi",
}


def easter(year: int) -> date:
    """Easter Sunday in the Gregorian calendar, by the anonymous Meeus algorithm.

    Worth computing rather than storing: it needs no data file and no updates, and the
    application has to work without a network.
    """
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    lunar = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * lunar) // 451
    month, day = divmod(h + lunar - 7 * m + 114, 31)
    return date(year, month, day + 1)


def holiday_keys_in(year: int) -> dict[date, str]:
    """Every Polish public holiday of one year, by date, as catalogue keys."""
    days = {date(year, month, day): key for (month, day), key in FIXED.items()}
    if year >= CHRISTMAS_EVE_FROM:
        days[date(year, 12, 24)] = "holiday.christmas_eve"

    sunday = easter(year)
    for offset, key in MOVABLE.items():
        days[sunday + timedelta(days=offset)] = key
    return days


def holidays_in(year: int, language: Language | None = None) -> dict[date, str]:
    """The same, named."""
    return {day: translate(key, language) for day, key in holiday_keys_in(year).items()}


def holiday_name(day: date, language: Language | None = None) -> str | None:
    key = holiday_keys_in(day.year).get(day)
    return None if key is None else translate(key, language)


def holidays_within(start: date, end: date, language: Language | None = None) -> dict[date, str]:
    """A period can span a new year, so both years have to be looked at."""
    days: dict[date, str] = {}
    for year in range(start.year, end.year + 1):
        days.update(
            {day: name for day, name in holidays_in(year, language).items() if start <= day <= end}
        )
    return days
