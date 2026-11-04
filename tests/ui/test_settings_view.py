from datetime import time

import pytest
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QPushButton
from sqlalchemy import Engine

from work_scheduler.database.session import create_session_factory
from work_scheduler.i18n import t
from work_scheduler.services import DayHours, OpeningHoursService, RuleSetService
from work_scheduler.ui.components import Switch
from work_scheduler.ui.settings.opening_hours_editor import OpeningHoursEditor
from work_scheduler.ui.settings.settings_view import SettingsView
from work_scheduler.ui.theme import LIGHT, METRICS

OPEN_ALL_WEEK = [DayHours(weekday, time(8), time(20)) for weekday in range(7)]


@pytest.fixture
def service(engine: Engine) -> OpeningHoursService:
    return OpeningHoursService(create_session_factory(engine))


@pytest.fixture
def editor(application) -> OpeningHoursEditor:
    return OpeningHoursEditor()


@pytest.fixture
def view(application, service: OpeningHoursService) -> SettingsView:
    return SettingsView(service, LIGHT)


class TestEditor:
    def test_it_has_a_row_for_every_weekday(self, editor: OpeningHoursEditor) -> None:
        editor.set_week(OPEN_ALL_WEEK)

        assert len(editor.week()) == 7

    def test_hours_survive_a_round_trip(self, editor: OpeningHoursEditor) -> None:
        editor.set_week([DayHours(0, time(9), time(17)), *OPEN_ALL_WEEK[1:]])

        assert editor.week()[0] == DayHours(0, time(9), time(17))

    def test_a_closed_day_comes_back_closed(self, editor: OpeningHoursEditor) -> None:
        editor.set_week([DayHours(0, None, None), *OPEN_ALL_WEEK[1:]])

        assert editor.week()[0].closed is True

    def test_closing_a_day_switches_its_hours_off(self, editor: OpeningHoursEditor) -> None:
        editor.set_week(OPEN_ALL_WEEK)
        editor.rows[0].open_switch.setChecked(False)

        assert editor.week()[0].closed is True
        assert editor.rows[0].opens.isEnabled() is False


class TestSettingsView:
    def test_it_opens_on_the_stored_week(
        self, view: SettingsView, service: OpeningHoursService
    ) -> None:
        assert view._editor.week() == service.week()

    def test_saving_keeps_the_change(
        self, view: SettingsView, service: OpeningHoursService
    ) -> None:
        view._editor.set_week([DayHours(0, time(9), time(17)), *OPEN_ALL_WEEK[1:]])
        view.save()

        assert service.week()[0].opens == time(9)

    def test_hours_in_the_wrong_order_are_not_saved(
        self, view: SettingsView, service: OpeningHoursService
    ) -> None:
        view._editor.set_week([DayHours(0, time(20), time(8)), *OPEN_ALL_WEEK[1:]])
        view.save()

        assert service.week()[0].opens == time(8)


class TestSections:
    def test_it_opens_on_appearance(self, view: SettingsView) -> None:
        assert view.section() == "appearance"

    def test_only_one_section_shows_at_a_time(self, view: SettingsView) -> None:
        view.show()
        view.show_section("hours")
        QApplication.processEvents()

        assert view._editor.isVisibleTo(view)
        assert not view._language.isVisibleTo(view)

    def test_the_tabs_switch_the_section(self, view: SettingsView) -> None:
        view._tabs.select("hours")
        view._tabs.changed.emit("hours")

        assert view.section() == "hours"

    def test_save_sits_with_the_hours_not_in_the_header(self, view: SettingsView) -> None:
        hours = view._pages["hours"]

        assert hours.isAncestorOf(view._save)
        assert view._save.text() == t("settings.hours.save")

    def test_a_row_puts_its_label_left_and_its_control_right(self, view: SettingsView) -> None:
        view.resize(900, 600)
        view.show()
        QApplication.processEvents()
        row = view._language.parentWidget()
        label = row.findChild(QLabel)

        assert row.objectName() == "settingsRow"
        assert label.geometry().right() < view._language.geometry().left()
        right_gap = row.width() - view._language.geometry().right()
        assert right_gap <= METRICS.space_4 + 1

    def test_rows_are_divided_by_lines(self, view: SettingsView) -> None:
        card = view._pages["appearance"].findChild(QFrame, "card")

        assert len(card.findChildren(QFrame, "rowDivider")) == 2


class TestClosedDay:
    def test_the_day_has_a_switch(self, editor: OpeningHoursEditor) -> None:
        assert isinstance(editor.rows[0].open_switch, Switch)

    def test_a_closed_day_says_closed_instead_of_showing_hours(
        self, editor: OpeningHoursEditor
    ) -> None:
        editor.show()
        editor.set_week([*OPEN_ALL_WEEK[:6], DayHours(6, None, None)])
        QApplication.processEvents()
        sunday = editor.rows[6]

        assert sunday.closed_label.isVisibleTo(editor)
        assert sunday.closed_label.text() == t("grid.closed")
        assert not sunday.opens.isVisibleTo(editor)
        assert editor.rows[0].opens.isVisibleTo(editor)


SATURDAY_RULE = {
    "kind": "saturdays",
    "severity": "warning",
    "comparison": "exact",
    "count": 2,
    "profession": "all",
}


class TestRuleSetsTab:
    @pytest.fixture
    def rule_sets(self, engine: Engine) -> RuleSetService:
        return RuleSetService(create_session_factory(engine))

    @pytest.fixture
    def rules_view(self, application, service, rule_sets: RuleSetService) -> SettingsView:
        return SettingsView(service, LIGHT, rule_sets=rule_sets)

    def test_the_sets_show_without_opening_anything(
        self, application, service, rule_sets: RuleSetService
    ) -> None:
        rule_sets.save("Soboty", [SATURDAY_RULE])
        rule_sets.save("Apteka", [SATURDAY_RULE, SATURDAY_RULE])
        view = SettingsView(service, LIGHT, rule_sets=rule_sets)
        view.show()
        view.show_section("rules")
        QApplication.processEvents()

        cards = view._rule_sets_panel.cards()
        assert [card.item.name for card in cards] == ["Apteka", "Soboty"]
        assert all(card.isVisibleTo(view) and card.objectName() == "card" for card in cards)
        assert not view._pages["rules"].findChildren(QPushButton, "manageRuleSets")

    def test_new_set_sits_in_the_header_only_on_its_tab(self, rules_view: SettingsView) -> None:
        rules_view.show()
        rules_view.show_section("rules")
        QApplication.processEvents()
        header = rules_view.findChild(QFrame, "toolbar")

        assert header.isAncestorOf(rules_view._new_set)
        assert rules_view._new_set.isVisibleTo(rules_view)
        rules_view.show_section("appearance")
        assert not rules_view._new_set.isVisibleTo(rules_view)

    def test_no_sets_says_so(self, rules_view: SettingsView) -> None:
        rules_view.show()
        rules_view.show_section("rules")
        QApplication.processEvents()

        assert rules_view._rule_sets_panel._empty.isVisibleTo(rules_view)

    def test_a_new_set_appears_in_the_list(
        self, rules_view: SettingsView, rule_sets: RuleSetService
    ) -> None:
        rule_sets.save("Wakacje", [SATURDAY_RULE])
        rules_view._rule_sets_panel.reload()

        names = [card.item.name for card in rules_view._rule_sets_panel.cards()]
        assert names == ["Wakacje"]
