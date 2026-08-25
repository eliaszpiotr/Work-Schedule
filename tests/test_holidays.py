from datetime import date

import pytest

from work_scheduler.services.holidays import easter, holiday_name, holidays_in, holidays_within


class TestEaster:
    @pytest.mark.parametrize(
        ("year", "expected"),
        [
            (2024, date(2024, 3, 31)),
            (2025, date(2025, 4, 20)),
            (2026, date(2026, 4, 5)),
            (2027, date(2027, 3, 28)),
            (2030, date(2030, 4, 21)),
        ],
    )
    def test_it_lands_on_the_right_sunday(self, year: int, expected: date) -> None:
        assert easter(year) == expected

    def test_easter_is_always_a_sunday(self) -> None:
        assert all(easter(year).weekday() == 6 for year in range(2020, 2060))


class TestPolishHolidays:
    def test_fixed_dates_are_named(self) -> None:
        days = holidays_in(2026)

        assert days[date(2026, 11, 11)] == "Święto Niepodległości"
        assert days[date(2026, 1, 1)] == "Nowy Rok"
        assert days[date(2026, 12, 26)] == "drugi dzień Bożego Narodzenia"

    def test_movable_dates_follow_easter(self) -> None:
        days = holidays_in(2026)

        assert days[date(2026, 4, 6)] == "Poniedziałek Wielkanocny"
        assert days[date(2026, 6, 4)] == "Boże Ciało"
        assert days[date(2026, 5, 24)] == "Zielone Świątki"

    def test_christmas_eve_counts_from_2025(self) -> None:
        assert date(2024, 12, 24) not in holidays_in(2024)
        assert date(2025, 12, 24) in holidays_in(2025)

    def test_an_ordinary_day_has_no_name(self) -> None:
        assert holiday_name(date(2026, 8, 14)) is None

    def test_a_holiday_is_named(self) -> None:
        assert holiday_name(date(2026, 8, 15)) == "Wniebowzięcie NMP"


class TestWithinAPeriod:
    def test_it_finds_the_holidays_of_a_period(self) -> None:
        found = holidays_within(date(2026, 8, 10), date(2026, 8, 20))

        assert list(found) == [date(2026, 8, 15)]

    def test_a_period_without_holidays_finds_none(self) -> None:
        assert holidays_within(date(2026, 8, 16), date(2026, 8, 31)) == {}

    def test_a_period_spanning_new_year_looks_at_both_years(self) -> None:
        found = holidays_within(date(2026, 12, 23), date(2027, 1, 2))

        assert set(found) == {
            date(2026, 12, 24),
            date(2026, 12, 25),
            date(2026, 12, 26),
            date(2027, 1, 1),
        }
