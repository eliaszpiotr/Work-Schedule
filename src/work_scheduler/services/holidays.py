from datetime import date, timedelta

# Christmas Eve became a public holiday in Poland only from 2025 onwards.
CHRISTMAS_EVE_FROM = 2025

FIXED = {
    (1, 1): "Nowy Rok",
    (1, 6): "Trzech Króli",
    (5, 1): "Święto Pracy",
    (5, 3): "Święto Konstytucji 3 Maja",
    (8, 15): "Wniebowzięcie NMP",
    (11, 1): "Wszystkich Świętych",
    (11, 11): "Święto Niepodległości",
    (12, 25): "Boże Narodzenie",
    (12, 26): "drugi dzień Bożego Narodzenia",
}

# Days after Easter Sunday.
MOVABLE = {
    0: "Wielkanoc",
    1: "Poniedziałek Wielkanocny",
    49: "Zielone Świątki",
    60: "Boże Ciało",
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


def holidays_in(year: int) -> dict[date, str]:
    """Every Polish public holiday of one year, by date."""
    days = {date(year, month, day): name for (month, day), name in FIXED.items()}
    if year >= CHRISTMAS_EVE_FROM:
        days[date(year, 12, 24)] = "Wigilia"

    sunday = easter(year)
    for offset, name in MOVABLE.items():
        days[sunday + timedelta(days=offset)] = name
    return days


def holiday_name(day: date) -> str | None:
    return holidays_in(day.year).get(day)


def holidays_within(start: date, end: date) -> dict[date, str]:
    """A period can span a new year, so both years have to be looked at."""
    days: dict[date, str] = {}
    for year in range(start.year, end.year + 1):
        days.update({day: name for day, name in holidays_in(year).items() if start <= day <= end})
    return days
