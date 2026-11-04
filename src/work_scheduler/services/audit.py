from calendar import monthrange
from dataclasses import dataclass
from datetime import date, time, timedelta
from enum import StrEnum

from work_scheduler.i18n import t, weekday_short
from work_scheduler.services.coverage import uncovered_days
from work_scheduler.services.rule_sets import CONSECUTIVE, DAY_COUNT, STAFFING
from work_scheduler.services.rule_sets import HOURS as HOURS_RULE
from work_scheduler.services.schedule_service import ScheduleData
from work_scheduler.services.time_text import format_range

Cell = tuple[int, date]
Hours = tuple[time, time]


class Kind(StrEnum):
    """What was found. Custom rules can override a finding's default severity."""

    EMPTY_DAY = "EMPTY_DAY"
    NO_PHARMACIST = "NO_PHARMACIST"
    OUTSIDE_HOURS = "OUTSIDE_HOURS"
    IDLE_PERSON = "IDLE_PERSON"
    SATURDAY_COUNT = "SATURDAY_COUNT"
    DAY_COUNT = "DAY_COUNT"
    HOURS_COUNT = "HOURS_COUNT"
    CONSECUTIVE = "CONSECUTIVE"
    STAFFING = "STAFFING"


# An open day with nobody on it is marked as unfinished. Custom rules choose their own
# severity independently and can explicitly stop finalization.
BLOCKING = frozenset({Kind.EMPTY_DAY})


@dataclass(frozen=True, slots=True)
class Finding:
    kind: Kind
    text: str
    blocking_override: bool | None = None

    @property
    def blocking(self) -> bool:
        return (
            self.blocking_override if self.blocking_override is not None else self.kind in BLOCKING
        )


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
            problems[day].blocking,
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


def _saturdays(schedule: ScheduleData, cells: dict[Cell, Hours]) -> list[Finding]:
    findings: list[Finding] = []
    months = sorted({(day.year, day.month) for day in schedule.days()})
    for rule in schedule.rules or []:
        if rule["kind"] != "saturdays":
            continue
        for year, month in months:
            # A partial month cannot establish a fair monthly count.
            if schedule.start_date > date(year, month, 1) or schedule.end_date < date(
                year, month, monthrange(year, month)[1]
            ):
                continue
            for lane in schedule.lanes:
                if not _matches(lane, rule):
                    continue
                actual = sum(
                    day.year == year and day.month == month and day.weekday() == 5
                    for employee, day in cells
                    if employee == lane.id
                )
                target = rule["count"]
                comparison = rule["comparison"]
                if (
                    (comparison == "min" and actual >= target)
                    or (comparison == "max" and actual <= target)
                    or (comparison == "exact" and actual == target)
                ):
                    continue
                findings.append(
                    Finding(
                        Kind.SATURDAY_COUNT,
                        t(
                            "audit.saturdays",
                            name=lane.name,
                            month=f"{month:02d}.{year}",
                            actual=actual,
                            comparison=t(f"rules.comparison.{comparison}"),
                            target=target,
                        ),
                        rule["severity"] == "block",
                    )
                )
    return findings


def _matches(lane, rule: dict) -> bool:  # noqa: ANN001
    if "employee_id" in rule:
        return lane.employee_id == rule["employee_id"]
    return rule["profession"] == "all" or lane.profession.value.lower() == rule["profession"]


def _periods(schedule: ScheduleData, period: str) -> list[tuple[date, date]]:
    """Only complete calendar weeks/months; partial edges cannot be judged fairly."""
    result = []
    if period == "week":
        first = schedule.start_date + timedelta(days=(7 - schedule.start_date.weekday()) % 7)
        while first + timedelta(days=6) <= schedule.end_date:
            result.append((first, first + timedelta(days=6)))
            first += timedelta(days=7)
    else:
        year, month = schedule.start_date.year, schedule.start_date.month
        while date(year, month, 1) <= schedule.end_date:
            first = date(year, month, 1)
            last = date(year, month, monthrange(year, month)[1])
            if first >= schedule.start_date and last <= schedule.end_date:
                result.append((first, last))
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return result


def _meets(actual: int, comparison: str, target: int) -> bool:
    return {"min": actual >= target, "exact": actual == target, "max": actual <= target}[comparison]


def _count_rules(schedule: ScheduleData, cells: dict[Cell, Hours]) -> list[Finding]:
    findings = []
    for rule in schedule.rules or []:
        if rule["kind"] not in (DAY_COUNT, HOURS_RULE):
            continue
        for first, last in _periods(schedule, rule["period"]):
            period_label = f"{first:%d.%m}–{last:%d.%m.%Y}"
            for lane in schedule.lanes:
                if not _matches(lane, rule):
                    continue
                shifts = [
                    (day, interval)
                    for (employee, day), interval in cells.items()
                    if employee == lane.id and first <= day <= last
                ]
                if rule["kind"] == DAY_COUNT:
                    actual = sum(day.weekday() in rule["weekdays"] for day, _ in shifts)
                    target = rule["count"]
                    key, kind = "audit.day_count", Kind.DAY_COUNT
                else:
                    actual = sum(
                        int((end.hour * 60 + end.minute) - (start.hour * 60 + start.minute))
                        for _, (start, end) in shifts
                    )
                    target = rule["minutes"]
                    key, kind = "audit.hours_count", Kind.HOURS_COUNT
                if _meets(actual, rule["comparison"], target):
                    continue
                findings.append(
                    Finding(
                        kind,
                        t(
                            key,
                            name=lane.name,
                            period=period_label,
                            actual=(f"{actual / 60:g}" if kind is Kind.HOURS_COUNT else actual),
                            comparison=t(f"rules.comparison.{rule['comparison']}"),
                            target=(f"{target / 60:g}" if kind is Kind.HOURS_COUNT else target),
                            days=(
                                ", ".join(weekday_short(day) for day in rule["weekdays"])
                                if kind is Kind.DAY_COUNT
                                else ""
                            ),
                        ),
                        rule["severity"] == "block",
                    )
                )
    return findings


def _consecutive(schedule: ScheduleData, cells: dict[Cell, Hours]) -> list[Finding]:
    findings = []
    for rule in schedule.rules or []:
        if rule["kind"] != CONSECUTIVE:
            continue
        for lane in schedule.lanes:
            if not _matches(lane, rule):
                continue
            worked = sorted(day for employee, day in cells if employee == lane.id)
            streak_start = previous = None
            for day in [*worked, None]:
                if day is not None and previous is not None and day == previous + timedelta(days=1):
                    previous = day
                    continue
                if streak_start is not None and previous is not None:
                    length = (previous - streak_start).days + 1
                    if length > rule["count"]:
                        findings.append(
                            Finding(
                                Kind.CONSECUTIVE,
                                t(
                                    "audit.consecutive",
                                    name=lane.name,
                                    first=f"{streak_start:%d.%m}",
                                    last=f"{previous:%d.%m}",
                                    actual=length,
                                    target=rule["count"],
                                ),
                                rule["severity"] == "block",
                            )
                        )
                streak_start = previous = day
    return findings


def _staffing(schedule: ScheduleData, cells: dict[Cell, Hours]) -> list[Finding]:
    findings = []
    lanes = {lane.id: lane for lane in schedule.lanes}
    for rule in schedule.rules or []:
        if rule["kind"] != STAFFING:
            continue
        for info in schedule.timeline():
            if info.closed or info.day.weekday() not in rule["weekdays"]:
                continue
            start = (
                max(info.opens, time.fromisoformat(rule["start"])) if rule["start"] else info.opens
            )
            end = min(info.closes, time.fromisoformat(rule["end"])) if rule["end"] else info.closes
            if start >= end:
                continue
            shifts = [
                hours
                for (employee, day), hours in cells.items()
                if day == info.day and employee in lanes and _matches(lanes[employee], rule)
            ]
            points = sorted(
                {
                    start,
                    end,
                    *(max(start, a) for a, b in shifts if a < end and b > start),
                    *(min(end, b) for a, b in shifts if a < end and b > start),
                }
            )
            missing = []
            for left, right in zip(points, points[1:], strict=False):
                active = sum(a <= left and b >= right for a, b in shifts)
                if active < rule["count"]:
                    if missing and missing[-1][1] == left:
                        missing[-1] = (missing[-1][0], right)
                    else:
                        missing.append((left, right))
            if missing:
                findings.append(
                    Finding(
                        Kind.STAFFING,
                        t(
                            "audit.staffing",
                            day=_day(info.day),
                            count=rule["count"],
                            profession=t(f"rules.profession.{rule['profession']}"),
                            hours=", ".join(format_range(a, b) for a, b in missing),
                        ),
                        rule["severity"] == "block",
                    )
                )
    return findings


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
            *_saturdays(schedule, cells),
            *_count_rules(schedule, cells),
            *_consecutive(schedule, cells),
            *_staffing(schedule, cells),
        ]
    )
