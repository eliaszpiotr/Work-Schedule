from copy import deepcopy
from dataclasses import dataclass
from datetime import time

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from work_scheduler.database.models import Employee, RuleSet
from work_scheduler.database.session import session_scope
from work_scheduler.i18n import t
from work_scheduler.services.errors import ValidationError

SATURDAYS = "saturdays"
COVERAGE = "coverage"
DAY_COUNT = "day_count"
HOURS = "hours"
CONSECUTIVE = "consecutive"
STAFFING = "staffing"
WARNING = "warning"
BLOCK = "block"
MAX_RULES = 30
PROFESSIONS = ("all", "pharmacist", "technician")
COMPARISONS = ("min", "exact", "max")
PERIODS = ("week", "month")


def _weekdays(value: object) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(type(day) is int and day in range(7) for day in value)
        and len(set(value)) == len(value)
    )


def _clock(value: object) -> bool:
    if value is None:
        return True
    try:
        parsed = time.fromisoformat(value)
    except (TypeError, ValueError):
        return False
    return value == parsed.strftime("%H:%M")


@dataclass(frozen=True, slots=True)
class RuleSetData:
    id: int
    name: str
    rules: list[dict]


def validate_rules(rules: list[dict]) -> list[dict]:
    """Accept only supported, bounded, JSON-safe rule definitions."""
    if not isinstance(rules, list) or len(rules) > MAX_RULES:
        raise ValidationError(t("rules.error.invalid"))
    clean: list[dict] = []
    covered_weekdays: set[int] = set()
    for rule in rules:
        if not isinstance(rule, dict) or rule.get("severity") not in (WARNING, BLOCK):
            raise ValidationError(t("rules.error.invalid"))
        employee_id = rule.get("employee_id")
        if "employee_id" in rule and (
            type(employee_id) is not int or employee_id < 1 or rule.get("profession") != "all"
        ):
            raise ValidationError(t("rules.error.invalid"))
        scoped = {"employee_id"} if "employee_id" in rule else set()
        if rule.get("kind") == SATURDAYS:
            if (
                set(rule) - scoped != {"kind", "severity", "comparison", "count", "profession"}
                or rule["comparison"] not in COMPARISONS
                or type(rule["count"]) is not int
                or not 0 <= rule["count"] <= 5
                or rule["profession"] not in PROFESSIONS
            ):
                raise ValidationError(t("rules.error.invalid"))
        elif rule.get("kind") == COVERAGE:
            if set(rule) != {"kind", "severity", "weekdays", "start", "end"}:
                raise ValidationError(t("rules.error.invalid"))
            days = rule["weekdays"]
            if not _weekdays(days) or covered_weekdays.intersection(days):
                raise ValidationError(t("rules.error.invalid"))
            covered_weekdays.update(days)
            if not _clock(rule["start"]) or not _clock(rule["end"]):
                raise ValidationError(t("rules.error.invalid"))
            if rule["start"] and rule["end"] and rule["start"] >= rule["end"]:
                raise ValidationError(t("rules.error.invalid"))
        elif rule.get("kind") == DAY_COUNT:
            if (
                set(rule) - scoped
                != {"kind", "severity", "period", "weekdays", "comparison", "count", "profession"}
                or rule["period"] not in PERIODS
                or not _weekdays(rule["weekdays"])
                or rule["comparison"] not in COMPARISONS
                or type(rule["count"]) is not int
                or not 0 <= rule["count"] <= (7 if rule["period"] == "week" else 31)
                or rule["profession"] not in PROFESSIONS
            ):
                raise ValidationError(t("rules.error.invalid"))
        elif rule.get("kind") == HOURS:
            if (
                set(rule) - scoped
                != {"kind", "severity", "period", "comparison", "minutes", "profession"}
                or rule["period"] not in PERIODS
                or rule["comparison"] not in COMPARISONS
                or type(rule["minutes"]) is not int
                or not 0 <= rule["minutes"] <= (10080 if rule["period"] == "week" else 44640)
                or rule["profession"] not in PROFESSIONS
            ):
                raise ValidationError(t("rules.error.invalid"))
        elif rule.get("kind") == CONSECUTIVE:
            if (
                set(rule) - scoped != {"kind", "severity", "count", "profession"}
                or type(rule["count"]) is not int
                or not 1 <= rule["count"] <= 31
                or rule["profession"] not in PROFESSIONS
            ):
                raise ValidationError(t("rules.error.invalid"))
        elif rule.get("kind") == STAFFING:
            if (
                scoped
                or set(rule)
                != {"kind", "severity", "weekdays", "start", "end", "count", "profession"}
                or not _weekdays(rule["weekdays"])
                or not _clock(rule["start"])
                or not _clock(rule["end"])
                or (rule["start"] and rule["end"] and rule["start"] >= rule["end"])
                or type(rule["count"]) is not int
                or not 1 <= rule["count"] <= 30
                or rule["profession"] not in PROFESSIONS
            ):
                raise ValidationError(t("rules.error.invalid"))
        else:
            raise ValidationError(t("rules.error.invalid"))
        clean.append(deepcopy(rule))
    return clean


class RuleSetService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def list_sets(self) -> list[RuleSetData]:
        with session_scope(self._session_factory) as session:
            rows = session.scalars(select(RuleSet).order_by(RuleSet.name)).all()
            return [RuleSetData(row.id, row.name, deepcopy(row.rules)) for row in rows]

    def list_people(self) -> list[tuple[int, str]]:
        with session_scope(self._session_factory) as session:
            rows = session.scalars(
                select(Employee).order_by(Employee.last_name, Employee.first_name)
            ).all()
            return [(row.id, f"{row.first_name} {row.last_name}") for row in rows]

    def save(self, name: str, rules: list[dict], rule_set_id: int | None = None) -> RuleSetData:
        name = name.strip()
        if not name or len(name) > 120:
            raise ValidationError(t("rules.error.name"))
        clean = validate_rules(rules)
        if not clean:
            raise ValidationError(t("rules.error.empty"))
        with session_scope(self._session_factory) as session:
            collision = session.scalar(select(RuleSet).where(RuleSet.name == name))
            if collision is not None and collision.id != rule_set_id:
                raise ValidationError(t("rules.error.duplicate"))
            if rule_set_id is None:
                row = RuleSet(name=name, rules=clean)
                session.add(row)
            else:
                row = session.get(RuleSet, rule_set_id)
                if row is None:
                    raise ValidationError(t("rules.error.missing"))
                row.name, row.rules = name, clean
            session.flush()
            return RuleSetData(row.id, row.name, deepcopy(row.rules))

    def delete(self, rule_set_id: int) -> None:
        with session_scope(self._session_factory) as session:
            row = session.get(RuleSet, rule_set_id)
            if row is None:
                raise ValidationError(t("rules.error.missing"))
            session.delete(row)
