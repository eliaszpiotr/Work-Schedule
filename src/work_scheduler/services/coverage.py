from dataclasses import dataclass
from datetime import date, time
from typing import TYPE_CHECKING

from work_scheduler.database.models import Profession
from work_scheduler.services.time_text import format_range, format_range_short

if TYPE_CHECKING:
    from work_scheduler.services.schedule_service import ScheduleData

Interval = tuple[time, time]


def _minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def _time(minutes: int) -> time:
    return time(minutes // 60, minutes % 60)


def gaps(opens: time, closes: time, shifts: list[Interval]) -> list[Interval]:
    """Stretches of the opening hours nobody in ``shifts`` is there for.

    Shifts may overlap, touch, run past the opening hours or arrive out of order.
    """
    start, end = _minutes(opens), _minutes(closes)
    covered = sorted(
        (max(start, _minutes(a)), min(end, _minutes(b)))
        for a, b in shifts
        if _minutes(a) < end and _minutes(b) > start
    )

    uncovered: list[Interval] = []
    edge = start
    for begins, finishes in covered:
        if begins > edge:
            uncovered.append((_time(edge), _time(begins)))
        edge = max(edge, finishes)

    if edge < end:
        uncovered.append((_time(edge), _time(end)))
    return uncovered


@dataclass(frozen=True, slots=True)
class Uncovered:
    """A day on which the pharmacy is open with no pharmacist present for part of it."""

    day: date
    intervals: list[Interval]
    whole_day: bool

    @property
    def hours(self) -> str:
        """The missing stretches, short enough to sit next to the date in a row header."""
        if self.whole_day:
            return "cały dzień"
        return ", ".join(format_range_short(a, b) for a, b in self.intervals)

    @property
    def full_hours(self) -> str:
        """The same, spelled out, for a tooltip that has room."""
        if self.whole_day:
            return "cały dzień"
        return ", ".join(format_range(a, b) for a, b in self.intervals)

    def describe(self) -> str:
        return f"{self.day:%d.%m} {self.hours}"


def uncovered_days(
    schedule: "ScheduleData", cells: dict[tuple[int, date], Interval]
) -> dict[date, Uncovered]:
    """Days on which the pharmacy is open without a pharmacist for part of the time.

    Two kinds of day are passed over. Closed ones — weekends, holidays, days shut by
    hand — carry no requirement. Days nobody has been put on yet are not a mistake
    either, only unfinished; without that, a schedule being filled in would be red from
    end to end before the first entry.
    """
    pharmacists = {lane.id for lane in schedule.lanes if lane.profession is Profession.PHARMACIST}

    problems: dict[date, Uncovered] = {}
    for info in schedule.timeline():
        if info.closed:
            continue

        on_duty = [(lane, hours) for (lane, day), hours in cells.items() if day == info.day]
        if not on_duty:
            continue

        missing = gaps(
            info.opens, info.closes, [hours for lane, hours in on_duty if lane in pharmacists]
        )
        if missing:
            problems[info.day] = Uncovered(
                day=info.day,
                intervals=missing,
                whole_day=missing == [(info.opens, info.closes)],
            )
    return problems
