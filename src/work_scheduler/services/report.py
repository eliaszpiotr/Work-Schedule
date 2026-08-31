from dataclasses import dataclass
from datetime import date, time

from work_scheduler.i18n import Language, current_language, profession_name, translate
from work_scheduler.services.audit import Cell, Hours
from work_scheduler.services.schedule_service import DayInfo, ScheduleData
from work_scheduler.services.time_text import minutes_between


@dataclass(frozen=True, slots=True)
class Person:
    """One column of the schedule, with their own hours already gathered."""

    name: str
    profession: str
    shifts: dict[date, Hours]
    minutes: int

    @property
    def surname(self) -> str:
        return self.name.split(" ", 1)[0]

    @property
    def forename(self) -> str:
        parts = self.name.split(" ", 1)
        return parts[1] if len(parts) > 1 else ""


@dataclass(frozen=True, slots=True)
class ScheduleReport:
    """Everything a printed page needs. Nothing here knows about a database."""

    name: str
    start_date: date
    end_date: date
    days: list[DayInfo]
    people: list[Person]
    # The language the report was built in. The sheet may be printed in Polish while the
    # interface stands in English, so the words cannot be looked up at drawing time.
    language: Language = Language.PL

    @property
    def period(self) -> str:
        return f"{self.start_date:%d.%m.%Y} – {self.end_date:%d.%m.%Y}"

    def hours(self, person: Person, day: date) -> Hours | None:
        return person.shifts.get(day)

    @property
    def total_minutes(self) -> int:
        return sum(person.minutes for person in self.people)


def build_report(
    schedule: ScheduleData, cells: dict[Cell, Hours], language: Language | None = None
) -> ScheduleReport:
    """Turn the open schedule and its grid into the shape the printer draws from."""
    language = language or current_language()
    people = []
    for lane in schedule.lanes:
        shifts = {day: hours for (owner, day), hours in cells.items() if owner == lane.id}
        people.append(
            Person(
                name=lane.name,
                profession=profession_name(lane.profession, language),
                shifts=dict(sorted(shifts.items())),
                minutes=sum(minutes_between(start, end) for start, end in shifts.values()),
            )
        )

    # Nothing from the audit reaches the paper. What is wrong with a schedule is the
    # business of whoever is editing it, not of everyone reading it off the wall.
    return ScheduleReport(
        name=schedule.name,
        start_date=schedule.start_date,
        end_date=schedule.end_date,
        days=schedule.timeline(language),
        people=people,
        language=language,
    )


def suggested_filename(report: ScheduleReport) -> str:
    """A name that sorts by period and survives every filesystem we might meet."""
    safe = "".join(letter if letter.isalnum() or letter in " -_" else "-" for letter in report.name)
    safe = "-".join(safe.split())
    prefix = translate("export.filename_prefix", report.language)
    return f"{prefix}-{safe}-{report.start_date:%Y-%m-%d}.pdf"


def day_hours(day: DayInfo) -> tuple[time, time] | None:
    return None if day.closed else (day.opens, day.closes)
