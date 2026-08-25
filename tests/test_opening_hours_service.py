from datetime import time

import pytest
from sqlalchemy import Engine

from work_scheduler.database.models import OpeningHours
from work_scheduler.database.session import create_session_factory
from work_scheduler.services import DayHours, OpeningHoursService, ValidationError


@pytest.fixture
def service(engine: Engine) -> OpeningHoursService:
    return OpeningHoursService(create_session_factory(engine))


class TestReading:
    def test_a_fresh_database_still_describes_a_whole_week(
        self, service: OpeningHoursService
    ) -> None:
        week = service.week()

        assert [day.weekday for day in week] == [0, 1, 2, 3, 4, 5, 6]

    def test_the_default_week_opens_on_weekdays_and_closes_on_sunday(
        self, service: OpeningHoursService
    ) -> None:
        week = service.week()

        assert week[0].opens == time(8)
        assert week[0].closes == time(20)
        assert week[6].closed is True

    def test_asking_twice_does_not_create_a_second_week(
        self, service: OpeningHoursService, session
    ) -> None:
        service.week()
        service.week()

        assert session.query(OpeningHours).count() == 7


class TestSaving:
    def test_saved_hours_come_back(self, service: OpeningHoursService) -> None:
        week = service.week()
        service.save([*week[:5], DayHours(5, time(10), time(14)), week[6]])

        assert service.week()[5].opens == time(10)

    def test_a_day_can_be_closed(self, service: OpeningHoursService) -> None:
        week = service.week()
        service.save([DayHours(0, None, None), *week[1:]])

        assert service.week()[0].closed is True

    def test_closing_before_opening_is_refused(self, service: OpeningHoursService) -> None:
        week = service.week()

        with pytest.raises(ValidationError):
            service.save([DayHours(0, time(20), time(8)), *week[1:]])

    def test_half_filled_hours_are_refused(self, service: OpeningHoursService) -> None:
        week = service.week()

        with pytest.raises(ValidationError):
            service.save([DayHours(0, time(8), None), *week[1:]])

    def test_a_partial_week_is_refused(self, service: OpeningHoursService) -> None:
        with pytest.raises(ValidationError):
            service.save([DayHours(0, time(8), time(20))])
