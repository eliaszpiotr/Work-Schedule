import pytest

from work_scheduler.ui.text import days, people


@pytest.mark.parametrize(
    ("count", "expected"),
    [(1, "1 dzień"), (2, "2 dni"), (5, "5 dni"), (21, "21 dni"), (22, "22 dni")],
)
def test_days_are_counted_in_polish(count: int, expected: str) -> None:
    assert days(count) == expected


@pytest.mark.parametrize(
    ("count", "expected"),
    [
        (1, "1 osoba"),
        (2, "2 osoby"),
        (4, "4 osoby"),
        (5, "5 osób"),
        (12, "12 osób"),
        (13, "13 osób"),
        (14, "14 osób"),
        (22, "22 osoby"),
        (25, "25 osób"),
        (0, "0 osób"),
    ],
)
def test_people_are_counted_in_polish(count: int, expected: str) -> None:
    assert people(count) == expected
