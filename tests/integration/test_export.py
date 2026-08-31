from collections import Counter
from datetime import date, time
from pathlib import Path

import pytest
from PySide6.QtGui import QImage, QPageLayout, QPainter
from PySide6.QtPdf import QPdfDocument

from work_scheduler.export import ORIENTATION, page_count, save_pdf
from work_scheduler.export.pages import (
    DATE_COLUMN_SHARE,
    MAX_ROW_HEIGHT,
    day_fill,
    draw_grid,
    open_runs,
    period_words,
)
from work_scheduler.export.paint import (
    CLOSED_FILL,
    HOLIDAY_FILL,
    SATURDAY_FILL,
    SUNDAY_FILL,
    Sheet,
)
from work_scheduler.i18n import Language
from work_scheduler.services.report import Person, ScheduleReport, suggested_filename
from work_scheduler.services.schedule_service import DayInfo, days_between

AUGUST = (date(2026, 8, 3), date(2026, 8, 9))


def timeline(start: date, end: date, closed: set[date] | None = None) -> list[DayInfo]:
    closed = closed or set()
    return [
        DayInfo(day, None, None, None, False)
        if day in closed
        else DayInfo(day, time(8), time(20), None, False)
        for day in days_between(start, end)
    ]


def person(name: str, days: list[date], hours: tuple[time, time] = (time(8), time(16))) -> Person:
    minutes = len(days) * (
        (hours[1].hour * 60 + hours[1].minute) - (hours[0].hour * 60 + hours[0].minute)
    )
    return Person(
        name=name,
        profession="magister",
        shifts=dict.fromkeys(days, hours),
        minutes=minutes,
    )


def make_report(people: int = 2) -> ScheduleReport:
    days = days_between(*AUGUST)
    return ScheduleReport(
        name="Sierpień 2026",
        start_date=AUGUST[0],
        end_date=AUGUST[1],
        days=timeline(*AUGUST),
        people=[person(f"Nazwisko{index} Imię", days) for index in range(people)],
    )


def read(path: Path) -> QPdfDocument:
    document = QPdfDocument()
    assert document.load(str(path)) == QPdfDocument.Error.None_
    return document


def text_of(document: QPdfDocument, page: int) -> str:
    return document.getAllText(page).text()


@pytest.fixture
def written(tmp_path: Path, application) -> Path:  # noqa: ANN001 - the shared QApplication
    return save_pdf(make_report(), tmp_path / "grafik.pdf")


class TestShape:
    def test_the_two_grids_come_first_then_one_page_each(self, written: Path) -> None:
        assert read(written).pageCount() == 4

    def test_the_promised_page_count_matches_the_file(self, written: Path) -> None:
        assert page_count(make_report()) == read(written).pageCount()

    def test_a_bigger_team_makes_a_longer_document(
        self,
        tmp_path: Path,
        application,  # noqa: ANN001
    ) -> None:
        path = save_pdf(make_report(people=5), tmp_path / "duzy.pdf")
        assert read(path).pageCount() == 7


class TestOrientation:
    def test_the_document_prints_sideways(self) -> None:
        assert ORIENTATION is QPageLayout.Orientation.Landscape

    def test_every_page_is_sideways_including_the_personal_ones(
        self,
        tmp_path: Path,
        application,  # noqa: ANN001
    ) -> None:
        document = read(save_pdf(make_report(people=8), tmp_path / "szeroki.pdf"))
        for page in range(document.pageCount()):
            size = document.pagePointSize(page)
            assert size.width() > size.height()

    def test_a_full_month_with_a_full_team_still_takes_one_sheet_each(
        self,
        tmp_path: Path,
        application,  # noqa: ANN001
    ) -> None:
        long_period = (date(2026, 8, 1), date(2026, 8, 31))
        days = days_between(*long_period)
        report = ScheduleReport(
            name="Sierpień 2026",
            start_date=long_period[0],
            end_date=long_period[1],
            days=timeline(*long_period),
            people=[person(f"Nazwisko{index} Imię", days) for index in range(9)],
        )
        assert read(save_pdf(report, tmp_path / "pelny.pdf")).pageCount() == 11


class TestContents:
    def test_the_managers_page_carries_the_names_and_the_total(self, written: Path) -> None:
        page = text_of(read(written), 0)
        assert "Nazwisko0" in page
        assert "Razem" in page

    def test_the_wall_copy_leaves_the_totals_off(self, written: Path) -> None:
        assert "Razem" not in text_of(read(written), 1)

    def test_each_person_gets_their_own_page(
        self,
        tmp_path: Path,
        application,  # noqa: ANN001
    ) -> None:
        document = read(save_pdf(make_report(people=3), tmp_path / "trzy.pdf"))
        for index in range(3):
            assert f"Nazwisko{index}" in text_of(document, 2 + index)

    def test_no_page_carries_the_audit(
        self,
        tmp_path: Path,
        application,  # noqa: ANN001
    ) -> None:
        """What is wrong with a schedule belongs on the screen, not on the wall."""
        document = read(save_pdf(make_report(), tmp_path / "czysto.pdf"))
        for page in range(document.pageCount()):
            assert "Braki w obsadzie" not in text_of(document, page)


class TestFilename:
    def test_the_name_carries_the_schedule_and_the_start(self) -> None:
        assert suggested_filename(make_report()) == "Grafik-Sierpień-2026-2026-08-03.pdf"

    def test_a_slash_in_the_name_cannot_reach_the_filesystem(self) -> None:
        report = make_report()
        awkward = ScheduleReport(
            name="Sierpień/wrzesień",
            start_date=report.start_date,
            end_date=report.end_date,
            days=report.days,
            people=report.people,
        )
        assert "/" not in suggested_filename(awkward)


class TestClosedDays:
    def test_a_closed_day_is_left_wordless(self, tmp_path: Path, application) -> None:  # noqa: ANN001
        days = days_between(*AUGUST)
        report = ScheduleReport(
            name="Sierpień 2026",
            start_date=AUGUST[0],
            end_date=AUGUST[1],
            days=timeline(*AUGUST, closed={date(2026, 8, 5)}),
            people=[person("Nowak Anna", [day for day in days if day != date(2026, 8, 5)])],
        )
        # The colour of the band carries it; a word stretched across the columns does not.
        page = text_of(read(save_pdf(report, tmp_path / "zamkniete.pdf")), 0)
        assert "zamknięte" not in page


class TestPageSize:
    def test_pages_are_a4_on_their_side(self, written: Path) -> None:
        size = read(written).pagePointSize(0)
        # A4 sideways in points, within the rounding the writer applies.
        assert round(size.width()) == 842
        assert round(size.height()) == 595


class TestWallCopy:
    def test_it_names_people_without_saying_what_they_do(
        self,
        tmp_path: Path,
        application,  # noqa: ANN001
    ) -> None:
        document = read(save_pdf(make_report(), tmp_path / "tablica.pdf"))
        wall = text_of(document, 1)

        assert "Nazwisko0" in wall
        assert "magister" not in wall

    def test_the_managers_copy_keeps_the_trades(
        self,
        tmp_path: Path,
        application,  # noqa: ANN001
    ) -> None:
        """Cover is checked against them, so the manager's sheet still spells them out."""
        document = read(save_pdf(make_report(), tmp_path / "kierownik.pdf"))
        assert "magister" in text_of(document, 0)


class TestPersonalSheet:
    @staticmethod
    def crossing_months() -> ScheduleReport:
        period = (date(2026, 8, 25), date(2026, 9, 1))
        days = days_between(*period)
        return ScheduleReport(
            name="Sierpień 2026",
            start_date=period[0],
            end_date=period[1],
            days=timeline(*period),
            people=[person("Fiuttak Antoni", days)],
        )

    def test_it_does_not_tell_people_what_they_do_for_a_living(
        self,
        tmp_path: Path,
        application,  # noqa: ANN001
    ) -> None:
        page = text_of(read(save_pdf(make_report(), tmp_path / "osoba.pdf")), 2)
        assert "magister" not in page
        assert "Nazwisko0" in page

    def test_a_period_crossing_a_month_stays_one_calendar(
        self,
        tmp_path: Path,
        application,  # noqa: ANN001
    ) -> None:
        page = text_of(read(save_pdf(self.crossing_months(), tmp_path / "przelom.pdf")), 2)
        # One run of weeks means one row of weekday labels, not one per month.
        assert page.count("PN") == 1

    def test_the_new_month_is_named_where_it_turns_over(
        self,
        tmp_path: Path,
        application,  # noqa: ANN001
    ) -> None:
        page = text_of(read(save_pdf(self.crossing_months(), tmp_path / "wrzesien.pdf")), 2)
        assert "wrz" in page

    def test_the_period_reads_across_the_month_boundary(self) -> None:
        assert period_words(self.crossing_months()) == "25 sierpnia – 1 września 2026"


# Antialiased grey text on a grey band can land on exactly the fill colour, so a
# handful of matching pixels proves nothing. A shaded row covers thousands.
SHADED = 200


def fill_counts(report: ScheduleReport) -> Counter[int]:
    """How much of the page each colour covers, sampled from the pixels.

    Drawn onto an image rather than a PDF: the fills are the point, and a check at
    model level would pass even if nothing reached the paper.
    """
    image = QImage(1200, 850, QImage.Format.Format_RGB32)
    image.fill(0xFFFFFFFF)

    painter = QPainter(image)
    sheet = Sheet.open(painter, image)
    draw_grid(sheet, report, totals=True)
    sheet.close()
    painter.end()

    return Counter(
        image.pixel(x, y) for y in range(0, image.height(), 3) for x in range(0, image.width(), 7)
    )


def report_over(start: date, end: date, holidays: dict[date, str] | None = None) -> ScheduleReport:
    holidays = holidays or {}
    days = [
        DayInfo(day, time(8), time(20), holidays.get(day), False)
        for day in days_between(start, end)
    ]
    return ScheduleReport(
        name="Sierpień 2026",
        start_date=start,
        end_date=end,
        days=days,
        people=[person("Nowak Anna", days_between(start, end))],
    )


class TestRowColours:
    def test_saturday_and_sunday_are_shaded_differently(self, application) -> None:  # noqa: ANN001
        # Monday to Sunday: the last two rows are the weekend.
        counts = fill_counts(report_over(date(2026, 8, 3), date(2026, 8, 9)))
        assert counts[SATURDAY_FILL.rgb()] > SHADED
        assert counts[SUNDAY_FILL.rgb()] > SHADED

    def test_a_week_without_a_weekend_has_no_shading(self, application) -> None:  # noqa: ANN001
        counts = fill_counts(report_over(date(2026, 8, 3), date(2026, 8, 7)))
        assert counts[SATURDAY_FILL.rgb()] < SHADED
        assert counts[SUNDAY_FILL.rgb()] < SHADED

    def test_a_holiday_gets_its_own_colour(self, application) -> None:  # noqa: ANN001
        counts = fill_counts(
            report_over(date(2026, 8, 3), date(2026, 8, 7), {date(2026, 8, 5): "Święto"})
        )
        assert counts[HOLIDAY_FILL.rgb()] > SHADED

    def test_the_shading_is_dark_enough_to_survive_printing(self) -> None:
        # Pure white is 255; anything above about 245 disappears on a laser printer.
        assert SATURDAY_FILL.lightness() < 243
        assert SUNDAY_FILL.lightness() < 235

    def test_the_weekend_is_grey_rather_than_tinted(self) -> None:
        for shade in (SATURDAY_FILL, SUNDAY_FILL):
            assert shade.red() == shade.green() == shade.blue()


def info_for(day: date, *, holiday: str | None = None, closed: bool = False) -> DayInfo:
    if closed:
        return DayInfo(day, None, None, holiday, False)
    return DayInfo(day, time(8), time(20), holiday, False)


class TestDayColour:
    def test_an_ordinary_open_day_is_left_white(self) -> None:
        assert day_fill(info_for(date(2026, 8, 6))) is None

    def test_a_weekday_nobody_works_is_still_white(self) -> None:
        """Not working is not the same as the pharmacy being shut."""
        assert day_fill(info_for(date(2026, 8, 6))) is None

    def test_saturday_is_shaded_even_when_the_pharmacy_opens(self) -> None:
        assert day_fill(info_for(date(2026, 8, 8))) is SATURDAY_FILL

    def test_sunday_has_its_own_shade_darker_than_saturday(self) -> None:
        assert day_fill(info_for(date(2026, 8, 9), closed=True)) is SUNDAY_FILL
        assert SUNDAY_FILL.lightness() < SATURDAY_FILL.lightness()

    def test_a_weekday_shut_by_hand_gets_the_closed_colour(self) -> None:
        assert day_fill(info_for(date(2026, 8, 6), closed=True)) is CLOSED_FILL

    def test_a_holiday_beats_everything_else(self) -> None:
        assert day_fill(info_for(date(2026, 8, 15), holiday="Święto", closed=True)) is HOLIDAY_FILL

    def test_every_kind_of_day_gets_its_own_colour(self) -> None:
        shades = {SATURDAY_FILL.rgb(), SUNDAY_FILL.rgb(), CLOSED_FILL.rgb(), HOLIDAY_FILL.rgb()}
        assert len(shades) == 4


class TestColumnRules:
    """Every row is ruled the same. A gap in the table reads as a hole punched in it."""

    def test_an_uninterrupted_week_is_one_run(self) -> None:
        days = [info_for(day) for day in days_between(date(2026, 8, 3), date(2026, 8, 7))]
        assert open_runs(days) == [(0, 5)]

    def test_a_holiday_does_not_break_the_run(self) -> None:
        days = [info_for(day) for day in days_between(date(2026, 8, 3), date(2026, 8, 7))]
        days[2] = info_for(date(2026, 8, 5), holiday="Święto", closed=True)
        assert open_runs(days) == [(0, 5)]

    def test_a_shut_day_without_a_name_keeps_its_rules(self) -> None:
        """A closed Sunday is a normal row in a different colour, not a gap."""
        days = [info_for(day) for day in days_between(date(2026, 8, 3), date(2026, 8, 9))]
        days[-1] = info_for(date(2026, 8, 9), closed=True)
        assert open_runs(days) == [(0, 7)]

    def test_a_holiday_at_each_end_still_leaves_one_run(self) -> None:
        days = [info_for(day) for day in days_between(date(2026, 8, 3), date(2026, 8, 7))]
        days[0] = info_for(date(2026, 8, 3), holiday="Święto", closed=True)
        days[-1] = info_for(date(2026, 8, 7), holiday="Święto", closed=True)
        assert open_runs(days) == [(0, 5)]

    def test_a_period_with_no_days_has_nothing_to_rule(self) -> None:
        assert open_runs([]) == []

    @pytest.mark.parametrize(
        ("language", "holiday"),
        [
            (Language.PL, "Wniebowzięcie NMP"),
            (Language.EN, "Assumption of Mary"),
        ],
    )
    def test_rendered_holiday_keeps_every_vertical_rule(
        self,
        application,
        language: Language,
        holiday: str,  # noqa: ANN001
    ) -> None:
        """The label may never paint a hole over the table in either language."""
        report = make_report(people=3)
        holiday_index = 2
        holiday_day = report.days[holiday_index].day
        days = list(report.days)
        days[holiday_index] = DayInfo(holiday_day, None, None, holiday, False)
        report = ScheduleReport(
            report.name,
            report.start_date,
            report.end_date,
            days,
            report.people,
            language,
        )

        image = QImage(1200, 850, QImage.Format.Format_RGB32)
        image.fill(0xFFFFFFFF)
        painter = QPainter(image)
        sheet = Sheet.open(painter, image)
        draw_grid(sheet, report, totals=True)

        top = 92
        units = len(report.days) + 1.8 + 1.4
        row_height = min((sheet.height - top - 18) / units, MAX_ROW_HEIGHT)
        head_height = row_height * 1.8
        y = top + head_height + (holiday_index + 0.5) * row_height
        date_width = sheet.width * DATE_COLUMN_SHARE
        column_width = (sheet.width - date_width) / len(report.people)
        rules = [date_width + index * column_width for index in range(len(report.people))]
        scale = sheet.scale

        sheet.close()
        painter.end()

        for rule in rules:
            x, row = round(rule * scale), round(y * scale)
            pixels = [image.pixelColor(x + offset, row).lightness() for offset in range(-2, 3)]
            assert min(pixels) < 160
