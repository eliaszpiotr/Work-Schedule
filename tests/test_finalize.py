from datetime import date, time
from pathlib import Path

import pytest
from PySide6.QtWidgets import QLineEdit
from sqlalchemy import Engine

from work_scheduler.database.models import Profession, ScheduleStatus
from work_scheduler.database.session import create_session_factory
from work_scheduler.services import (
    DayHours,
    EmployeeService,
    OpeningHoursService,
    ScheduleData,
    ScheduleService,
    ShiftService,
)
from work_scheduler.services.audit import Audit, Finding, Kind
from work_scheduler.ui.schedules import schedule_grid
from work_scheduler.ui.schedules.export_actions import save_as_pdf
from work_scheduler.ui.schedules.finalize_dialog import FinalizeDialog, Outcome
from work_scheduler.ui.schedules.schedule_grid import ScheduleGridView
from work_scheduler.ui.schedules.schedules_view import SchedulesView
from work_scheduler.ui.theme import LIGHT

PERIOD = (date(2026, 8, 12), date(2026, 8, 14))
WEEK = [DayHours(weekday, time(8), time(20)) for weekday in range(7)]


@pytest.fixture
def schedules(engine: Engine) -> ScheduleService:
    return ScheduleService(create_session_factory(engine))


@pytest.fixture
def shifts(engine: Engine) -> ShiftService:
    return ShiftService(create_session_factory(engine))


@pytest.fixture
def employees(engine: Engine) -> EmployeeService:
    service = EmployeeService(create_session_factory(engine))
    service.create("Anna", "Kowalska", Profession.PHARMACIST)
    service.create("Marek", "Nowak", Profession.TECHNICIAN)
    return service


@pytest.fixture
def schedule_id(schedules: ScheduleService, employees: EmployeeService) -> int:
    ids = [person.id for person in employees.list_employees()]
    return schedules.create("Sierpień", *PERIOD, ids, WEEK).id


@pytest.fixture
def filled(schedules: ScheduleService, shifts: ShiftService, schedule_id: int) -> int:
    """A schedule nobody can complain about: everyone in, all day, every day."""
    data = schedules.open_schedule(schedule_id)
    for lane in data.lanes:
        for day in data.days():
            shifts.set_shift(lane.id, day, time(8), time(20))
    return schedule_id


def status(schedules: ScheduleService, schedule_id: int) -> ScheduleStatus:
    return schedules.open_schedule(schedule_id).status


class TestClosing:
    def test_closing_marks_the_schedule_ready(
        self, schedules: ScheduleService, filled: int
    ) -> None:
        schedules.finalize(filled)
        assert status(schedules, filled) is ScheduleStatus.FINAL

    def test_closing_records_when(self, schedules: ScheduleService, filled: int) -> None:
        schedules.finalize(filled)
        summary = next(one for one in schedules.list_schedules() if one.id == filled)
        assert summary.status is ScheduleStatus.FINAL

    def test_reopening_puts_it_back(self, schedules: ScheduleService, filled: int) -> None:
        schedules.finalize(filled)
        schedules.reopen(filled)
        assert status(schedules, filled) is ScheduleStatus.DRAFT


class TestEditingAfterClosing:
    def test_writing_a_cell_returns_it_to_draft(
        self, schedules: ScheduleService, shifts: ShiftService, filled: int
    ) -> None:
        schedules.finalize(filled)
        lane = schedules.open_schedule(filled).lanes[0]

        assert shifts.set_shift(lane.id, PERIOD[0], time(9), time(17)) is True
        assert status(schedules, filled) is ScheduleStatus.DRAFT

    def test_clearing_a_cell_returns_it_to_draft(
        self, schedules: ScheduleService, shifts: ShiftService, filled: int
    ) -> None:
        schedules.finalize(filled)
        lane = schedules.open_schedule(filled).lanes[0]

        assert shifts.clear_shift(lane.id, PERIOD[0]) is True
        assert status(schedules, filled) is ScheduleStatus.DRAFT

    def test_clearing_an_empty_cell_leaves_the_status_alone(
        self, schedules: ScheduleService, shifts: ShiftService, filled: int
    ) -> None:
        lane = schedules.open_schedule(filled).lanes[0]
        shifts.clear_shift(lane.id, PERIOD[0])
        schedules.finalize(filled)

        assert shifts.clear_shift(lane.id, PERIOD[0]) is False
        assert status(schedules, filled) is ScheduleStatus.FINAL

    def test_closing_a_day_by_hand_returns_it_to_draft(
        self, schedules: ScheduleService, filled: int
    ) -> None:
        schedules.finalize(filled)
        schedules.override_day(filled, PERIOD[0], None, None)
        assert status(schedules, filled) is ScheduleStatus.DRAFT

    def test_editing_a_draft_changes_nothing(
        self, schedules: ScheduleService, shifts: ShiftService, filled: int
    ) -> None:
        lane = schedules.open_schedule(filled).lanes[0]
        assert shifts.set_shift(lane.id, PERIOD[0], time(9), time(17)) is False


class TestDialog:
    @staticmethod
    def dialog(application, findings: list[Finding]) -> FinalizeDialog:  # noqa: ANN001
        return FinalizeDialog(None, Audit(findings), LIGHT)

    def test_a_clean_schedule_says_so(self, application) -> None:  # noqa: ANN001
        assert self.dialog(application, []).windowTitle() == "Zakończ grafik"

    def test_a_problem_leads_the_window(self, application) -> None:  # noqa: ANN001
        window = self.dialog(application, [Finding(Kind.EMPTY_DAY, "Nikogo nie wpisano: 12.08")])
        assert "niedokończony" in window._headline()

    def test_notes_alone_do_not_call_it_unfinished(self, application) -> None:  # noqa: ANN001
        window = self.dialog(application, [Finding(Kind.NO_PHARMACIST, "Brak magistra")])
        assert "niedokończony" not in window._headline()
        assert window._audit.problems == []

    def test_nothing_is_chosen_until_a_button_is_pressed(self, application) -> None:  # noqa: ANN001
        assert self.dialog(application, []).outcome is Outcome.CANCEL


class TestGridButton:
    @pytest.fixture
    def opened(
        self, application, schedules: ScheduleService, shifts: ShiftService, filled: int
    ) -> tuple[ScheduleGridView, ScheduleData]:
        data = schedules.open_schedule(filled)
        return ScheduleGridView(data, schedules, shifts, LIGHT), data

    def test_the_check_sees_a_finished_schedule_as_clean(
        self, opened: tuple[ScheduleGridView, ScheduleData]
    ) -> None:
        view, _ = opened
        assert view.check().clean

    def test_closing_from_the_grid_marks_it_ready(
        self,
        opened: tuple[ScheduleGridView, ScheduleData],
        schedules: ScheduleService,
        filled: int,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        view, _ = opened
        monkeypatch.setattr(schedule_grid, "FinalizeDialog", accepting(Outcome.CLOSE))

        announced: list[tuple[int, bool]] = []
        view.finalized.connect(lambda schedule_id, save: announced.append((schedule_id, save)))
        view.finish_schedule()

        assert announced == [(filled, False)]
        assert status(schedules, filled) is ScheduleStatus.FINAL

    def test_asking_for_the_pdf_is_passed_on(
        self,
        opened: tuple[ScheduleGridView, ScheduleData],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        view, _ = opened
        monkeypatch.setattr(schedule_grid, "FinalizeDialog", accepting(Outcome.CLOSE_AND_SAVE))

        announced: list[bool] = []
        view.finalized.connect(lambda _, save: announced.append(save))
        view.finish_schedule()

        assert announced == [True]

    def test_a_cell_still_being_typed_in_is_written_before_closing(
        self,
        opened: tuple[ScheduleGridView, ScheduleData],
        schedules: ScheduleService,
        filled: int,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Qt hands an open editor's value to the model only when the view dies.

        Closing with one open therefore wrote a shift after the schedule was marked
        ready, and the write pulled it straight back to draft.
        """
        view, _ = opened
        monkeypatch.setattr(schedule_grid, "FinalizeDialog", accepting(Outcome.CLOSE))
        view.show()

        index = view._model.index(0, 0)
        view._table.setCurrentIndex(index)
        view._table.edit(index)
        editor = view._table.findChild(QLineEdit)
        assert editor is not None
        editor.setText("9-15")

        view.finish_schedule()

        assert status(schedules, filled) is ScheduleStatus.FINAL

    def test_what_was_typed_is_kept_not_thrown_away(
        self,
        opened: tuple[ScheduleGridView, ScheduleData],
        shifts: ShiftService,
        filled: int,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        view, data = opened
        monkeypatch.setattr(schedule_grid, "FinalizeDialog", accepting(Outcome.CLOSE))
        view.show()

        index = view._model.index(0, 0)
        view._table.setCurrentIndex(index)
        view._table.edit(index)
        view._table.findChild(QLineEdit).setText("9-15")

        view.finish_schedule()

        assert shifts.grid(filled)[data.lanes[0].id, PERIOD[0]] == (time(9), time(15))

    def test_the_check_sees_the_cell_being_typed_in(
        self, opened: tuple[ScheduleGridView, ScheduleData]
    ) -> None:
        view, _ = opened
        view.show()
        index = view._model.index(0, 0)
        view._table.setCurrentIndex(index)
        view._table.edit(index)
        view._table.findChild(QLineEdit).setText("6-22")

        outside = [finding for finding in view.check().notes if finding.kind is Kind.OUTSIDE_HOURS]

        assert outside != []

    def test_cancelling_leaves_the_schedule_alone(
        self,
        opened: tuple[ScheduleGridView, ScheduleData],
        schedules: ScheduleService,
        filled: int,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        view, _ = opened
        monkeypatch.setattr(schedule_grid, "FinalizeDialog", refusing())
        view.finish_schedule()

        assert status(schedules, filled) is ScheduleStatus.DRAFT


def accepting(outcome: Outcome):  # noqa: ANN201 - a stand-in for the dialog class
    class Stub:
        DialogCode = FinalizeDialog.DialogCode

        def __init__(self, *_: object) -> None:
            self.outcome = outcome

        def exec(self) -> int:
            return FinalizeDialog.DialogCode.Accepted

    return Stub


def refusing():  # noqa: ANN201 - a stand-in for the dialog class
    class Stub:
        DialogCode = FinalizeDialog.DialogCode

        def __init__(self, *_: object) -> None:
            self.outcome = Outcome.CANCEL

        def exec(self) -> int:
            return FinalizeDialog.DialogCode.Rejected

    return Stub


class TestListActions:
    @pytest.fixture
    def view(
        self,
        application,
        schedules: ScheduleService,
        employees: EmployeeService,
        shifts: ShiftService,
        engine: Engine,
    ) -> SchedulesView:
        hours = OpeningHoursService(create_session_factory(engine))
        return SchedulesView(schedules, employees, hours, shifts, LIGHT)

    @staticmethod
    def menu_entries(view: SchedulesView) -> dict[str, bool]:
        from PySide6.QtWidgets import QMenu

        menu = QMenu()
        view._add_export_actions(menu)
        return {action.text(): action.isEnabled() for action in menu.actions()}

    def test_printing_is_offered_only_once_the_schedule_is_closed(
        self, view: SchedulesView, schedules: ScheduleService, filled: int
    ) -> None:
        view.reload()
        view.pick(filled)
        assert self.menu_entries(view)["Zapisz PDF…"] is False

        schedules.finalize(filled)
        view.reload()
        view.pick(filled)
        assert self.menu_entries(view)["Zapisz PDF…"] is True

    def test_going_back_to_draft_is_offered_only_for_a_closed_one(
        self, view: SchedulesView, schedules: ScheduleService, filled: int
    ) -> None:
        view.reload()
        view.pick(filled)
        assert "Wróć do roboczego" not in self.menu_entries(view)

        schedules.finalize(filled)
        view.reload()
        view.pick(filled)
        assert "Wróć do roboczego" in self.menu_entries(view)

    def test_going_back_to_draft_from_the_list_works(
        self, view: SchedulesView, schedules: ScheduleService, filled: int
    ) -> None:
        schedules.finalize(filled)
        view.reload()
        view.pick(filled)
        view.reopen_selected()

        assert status(schedules, filled) is ScheduleStatus.DRAFT


class TestSavingFromTheList:
    def test_the_file_lands_where_it_was_asked_for(
        self,
        application,  # noqa: ANN001
        schedules: ScheduleService,
        shifts: ShiftService,
        filled: int,
        tmp_path: Path,
    ) -> None:
        written = save_as_pdf(None, schedules, shifts, filled, path=tmp_path / "grafik.pdf")
        assert written is not None
        assert written.exists()

    def test_a_name_without_an_extension_still_becomes_a_pdf(
        self,
        application,  # noqa: ANN001
        schedules: ScheduleService,
        shifts: ShiftService,
        filled: int,
        tmp_path: Path,
    ) -> None:
        written = save_as_pdf(None, schedules, shifts, filled, path=tmp_path / "grafik")
        assert written is not None
        assert written.suffix == ".pdf"
        assert written.exists()
