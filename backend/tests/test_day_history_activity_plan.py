
from datetime import date

from backend.services.day_history import DayHistoryService


class FakeDailyLogsRepository:
    def __init__(self, rows):
        self.rows = rows

    def list_date_range(
        self,
        user_id,
        start_date,
        end_date,
    ):
        return self.rows


class FakeActivitiesRepository:
    def __init__(self, rows):
        self.rows = rows

    def list_date_range(
        self,
        user_id,
        start_date,
        end_date,
    ):
        return self.rows


def build_service(logs, activities):
    return DayHistoryService(
        daily_logs_repo=FakeDailyLogsRepository(logs),
        activities_repo=FakeActivitiesRepository(activities),
    )


def test_activity_plan_profile_aggregates_activity_per_day():
    service = build_service(
        [
            {"date": "2026-08-25", "activity_plan": "Attiva"},
            {"date": "2026-08-26", "activity_plan": "Attiva"},
        ],
        [
            {"date": "2026-08-25", "burned_calories": 300},
            {"date": "2026-08-25", "burned_calories": 200},
            {"date": "2026-08-26", "burned_calories": 400},
        ],
    )

    result = service.activity_profile_by_activity_plan(
        user_id="u1",
        end_date=date(2026, 8, 26),
        lookback_days=2,
    )

    profile = result["profiles"]["Attiva"]

    assert profile["days"] == 2
    assert profile["days_with_activity"] == 2
    assert profile["days_without_activity"] == 0
    assert profile["average_burned_calories"] == 450
    assert profile["median_burned_calories"] == 450
    assert profile["min_burned_calories"] == 400
    assert profile["max_burned_calories"] == 500


def test_activity_plan_profile_counts_days_without_activity():
    service = build_service(
        [
            {"date": "2026-08-25", "activity_plan": "Riposo"},
            {"date": "2026-08-26", "activity_plan": "Riposo"},
        ],
        [
            {"date": "2026-08-26", "burned_calories": 100},
        ],
    )

    result = service.activity_profile_by_activity_plan(
        user_id="u1",
        end_date=date(2026, 8, 26),
        lookback_days=2,
    )

    profile = result["profiles"]["Riposo"]

    assert profile["days"] == 2
    assert profile["days_with_activity"] == 1
    assert profile["days_without_activity"] == 1
    assert profile["average_burned_calories"] == 50
    assert profile["median_burned_calories"] == 50


def test_activity_plan_profile_ignores_logs_without_plan():
    service = build_service(
        [
            {"date": "2026-08-25", "activity_plan": None},
            {"date": "2026-08-26", "activity_plan": "Attiva"},
        ],
        [
            {"date": "2026-08-25", "burned_calories": 900},
            {"date": "2026-08-26", "burned_calories": 300},
        ],
    )

    result = service.activity_profile_by_activity_plan(
        user_id="u1",
        end_date=date(2026, 8, 26),
        lookback_days=2,
    )

    assert set(result["profiles"]) == {"Attiva"}
    assert result["profiles"]["Attiva"]["days"] == 1
    assert result["profiles"]["Attiva"]["average_burned_calories"] == 300


def test_activity_plan_profile_keeps_negative_calories_at_zero():
    service = build_service(
        [
            {"date": "2026-08-26", "activity_plan": "Attiva"},
        ],
        [
            {"date": "2026-08-26", "burned_calories": -100},
        ],
    )

    result = service.activity_profile_by_activity_plan(
        user_id="u1",
        end_date=date(2026, 8, 26),
        lookback_days=1,
    )

    profile = result["profiles"]["Attiva"]

    assert profile["days"] == 1
    assert profile["days_with_activity"] == 1
    assert profile["days_without_activity"] == 0
    assert profile["average_burned_calories"] == 0
    assert profile["min_burned_calories"] == 0
    assert profile["max_burned_calories"] == 0


def test_average_activity_kcal_uses_complete_calendar_window():
    service = build_service(
        [],
        [
            {"date": "2026-08-20", "burned_calories": 350},
            {"date": "2026-08-20", "burned_calories": 150},
            {"date": "2026-08-22", "burned_calories": 700},
            {"date": "2026-08-26", "burned_calories": -100},
        ],
    )

    result = service.average_activity_kcal(
        user_id="u1",
        end_date=date(2026, 8, 26),
        lookback_days=7,
    )

    assert result["start_date"] == "2026-08-20"
    assert result["end_date"] == "2026-08-26"
    assert result["total_burned_calories"] == 1200
    assert result["average_burned_calories"] == 171.43


def test_average_activity_kcal_counts_missing_days_as_zero():
    service = build_service(
        [],
        [
            {"date": "2026-08-20", "burned_calories": 350},
        ],
    )

    result = service.average_activity_kcal(
        user_id="u1",
        end_date=date(2026, 8, 26),
        lookback_days=7,
    )

    assert result["total_burned_calories"] == 350
    assert result["average_burned_calories"] == 50

