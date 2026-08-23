from datetime import date

from backend.services.day_metrics import DayMetricsService


class FakeMealsRepository:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def list_for_date_compatible(self, user_id, log_date):
        self.calls.append((user_id, str(log_date)))
        return self.rows


class FakeActivitiesRepository:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def list_for_date(self, user_id, log_date):
        self.calls.append((user_id, str(log_date)))
        return self.rows


def build(meals=None, activities=None):
    meals_repo = FakeMealsRepository(meals or [])
    activities_repo = FakeActivitiesRepository(activities or [])

    service = DayMetricsService(
        meals_repo=meals_repo,
        activities_repo=activities_repo,
    )

    result = service.for_day(
        user_id="u1",
        day_date=date(2026, 8, 25),
    )

    return result, meals_repo, activities_repo


def test_empty_day_returns_zero_actuals():
    result, _, _ = build()

    assert result == {
        "date": "2026-08-25",
        "consumed_kcal": 0.0,
        "protein_consumed_g": 0.0,
        "actual_activity_kcal": 0.0,
        "meal_count": 0,
        "activity_count": 0,
    }


def test_meals_are_aggregated_into_consumed_calories_and_protein():
    result, _, _ = build(
        meals=[
            {"calories": 310, "protein": 18},
            {"calories": 650, "protein": 42},
            {"calories": 120, "protein": 3.5},
        ]
    )

    assert result["consumed_kcal"] == 1080
    assert result["protein_consumed_g"] == 63.5
    assert result["meal_count"] == 3


def test_activities_are_aggregated():
    result, _, _ = build(
        activities=[
            {"burned_calories": 350},
            {"burned_calories": 125},
        ]
    )

    assert result["actual_activity_kcal"] == 475
    assert result["activity_count"] == 2


def test_food_and_activity_are_aggregated_together():
    result, _, _ = build(
        meals=[
            {"calories": 500, "protein": 30},
            {"calories": 700, "protein": 40},
        ],
        activities=[
            {"burned_calories": 450},
        ],
    )

    assert result["consumed_kcal"] == 1200
    assert result["protein_consumed_g"] == 70
    assert result["actual_activity_kcal"] == 450


def test_missing_numeric_fields_do_not_break_aggregation():
    result, _, _ = build(
        meals=[
            {"calories": None, "protein": ""},
            {"name": "Legacy incomplete row"},
            {"calories": "250.5", "protein": "12.25"},
        ],
        activities=[
            {"burned_calories": None},
            {"burned_calories": "100.5"},
        ],
    )

    assert result["consumed_kcal"] == 250.5
    assert result["protein_consumed_g"] == 12.25
    assert result["actual_activity_kcal"] == 100.5


def test_invalid_numeric_values_are_ignored_safely():
    result, _, _ = build(
        meals=[
            {"calories": "bad", "protein": "bad"},
            {"calories": 300, "protein": 20},
        ],
        activities=[
            {"burned_calories": "unknown"},
            {"burned_calories": 200},
        ],
    )

    assert result["consumed_kcal"] == 300
    assert result["protein_consumed_g"] == 20
    assert result["actual_activity_kcal"] == 200


def test_repositories_are_scoped_to_requested_user_and_date():
    _, meals_repo, activities_repo = build()

    assert meals_repo.calls == [("u1", "2026-08-25")]
    assert activities_repo.calls == [("u1", "2026-08-25")]
