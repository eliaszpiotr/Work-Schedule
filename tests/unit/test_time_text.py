from datetime import time

import pytest

from work_scheduler.services.time_text import (
    format_hours,
    format_range,
    format_range_short,
    parse_range,
)


class TestParsing:
    @pytest.mark.parametrize(
        "text",
        [
            "10-15",
            "10:00-15:00",
            "10.00-15.00",
            "10 - 15",
            "10–15",
            "10—15",
            "od 10 do 15",
            "  10:00 – 15:00  ",
        ],
        ids=[
            "bare-hours",
            "colons",
            "dots",
            "spaces",
            "en-dash",
            "em-dash",
            "polish-words",
            "surrounding-space",
        ],
    )
    def test_accepts_the_ways_people_actually_type_it(self, text: str) -> None:
        assert parse_range(text) == (time(10), time(15))

    def test_keeps_the_minutes(self) -> None:
        assert parse_range("8:30-16:15") == (time(8, 30), time(16, 15))

    @pytest.mark.parametrize(
        "text",
        ["", "   ", "10", "abc", "10-", "-15", "25-26", "10:70-15:00", "15-10", "10-10"],
        ids=[
            "empty",
            "blank",
            "single-hour",
            "letters",
            "missing-end",
            "missing-start",
            "outside-the-day",
            "impossible-minutes",
            "end-before-start",
            "zero-length",
        ],
    )
    def test_rejects_what_it_cannot_read(self, text: str) -> None:
        assert parse_range(text) is None

    def test_midnight_end_is_rejected_because_shifts_cannot_cross_it(self) -> None:
        assert parse_range("22-00") is None


class TestFormatting:
    def test_shows_a_range_the_way_the_grid_displays_it(self) -> None:
        assert format_range(time(10), time(15, 30)) == "10:00–15:30"

    def test_the_short_form_drops_a_whole_hour_s_minutes(self) -> None:
        assert format_range_short(time(16), time(20)) == "16–20"

    def test_the_short_form_keeps_real_minutes_without_a_leading_zero(self) -> None:
        assert format_range_short(time(8, 30), time(17)) == "8:30–17"

    def test_shows_hours_with_a_polish_comma(self) -> None:
        assert format_hours(510) == "8,5 h"

    def test_drops_the_fraction_when_there_is_none(self) -> None:
        assert format_hours(480) == "8 h"

    def test_zero_is_a_dash_so_the_totals_row_stays_quiet(self) -> None:
        assert format_hours(0) == "—"
