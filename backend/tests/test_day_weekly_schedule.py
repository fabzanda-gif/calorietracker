from datetime import date

from backend.services.day import DayService


class FakeDailyLogsRepository:
    def get_for_date_compatible(
        self,
        user_id,
        log_date,
    ):
        return None

    def list_date_range(
        self,
        user_id,
        start_date,
        end_date,
        columns=None,
    ):
        return []


class FakeWeeklyScheduleRepository:
    def list_for_week(
        self,
        user_id,
        week_start,
    ):
        return [
            {
                "day_of_week": 1,
                "context": "home",
            },
            {
                "day_of_week": 2,
                "context": "office",
            },
            {
                "day_of_week": 3,
                "context": "home",
            },
        ]


def test_wednesday_uses_wednesday_schedule_not_tuesday():
    result = DayService(
        daily_logs_repo=FakeDailyLogsRepository(),
        weekly_schedule_repo=(
            FakeWeeklyScheduleRepository()
        ),
    ).build_day(
        user_id="user-1",
        day_date=date(2026, 9, 2),
    )

    assert result["context"] == {
        "value": "home",
        "state": "predicted",
        "source": "weekly_schedule",
    }


def test_monday_uses_day_number_one():
    result = DayService(
        daily_logs_repo=FakeDailyLogsRepository(),
        weekly_schedule_repo=(
            FakeWeeklyScheduleRepository()
        ),
    ).build_day(
        user_id="user-1",
        day_date=date(2026, 8, 31),
    )

    assert result["context"]["value"] == "home"
