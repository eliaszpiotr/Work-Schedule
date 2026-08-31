from dataclasses import dataclass
from datetime import date, time
from enum import StrEnum

from work_scheduler.i18n import t
from work_scheduler.services.coverage import uncovered_days
from work_scheduler.services.schedule_service import ScheduleData
from work_scheduler.services.time_text import format_range

Cell = tuple[int, date]
Hours = tuple[time, time]


class Kind(StrEnum):
    """What was found. Only one kind stands in the way of closing a schedule."""

    EMPTY_DAY = "EMPTY_DAY"
    NO_PHARMACIST = "NO_PHARMACIST"
    OUTSIDE_HOURS = "OUTSIDE_HOURS"
    IDLE_PERSON = "IDLE_PERSON"


# An open day with nobody on it almost always means the schedule is simply unfinished,
# so it is the one thing worth stopping for. The rest are judgement calls the pharmacy
# makes on purpose often enough that blocking them would train people to click through.
BLOCKING = frozenset({Kind.EMPTY_DAY})


@dataclass(frozen=True, slots=True)
class Finding:
    kind: Kind
    text: str

    @property
    def blocking(self) -> bool:
        return self.kind in BLOCKING


@dataclass(frozen=True, slots=True)
class Audit:
    findings: list[Finding]

    @property
    def problems(self) -> list[Finding]:
        return [finding for finding in self.findings if finding.blocking]

    @property
    def notes(self) -> list[Finding]:
        return [finding for finding in self.findings if not finding.blocking]

    @property
    def clean(self) -> bool:
        return not self.findings


def _day(day: date) -> str:
    return f"{day:%d.%m}"


def _empty_days(schedule: ScheduleData, cells: dict[Cell, Hours]) -> list[Finding]:
    """Days the pharmacy is open and nobody has been put on."""
    taken = {day for _, day in cells}
    missing = [
        info.day for info in schedule.timeline() if not info.closed and info.day not in taken
    ]
    if not missing:
        return []
    return [
        Finding(
            Kind.EMPTY_DAY,
            t("audit.empty_days", days=", ".join(_day(day) for day in missing)),
        )
    ]


def _coverage(schedule: ScheduleData, cells: dict[Cell, Hours]) -> list[Finding]:
    problems = uncovered_days(schedule, cells)
    return [
        Finding(
            Kind.NO_PHARMACIST,
            t("audit.no_pharmacist", day=_day(day), hours=problems[day].full_hours),
        )
        for day in sorted(problems)
    ]


def _outside_hours(schedule: ScheduleData, cells: dict[Cell, Hours]) -> list[Finding]:
    names = {lane.id: lane.name for lane in schedule.lanes}
    timeline = {info.day: info for info in schedule.timeline()}

    findings = []
    ordered = sorted(cells.items(), key=lambda item: (item[0][1], item[0][0]))
    for (lane, day), (start, end) in ordered:
        info = timeline.get(day)
        if info is None or info.closed:
            continue
        if start < info.opens or end > info.closes:
            findings.append(
                Finding(
                    Kind.OUTSIDE_HOURS,
                    f"{names.get(lane, '?')} {_day(day)}: {format_range(start, end)} "
                    f"poza otwarciem {format_range(info.opens, info.closes)}",
                )
            )
    return findings


def _idle_people(schedule: ScheduleData, cells: dict[Cell, Hours]) -> list[Finding]:
    working = {lane for lane, _ in cells}
    return [
        Finding(Kind.IDLE_PERSON, f"{lane.name} nie ma ani jednej zmiany")
        for lane in schedule.lanes
        if lane.id not in working
    ]


def audit(schedule: ScheduleData, cells: dict[Cell, Hours]) -> Audit:
    """Everything worth saying before a schedule is closed, in one pass over plain data.

    Takes no session: the same call serves the dialog, the printout and the tests.
    """
    return Audit(
        [
            *_empty_days(schedule, cells),
            *_coverage(schedule, cells),
            *_outside_hours(schedule, cells),
            *_idle_people(schedule, cells),
        ]
    )
