def word(count: int, one: str, few: str, many: str) -> str:
    """The form a Polish word takes for a count, without the number itself.

    Verbs need this as much as nouns: "wypada 1 święto" but "wypadają 2 święta".
    The "few" form covers counts ending in 2-4, except the teens, which take "many".
    """
    if count == 1:
        return one

    last, last_two = count % 10, count % 100
    if 2 <= last <= 4 and not 12 <= last_two <= 14:
        return few
    return many


def plural(count: int, one: str, few: str, many: str) -> str:
    """The count with its word: 1 osoba, 2 osoby, 5 osób."""
    return f"{count} {word(count, one, few, many)}"


def days(count: int) -> str:
    return plural(count, "dzień", "dni", "dni")


def people(count: int) -> str:
    return plural(count, "osoba", "osoby", "osób")
