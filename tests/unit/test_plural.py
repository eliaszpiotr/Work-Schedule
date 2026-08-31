import pytest

from work_scheduler.i18n import Language, translate


class TestPolishForms:
    """1 osoba, 2 osoby, 5 osób — and the teens go with the "many" form."""

    @pytest.mark.parametrize(
        ("count", "expected"),
        [
            (1, "1 osoba"),
            (2, "2 osoby"),
            (4, "4 osoby"),
            (5, "5 osób"),
            (11, "11 osób"),
            (12, "12 osób"),
            (14, "14 osób"),
            (22, "22 osoby"),
            (25, "25 osób"),
            (0, "0 osób"),
        ],
    )
    def test_people(self, count: int, expected: str) -> None:
        assert translate("count.people", Language.PL, count=count) == expected

    @pytest.mark.parametrize(
        ("count", "expected"),
        [(1, "1 dzień"), (2, "2 dni"), (5, "5 dni"), (22, "22 dni")],
    )
    def test_days(self, count: int, expected: str) -> None:
        assert translate("count.days", Language.PL, count=count) == expected

    def test_the_verb_agrees_with_the_noun(self) -> None:
        """Verb and noun are one entry, so they cannot drift apart."""
        assert "wypada 1 święto" in translate(
            "schedule.wizard.holidays_in_period", Language.PL, count=1
        )
        assert "wypadają 2 święta" in translate(
            "schedule.wizard.holidays_in_period", Language.PL, count=2
        )
        assert "wypada 5 świąt" in translate(
            "schedule.wizard.holidays_in_period", Language.PL, count=5
        )


class TestEnglishForms:
    @pytest.mark.parametrize(
        ("count", "expected"),
        [(1, "1 person"), (2, "2 people"), (5, "5 people"), (0, "0 people")],
    )
    def test_people(self, count: int, expected: str) -> None:
        assert translate("count.people", Language.EN, count=count) == expected

    @pytest.mark.parametrize(("count", "expected"), [(1, "1 day"), (2, "2 days")])
    def test_days(self, count: int, expected: str) -> None:
        assert translate("count.days", Language.EN, count=count) == expected
