from datetime import date, time

import pytest
from sqlalchemy import Engine

from work_scheduler.database.models import Profession, ScheduleStatus
from work_scheduler.database.session import create_session_factory
from work_scheduler.services import DayHours, EmployeeService, ScheduleService, ShiftService
from work_scheduler.services.audit import Kind, audit
from work_scheduler.services.errors import ValidationError
from work_scheduler.services.rule_sets import RuleSetService


def saturday_rule(severity: str = "warning") -> dict:
    return {
        "kind": "saturdays",
        "severity": severity,
        "comparison": "exact",
        "count": 2,
        "profession": "all",
    }


def coverage_rule(severity: str = "warning") -> dict:
    return {
        "kind": "coverage",
        "severity": severity,
        "weekdays": [0, 1, 2, 3, 4],
        "start": "08:00",
        "end": None,
    }


@pytest.fixture
def setup(engine: Engine):  # noqa: ANN201
    factory = create_session_factory(engine)
    people = EmployeeService(factory)
    pharmacist = people.create("Anna", "Kowalska", Profession.PHARMACIST)
    technician = people.create("Marek", "Nowak", Profession.TECHNICIAN)
    schedules = ScheduleService(factory)
    shifts = ShiftService(factory)
    sets = RuleSetService(factory)
    week = [DayHours(day, time(7, 30), time(20)) for day in range(7)]
    return schedules, shifts, sets, week, pharmacist.id, technician.id


def test_rule_set_is_copied_and_can_be_replaced_without_changing_template(setup) -> None:  # noqa: ANN001
    schedules, _, sets, week, pharmacist, technician = setup
    source = sets.save("Apteka", [saturday_rule()])
    schedule = schedules.create(
        "Październik",
        date(2026, 10, 1),
        date(2026, 10, 31),
        [pharmacist, technician],
        week,
        source.id,
    )
    assert schedules.open_schedule(schedule.id).rules == [saturday_rule()]

    sets.save("Apteka", [coverage_rule()], source.id)
    assert schedules.open_schedule(schedule.id).rules == [saturday_rule()]
    schedules.set_rule_set(schedule.id, source.id)
    assert schedules.open_schedule(schedule.id).rules == [coverage_rule()]
    sets.delete(source.id)
    assert schedules.open_schedule(schedule.id).rules == [coverage_rule()]


def test_saturday_rule_warns_for_each_person_and_month(setup) -> None:  # noqa: ANN001
    schedules, shifts, sets, week, pharmacist, technician = setup
    source = sets.save("Soboty", [saturday_rule()])
    created = schedules.create(
        "Październik",
        date(2026, 10, 1),
        date(2026, 10, 31),
        [pharmacist, technician],
        week,
        source.id,
    )
    data = schedules.open_schedule(created.id)
    shifts.set_shift(data.lanes[0].id, date(2026, 10, 3), time(8), time(16))
    findings = [
        item
        for item in audit(data, shifts.grid(created.id)).findings
        if item.kind is Kind.SATURDAY_COUNT
    ]
    assert len(findings) == 2
    assert all(not item.blocking for item in findings)
    assert "1" in findings[0].text


def test_partial_month_is_not_judged_as_full_month(setup) -> None:  # noqa: ANN001
    schedules, shifts, sets, week, pharmacist, _ = setup
    source = sets.save("Soboty", [saturday_rule()])
    created = schedules.create(
        "Część miesiąca",
        date(2026, 10, 10),
        date(2026, 10, 20),
        [pharmacist],
        week,
        source.id,
    )
    assert not any(
        item.kind is Kind.SATURDAY_COUNT
        for item in audit(schedules.open_schedule(created.id), shifts.grid(created.id)).findings
    )


def test_coverage_starts_at_eight_and_blocking_rule_prevents_finalization(setup) -> None:  # noqa: ANN001
    schedules, shifts, sets, week, pharmacist, technician = setup
    source = sets.save("Magister", [coverage_rule("block")])
    created = schedules.create(
        "Tydzień",
        date(2026, 10, 5),
        date(2026, 10, 11),
        [pharmacist, technician],
        week,
        source.id,
    )
    data = schedules.open_schedule(created.id)
    pharm_lane, tech_lane = data.lanes
    shifts.set_shift(pharm_lane.id, date(2026, 10, 5), time(8), time(20))
    shifts.set_shift(tech_lane.id, date(2026, 10, 5), time(7, 30), time(20))
    first = audit(data, shifts.grid(created.id))
    assert not any(
        item.kind is Kind.NO_PHARMACIST for item in first.findings if "05.10" in item.text
    )

    shifts.clear_shift(pharm_lane.id, date(2026, 10, 5))
    second = audit(data, shifts.grid(created.id))
    gap = next(
        item for item in second.findings if item.kind is Kind.NO_PHARMACIST and "05.10" in item.text
    )
    assert gap.blocking
    assert "08:00" in gap.text
    with pytest.raises(ValidationError):
        schedules.finalize(created.id)
    assert schedules.open_schedule(created.id).status is ScheduleStatus.DRAFT


def test_coverage_warning_allows_finalization(setup) -> None:  # noqa: ANN001
    schedules, shifts, sets, week, pharmacist, technician = setup
    source = sets.save("Magister", [coverage_rule("warning")])
    created = schedules.create(
        "Tydzień",
        date(2026, 10, 5),
        date(2026, 10, 11),
        [pharmacist, technician],
        week,
        source.id,
    )
    data = schedules.open_schedule(created.id)
    shifts.set_shift(data.lanes[1].id, date(2026, 10, 5), time(8), time(20))
    schedules.finalize(created.id)
    assert schedules.open_schedule(created.id).status is ScheduleStatus.FINAL


def test_duplicate_coverage_days_and_invalid_time_are_rejected(setup) -> None:  # noqa: ANN001
    _, _, sets, _, _, _ = setup
    duplicate = {**coverage_rule(), "weekdays": [0]}
    with pytest.raises(ValidationError):
        sets.save("Nakładanie", [coverage_rule(), duplicate])
    with pytest.raises(ValidationError):
        sets.save("Godzina", [{**coverage_rule(), "start": "8:00"}])


def test_selected_weekdays_and_hours_are_checked_only_for_complete_periods(setup) -> None:  # noqa: ANN001
    schedules, shifts, sets, week, pharmacist, _ = setup
    rules = [
        {
            "kind": "day_count",
            "severity": "warning",
            "period": "week",
            "weekdays": [0, 2],
            "comparison": "exact",
            "count": 2,
            "profession": "pharmacist",
        },
        {
            "kind": "hours",
            "severity": "block",
            "period": "week",
            "comparison": "min",
            "minutes": 960,
            "profession": "pharmacist",
        },
    ]
    source = sets.save("Zmiany i godziny", rules)
    created = schedules.create(
        "Tydzień", date(2026, 10, 5), date(2026, 10, 11), [pharmacist], week, source.id
    )
    data = schedules.open_schedule(created.id)
    lane = data.lanes[0].id
    shifts.set_shift(lane, date(2026, 10, 5), time(8), time(16))
    findings = audit(data, shifts.grid(created.id)).findings
    assert any(item.kind is Kind.DAY_COUNT and not item.blocking for item in findings)
    assert any(item.kind is Kind.HOURS_COUNT and item.blocking for item in findings)
    shifts.set_shift(lane, date(2026, 10, 7), time(8), time(16))
    findings = audit(data, shifts.grid(created.id)).findings
    assert not any(item.kind in (Kind.DAY_COUNT, Kind.HOURS_COUNT) for item in findings)


def test_consecutive_days_and_staffing_time_window(setup) -> None:  # noqa: ANN001
    schedules, shifts, sets, week, pharmacist, technician = setup
    rules = [
        {"kind": "consecutive", "severity": "block", "count": 2, "profession": "all"},
        {
            "kind": "staffing",
            "severity": "warning",
            "weekdays": [0],
            "start": "08:00",
            "end": "10:00",
            "count": 2,
            "profession": "all",
        },
    ]
    source = sets.save("Obsada", rules)
    created = schedules.create(
        "Tydzień", date(2026, 10, 5), date(2026, 10, 11), [pharmacist, technician], week, source.id
    )
    data = schedules.open_schedule(created.id)
    first, second = [lane.id for lane in data.lanes]
    for day in (5, 6, 7):
        shifts.set_shift(first, date(2026, 10, day), time(8), time(16))
    shifts.set_shift(second, date(2026, 10, 5), time(9), time(16))
    findings = audit(data, shifts.grid(created.id)).findings
    assert any(item.kind is Kind.CONSECUTIVE and item.blocking for item in findings)
    gap = next(item for item in findings if item.kind is Kind.STAFFING)
    assert not gap.blocking
    assert "08:00" in gap.text and "09:00" in gap.text
    shifts.set_shift(second, date(2026, 10, 5), time(8), time(16))
    assert not any(
        item.kind is Kind.STAFFING for item in audit(data, shifts.grid(created.id)).findings
    )


def test_new_rule_validation_rejects_invalid_bounds(setup) -> None:  # noqa: ANN001
    _, _, sets, _, _, _ = setup
    invalid_rules = [
        {
            "kind": "day_count",
            "severity": "warning",
            "period": "week",
            "weekdays": [0, 0],
            "comparison": "min",
            "count": 2,
            "profession": "all",
        },
        {
            "kind": "hours",
            "severity": "warning",
            "period": "week",
            "comparison": "max",
            "minutes": 10081,
            "profession": "all",
        },
        {"kind": "consecutive", "severity": "warning", "count": 0, "profession": "all"},
        {
            "kind": "staffing",
            "severity": "warning",
            "weekdays": [1],
            "start": "10:00",
            "end": "08:00",
            "count": 2,
            "profession": "all",
        },
    ]
    for rule in invalid_rules:
        with pytest.raises(ValidationError):
            sets.save("Niepoprawny", [rule])


def test_individual_rule_only_checks_selected_person(setup) -> None:  # noqa: ANN001
    schedules, shifts, sets, week, pharmacist, technician = setup
    rule = {
        "kind": "consecutive",
        "severity": "warning",
        "count": 1,
        "profession": "all",
        "employee_id": technician,
    }
    source = sets.save("Indywidualny", [rule])
    created = schedules.create(
        "Tydzień",
        date(2026, 10, 5),
        date(2026, 10, 11),
        [pharmacist, technician],
        week,
        source.id,
    )
    data = schedules.open_schedule(created.id)
    for lane in data.lanes:
        for day in (5, 6):
            shifts.set_shift(lane.id, date(2026, 10, day), time(8), time(16))
    findings = [
        item
        for item in audit(data, shifts.grid(created.id)).findings
        if item.kind is Kind.CONSECUTIVE
    ]
    assert len(findings) == 1
    assert (
        next(lane.name for lane in data.lanes if lane.employee_id == technician) in findings[0].text
    )
    assert len(sets.list_people()) == 2
