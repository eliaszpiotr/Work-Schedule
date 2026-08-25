from dataclasses import dataclass
from datetime import date, time

from work_scheduler.database.models import Profession
from work_scheduler.services.audit import Cell, Hours
from work_scheduler.services.schedule_service import DayInfo, ScheduleData
from work_scheduler.services.time_text import minutes_between

PROFESSION_NAMES = {Profession.PHARMACIST: "magister", Profession.TECHNICIAN: "technik"}


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

    @property
    def period(self) -> str:
        return f"{self.start_date:%d.%m.%Y} – {self.end_date:%d.%m.%Y}"

    def hours(self, person: Person, day: date) -> Hours | None:
        return person.shifts.get(day)

    @property
    def total_minutes(self) -> int:
        return sum(person.minutes for person in self.people)


def build_report(schedule: ScheduleData, cells: dict[Cell, Hours]) -> ScheduleReport:
    """Turn the open schedule and its grid into the shape the printer draws from."""
    people = []
    for lane in schedule.lanes:
        shifts = {day: hours for (owner, day), hours in cells.items() if owner == lane.id}
        people.append(
            Person(
                name=lane.name,
                profession=PROFESSION_NAMES[lane.profession],
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
        days=schedule.timeline(),
        people=people,
    )


def suggested_filename(report: ScheduleReport) -> str:
    """A name that sorts by period and survives every filesystem we might meet."""
    safe = "".join(letter if letter.isalnum() or letter in " -_" else "-" for letter in report.name)
    safe = "-".join(safe.split())
    return f"Grafik-{safe}-{report.start_date:%Y-%m-%d}.pdf"


def day_hours(day: DayInfo) -> tuple[time, time] | None:
    return None if day.closed else (day.opens, day.closes)
