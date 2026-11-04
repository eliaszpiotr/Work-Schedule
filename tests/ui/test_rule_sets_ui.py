from datetime import time

from PySide6.QtWidgets import QPushButton
from sqlalchemy import Engine

from work_scheduler.database.session import create_session_factory
from work_scheduler.i18n import t
from work_scheduler.services import DayHours
from work_scheduler.services.audit import Audit, Finding, Kind
from work_scheduler.services.rule_sets import RuleSetService
from work_scheduler.ui.schedules.finalize_dialog import FinalizeDialog
from work_scheduler.ui.schedules.schedule_dialog import ScheduleDialog
from work_scheduler.ui.settings.rule_sets_dialog import (
    RuleEditorDialog,
    RuleSetEditDialog,
    RuleSetPickerDialog,
)
from work_scheduler.ui.settings.rule_sets_panel import RuleSetCard, RuleSetsPanel
from work_scheduler.ui.theme import LIGHT


def test_rule_forms_and_schedule_picker(application, engine: Engine) -> None:  # noqa: ANN001
    factory = create_session_factory(engine)
    service = RuleSetService(factory)
    rule = {
        "kind": "coverage",
        "severity": "block",
        "weekdays": [0, 1, 2, 3, 4],
        "start": "08:00",
        "end": None,
    }
    source = service.save("Poranny dyżur", [rule])

    editor = RuleEditorDialog(None, rule)
    assert editor.value() == rule
    editor._accept_valid()
    assert editor.result() == editor.DialogCode.Accepted

    set_editor = RuleSetEditDialog(None, source)
    assert set_editor.name.text() == source.name
    assert set_editor.rows.count() == 1

    manager = RuleSetsPanel(service, LIGHT)
    assert len(manager.findChildren(RuleSetCard)) == 1

    week = [DayHours(day, time(8), time(20)) for day in range(7)]
    wizard = ScheduleDialog(None, [], week, rule_sets=service.list_sets())
    wizard._rule_set.setCurrentIndex(1)
    assert wizard.rule_set_id == source.id


def test_blocking_custom_rule_disables_finalization_actions(application) -> None:  # noqa: ANN001
    finding = Finding(Kind.SATURDAY_COUNT, "Test", True)
    dialog = FinalizeDialog(None, Audit([finding]), LIGHT)
    buttons = {button.text(): button for button in dialog.findChildren(QPushButton)}
    assert not buttons[t("finalize.close_only")].isEnabled()
    assert not buttons[t("finalize.close_and_save")].isEnabled()
    assert buttons[t("common.cancel")].isEnabled()


def test_all_rule_types_round_trip_through_editor(application) -> None:  # noqa: ANN001
    rules = [
        {
            "kind": "saturdays",
            "severity": "warning",
            "comparison": "min",
            "count": 2,
            "profession": "all",
        },
        {
            "kind": "day_count",
            "severity": "block",
            "period": "week",
            "weekdays": [0, 4],
            "comparison": "max",
            "count": 1,
            "profession": "technician",
        },
        {
            "kind": "hours",
            "severity": "warning",
            "period": "month",
            "comparison": "min",
            "minutes": 9300,
            "profession": "all",
        },
        {"kind": "consecutive", "severity": "block", "count": 5, "profession": "pharmacist"},
        {"kind": "coverage", "severity": "warning", "weekdays": [0], "start": "08:00", "end": None},
        {
            "kind": "staffing",
            "severity": "block",
            "weekdays": [1, 3],
            "start": None,
            "end": "18:00",
            "count": 2,
            "profession": "technician",
        },
    ]
    for rule in rules:
        editor = RuleEditorDialog(None, rule)
        assert editor.value() == rule
        editor._accept_valid()
        assert editor.result() == editor.DialogCode.Accepted


def test_picker_keeps_current_selection(application, engine: Engine) -> None:  # noqa: ANN001
    service = RuleSetService(create_session_factory(engine))
    source = service.save(
        "Zespół", [{"kind": "consecutive", "severity": "warning", "count": 5, "profession": "all"}]
    )
    picker = RuleSetPickerDialog(None, service.list_sets(), source.name, LIGHT)
    assert picker.rule_set_id == source.id
    picker.choice.setCurrentIndex(0)
    assert picker.rule_set_id is None


def test_rule_editor_can_target_one_person(application) -> None:  # noqa: ANN001
    rule = {
        "kind": "consecutive",
        "severity": "warning",
        "count": 4,
        "profession": "all",
        "employee_id": 42,
    }
    editor = RuleEditorDialog(None, rule, people=[(42, "Anna Kowalska")])
    assert editor.value() == rule
    assert "Anna Kowalska" in editor.consecutive_profession.currentText()
