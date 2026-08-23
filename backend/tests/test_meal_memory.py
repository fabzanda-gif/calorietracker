from datetime import date

from backend.services.meal_memory import MealMemoryService


TARGET = date(2026, 9, 1)  # Tuesday


class FakeMealsRepository:
    def __init__(self, rows):
        self.rows = rows

    def list_date_range(self, user_id, start_date, end_date, columns=None):
        return self.rows


class FakeDailyLogsRepository:
    def __init__(self, rows):
        self.rows = rows

    def list_date_range(self, user_id, start_date, end_date, columns=None):
        return self.rows


def predict(meals, day_logs=None, *, context=None):
    service = MealMemoryService(
        meals_repo=FakeMealsRepository(meals),
        daily_logs_repo=FakeDailyLogsRepository(day_logs or []),
    )
    return service.predict_meal(
        user_id="u1",
        day_date=TARGET,
        meal_type="Colazione",
        day_context=context,
    )


def test_no_history_is_unknown():
    result = predict([])

    assert result["state"] == "unknown"
    assert result["value"] is None


def test_one_matching_meal_is_low_confidence():
    result = predict([
        {
            "date": "2026-08-25",
            "meal_type": "Colazione",
            "name": "Colazione Ufficio",
            "calories": 310,
            "protein": 18,
        }
    ])

    assert result["value"] == "Colazione Ufficio"
    assert result["confidence_level"] == "low"
    assert result["confidence"] == 1.0


def test_three_identical_weekly_meals_are_medium_confidence():
    result = predict([
        {"date": "2026-08-11", "meal_type": "Colazione", "name": "Colazione Ufficio"},
        {"date": "2026-08-18", "meal_type": "Colazione", "name": "Colazione Ufficio"},
        {"date": "2026-08-25", "meal_type": "Colazione", "name": "Colazione Ufficio"},
    ])

    assert result["confidence_level"] == "medium"


def test_four_recent_identical_weekly_meals_are_high_confidence():
    result = predict([
        {"date": "2026-08-04", "meal_type": "Colazione", "name": "Colazione Ufficio"},
        {"date": "2026-08-11", "meal_type": "Colazione", "name": "Colazione Ufficio"},
        {"date": "2026-08-18", "meal_type": "Colazione", "name": "Colazione Ufficio"},
        {"date": "2026-08-25", "meal_type": "Colazione", "name": "Colazione Ufficio"},
    ])

    assert result["confidence_level"] == "high"
    assert result["evidence"]["recent_matches"] == 4


def test_only_same_weekday_is_considered():
    result = predict([
        {"date": "2026-08-24", "meal_type": "Colazione", "name": "Casa"},
        {"date": "2026-08-25", "meal_type": "Colazione", "name": "Ufficio"},
        {"date": "2026-08-26", "meal_type": "Colazione", "name": "Casa"},
    ])

    assert result["value"] == "Ufficio"
    assert result["evidence"]["observations"] == 1


def test_only_requested_meal_type_is_considered():
    result = predict([
        {"date": "2026-08-25", "meal_type": "Pranzo", "name": "Pranzo Ufficio"},
        {"date": "2026-08-25", "meal_type": "Colazione", "name": "Colazione Ufficio"},
    ])

    assert result["value"] == "Colazione Ufficio"
    assert result["evidence"]["observations"] == 1


def test_context_filters_meal_history():
    meals = [
        {"date": "2026-08-04", "meal_type": "Colazione", "name": "Colazione Casa"},
        {"date": "2026-08-11", "meal_type": "Colazione", "name": "Colazione Ufficio"},
        {"date": "2026-08-18", "meal_type": "Colazione", "name": "Colazione Casa"},
        {"date": "2026-08-25", "meal_type": "Colazione", "name": "Colazione Ufficio"},
    ]
    day_logs = [
        {"date": "2026-08-04", "day_type": "Lavoro da casa"},
        {"date": "2026-08-11", "day_type": "Ufficio"},
        {"date": "2026-08-18", "day_type": "Lavoro da casa"},
        {"date": "2026-08-25", "day_type": "Ufficio"},
    ]

    result = predict(
        meals,
        day_logs,
        context="Ufficio",
    )

    assert result["value"] == "Colazione Ufficio"
    assert result["evidence"]["observations"] == 2


def test_context_does_not_fall_back_to_other_contexts():
    meals = [
        {"date": "2026-08-25", "meal_type": "Colazione", "name": "Colazione Casa"},
    ]
    day_logs = [
        {"date": "2026-08-25", "day_type": "Lavoro da casa"},
    ]

    result = predict(
        meals,
        day_logs,
        context="Ufficio",
    )

    assert result["state"] == "unknown"


def test_estimated_calories_and_protein_use_matching_routine_average():
    result = predict([
        {
            "date": "2026-08-11",
            "meal_type": "Colazione",
            "name": "Colazione Ufficio",
            "calories": 300,
            "protein": 16,
        },
        {
            "date": "2026-08-18",
            "meal_type": "Colazione",
            "name": "Altro",
            "calories": 800,
            "protein": 50,
        },
        {
            "date": "2026-08-25",
            "meal_type": "Colazione",
            "name": "Colazione Ufficio",
            "calories": 320,
            "protein": 20,
        },
    ])

    assert result["value"] == "Colazione Ufficio"
    assert result["estimated_calories"] == 310
    assert result["estimated_protein_g"] == 18


def test_missing_nutrition_values_do_not_break_prediction():
    result = predict([
        {
            "date": "2026-08-18",
            "meal_type": "Colazione",
            "name": "Colazione Ufficio",
            "calories": None,
            "protein": None,
        },
        {
            "date": "2026-08-25",
            "meal_type": "Colazione",
            "name": "Colazione Ufficio",
        },
    ])

    assert result["value"] == "Colazione Ufficio"
    assert result["estimated_calories"] is None
    assert result["estimated_protein_g"] is None
