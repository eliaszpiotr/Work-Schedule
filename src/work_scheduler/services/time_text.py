import re
from datetime import time

# Anything a person might put between two hours: hyphen, both dashes, or the word "do".
RANGE = re.compile(
    r"^(?:od\s+)?(\d{1,2})(?:[:.](\d{2}))?\s*(?:-|–|—|do)\s*(\d{1,2})(?:[:.](\d{2}))?$",
    re.IGNORECASE,
)


def _time_or_none(hour: str, minute: str | None) -> time | None:
    hours, minutes = int(hour), int(minute or 0)
    if hours > 23 or minutes > 59:
        return None
    return time(hours, minutes)


def parse_range(text: str) -> tuple[time, time] | None:
    """Read what the user typed into a cell. None means it could not be understood."""
    match = RANGE.match(text.strip())
    if match is None:
        return None

    start = _time_or_none(match[1], match[2])
    end = _time_or_none(match[3], match[4])
    if start is None or end is None:
        return None

    # A shift cannot cross midnight, so the end has to come later the same day.
    if end <= start:
        return None
    return start, end


def format_range(start: time, end: time) -> str:
    return f"{start:%H:%M}–{end:%H:%M}"


def format_short(value: time) -> str:
    """Drops the ":00" from a whole hour and the leading zero, where width is tight."""
    return f"{value.hour}:{value.minute:02d}" if value.minute else str(value.hour)


def format_range_short(start: time, end: time) -> str:
    return f"{format_short(start)}–{format_short(end)}"


def minutes_between(start: time, end: time) -> int:
    return (end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)


def format_hours(minutes: int) -> str:
    """Totals read as hours; zero is a dash so an empty column does not shout '0 h'."""
    if minutes == 0:
        return "—"

    hours = minutes / 60
    if minutes % 60 == 0:
        return f"{minutes // 60} h"
    return f"{hours:.1f}".replace(".", ",") + " h"
