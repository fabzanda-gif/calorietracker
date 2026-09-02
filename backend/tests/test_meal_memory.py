from datetime import date

from backend.services.meal_memory import MealMemoryService


TARGET = date(2026, 9, 1)


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
    assert result["estimated_carbs_g"] is None
    assert result["estimated_fat_g"] is None


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
    result = predict(
        [
            {
                "date": "2026-08-25",
                "meal_type": "Colazione",
                "name": "Colazione Casa",
            }
        ],
        [
            {
                "date": "2026-08-25",
                "day_type": "Lavoro da casa",
            }
        ],
        context="Ufficio",
    )

    assert result["state"] == "unknown"


def test_estimated_nutrition_uses_matching_routine_average():
    result = predict([
        {
            "date": "2026-08-11",
            "meal_type": "Colazione",
            "name": "Colazione Ufficio",
            "calories": 300,
            "protein": 16,
            "carbs": 30,
            "fat": 8,
        },
        {
            "date": "2026-08-18",
            "meal_type": "Colazione",
            "name": "Altro",
            "calories": 800,
            "protein": 50,
            "carbs": 100,
            "fat": 30,
        },
        {
            "date": "2026-08-25",
            "meal_type": "Colazione",
            "name": "Colazione Ufficio",
            "calories": 320,
            "protein": 20,
            "carbs": 40,
            "fat": 12,
        },
    ])

    assert result["value"] == "Colazione Ufficio"
    assert result["estimated_calories"] == 310
    assert result["estimated_protein_g"] == 18
    assert result["estimated_carbs_g"] == 35
    assert result["estimated_fat_g"] == 10


def test_missing_nutrition_values_do_not_break_prediction():
    result = predict([
        {
            "date": "2026-08-18",
            "meal_type": "Colazione",
            "name": "Colazione Ufficio",
            "calories": None,
            "protein": None,
            "carbs": None,
            "fat": None,
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
    assert result["estimated_carbs_g"] is None
    assert result["estimated_fat_g"] is None


def test_base_name_is_used_as_routine_identity_when_available():
    result = predict([
        {
            "date": "2026-08-11",
            "meal_type": "Colazione",
            "name": "Fit Lasagna (1 porz.)",
            "base_name": "Fit Lasagna",
            "quantity": 1,
            "calories": 348,
            "protein": 30,
        },
        {
            "date": "2026-08-18",
            "meal_type": "Colazione",
            "name": "Fit Lasagna (2 porz.)",
            "base_name": "Fit Lasagna",
            "quantity": 2,
            "calories": 696,
            "protein": 60,
        },
        {
            "date": "2026-08-25",
            "meal_type": "Colazione",
            "name": "Fit Lasagna",
            "base_name": "Fit Lasagna",
            "quantity": 2,
            "calories": 696,
            "protein": 60,
        },
    ])

    assert result["value"] == "Fit Lasagna"
    assert result["confidence_level"] == "medium"
    assert result["evidence"]["matches"] == 3


def test_legacy_meals_still_use_name_when_base_name_is_missing():
    result = predict([
        {
            "date": "2026-08-11",
            "meal_type": "Colazione",
            "name": "Colazione Ufficio",
            "calories": 300,
        },
        {
            "date": "2026-08-18",
            "meal_type": "Colazione",
            "name": "Colazione Ufficio",
            "calories": 320,
        },
        {
            "date": "2026-08-25",
            "meal_type": "Colazione",
            "name": "Colazione Ufficio",
            "calories": 310,
        },
    ])

    assert result["value"] == "Colazione Ufficio"
    assert result["estimated_calories"] == 310


def test_base_name_is_used_as_routine_identity_when_available():
    result = predict([
        {
            "date": "2026-08-11",
            "meal_type": "Colazione",
            "name": "Fit Lasagna (1 porz.)",
            "base_name": "Fit Lasagna",
            "quantity": 1,
            "calories": 348,
            "protein": 30,
        },
        {
            "date": "2026-08-18",
            "meal_type": "Colazione",
            "name": "Fit Lasagna (2 porz.)",
            "base_name": "Fit Lasagna",
            "quantity": 2,
            "calories": 696,
            "protein": 60,
        },
        {
            "date": "2026-08-25",
            "meal_type": "Colazione",
            "name": "Fit Lasagna",
            "base_name": "Fit Lasagna",
            "quantity": 2,
            "calories": 696,
            "protein": 60,
        },
    ])

    assert result["value"] == "Fit Lasagna"
    assert result["confidence_level"] == "medium"
    assert result["evidence"]["matches"] == 3


def test_legacy_meals_still_use_name_when_base_name_is_missing():
    result = predict([
        {
            "date": "2026-08-11",
            "meal_type": "Colazione",
            "name": "Colazione Ufficio",
            "calories": 300,
        },
        {
            "date": "2026-08-18",
            "meal_type": "Colazione",
            "name": "Colazione Ufficio",
            "calories": 320,
        },
        {
            "date": "2026-08-25",
            "meal_type": "Colazione",
            "name": "Colazione Ufficio",
            "calories": 310,
        },
    ])

    assert result["value"] == "Colazione Ufficio"
    assert result["estimated_calories"] == 310


def test_structured_routine_learns_typical_quantity():
    result = predict([
        {
            "date": "2026-08-11",
            "meal_type": "Colazione",
            "name": "Fit Lasagna",
            "base_name": "Fit Lasagna",
            "quantity": 1,
            "base_calories": 348,
            "base_protein": 30,
            "calories": 348,
            "protein": 30,
        },
        {
            "date": "2026-08-18",
            "meal_type": "Colazione",
            "name": "Fit Lasagna",
            "base_name": "Fit Lasagna",
            "quantity": 2,
            "base_calories": 348,
            "base_protein": 30,
            "calories": 696,
            "protein": 60,
        },
        {
            "date": "2026-08-25",
            "meal_type": "Colazione",
            "name": "Fit Lasagna",
            "base_name": "Fit Lasagna",
            "quantity": 2,
            "base_calories": 348,
            "base_protein": 30,
            "calories": 696,
            "protein": 60,
        },
    ])

    assert result["value"] == "Fit Lasagna"
    assert result["estimated_quantity"] == 2
    assert result["estimated_calories"] == 696
    assert result["estimated_protein_g"] == 60


def test_structured_routine_uses_recent_quantity_on_tie():
    result = predict([
        {
            "date": "2026-08-04",
            "meal_type": "Colazione",
            "name": "Fit Lasagna",
            "base_name": "Fit Lasagna",
            "quantity": 1,
            "base_calories": 348,
            "calories": 348,
        },
        {
            "date": "2026-08-11",
            "meal_type": "Colazione",
            "name": "Fit Lasagna",
            "base_name": "Fit Lasagna",
            "quantity": 2,
            "base_calories": 348,
            "calories": 696,
        },
    ])

    assert result["estimated_quantity"] == 2
    assert result["estimated_calories"] == 696


def test_legacy_routine_keeps_average_nutrition_behavior():
    result = predict([
        {
            "date": "2026-08-11",
            "meal_type": "Colazione",
            "name": "Legacy Meal",
            "calories": 300,
        },
        {
            "date": "2026-08-18",
            "meal_type": "Colazione",
            "name": "Legacy Meal",
            "calories": 320,
        },
    ])

    assert result["estimated_quantity"] is None
    assert result["estimated_calories"] == 310


def test_portion_routine_ignores_gram_based_observation_for_nutrition():
    result = predict([
        {
            "date": "2026-08-04",
            "meal_type": "Colazione",
            "name": "Fit Lasagna (745g)",
            "base_name": "Fit Lasagna",
            "quantity": 745,
            "is_per_100g": True,
            "base_calories": 206.85,
            "base_protein": 11.52,
            "calories": 1541,
            "protein": 86,
        },
        {
            "date": "2026-08-11",
            "meal_type": "Colazione",
            "name": "Fit Lasagna (2 porz.)",
            "base_name": "Fit Lasagna",
            "quantity": 2,
            "is_per_100g": False,
            "base_calories": 347.75,
            "base_protein": 20.45,
            "calories": 696,
            "protein": 41,
        },
        {
            "date": "2026-08-18",
            "meal_type": "Colazione",
            "name": "Fit Lasagna (2 porz.)",
            "base_name": "Fit Lasagna",
            "quantity": 2,
            "is_per_100g": False,
            "base_calories": 347.75,
            "base_protein": 20.45,
            "calories": 696,
            "protein": 41,
        },
        {
            "date": "2026-08-25",
            "meal_type": "Colazione",
            "name": "Fit Lasagna (2 porz.)",
            "base_name": "Fit Lasagna",
            "quantity": 2,
            "is_per_100g": False,
            "base_calories": 347.75,
            "base_protein": 20.45,
            "calories": 696,
            "protein": 41,
        },
    ])

    assert result["value"] == "Fit Lasagna"
    assert result["estimated_quantity"] == 2
    assert result["estimated_calories"] == 695.5
    assert result["estimated_protein_g"] == 40.9

def test_combination_rows_become_one_meal_routine():
    meals = []

    for day_date in (
        "2026-08-28",
        "2026-08-29",
        "2026-08-30",
        "2026-08-31",
    ):
        meals.extend([
            {
                "date": day_date,
                "meal_type": "Colazione",
                "name": "Latte macchiato d'avena",
                "calories": 120,
                "protein": 2,
                "carbs": 18,
                "fat": 4,
            },
            {
                "date": day_date,
                "meal_type": "Colazione",
                "name": "Cheesecake",
                "calories": 283,
                "protein": 15,
                "carbs": 25,
                "fat": 12,
            },
        ])

    logs = [
        {
            "date": day_date,
            "day_type": (
                "home"
                if index % 2 == 0
                else "free"
            ),
        }
        for index, day_date in enumerate((
            "2026-08-28",
            "2026-08-29",
            "2026-08-30",
            "2026-08-31",
        ))
    ]

    result = predict(
        meals,
        logs,
        context="home",
    )

    assert result["value"] == (
        "Cheesecake + "
        "Latte macchiato d'avena"
    )
    assert result["confidence_level"] == "high"
    assert result["estimated_calories"] == 403
    assert len(result["components"]) == 2


def test_home_and_free_share_breakfast_context():
    result = predict(
        [
            {
                "date": "2026-08-30",
                "meal_type": "Colazione",
                "name": "Latte d'avena",
                "calories": 120,
            },
            {
                "date": "2026-08-30",
                "meal_type": "Colazione",
                "name": "Cheesecake",
                "calories": 280,
            },
        ],
        [
            {
                "date": "2026-08-30",
                "day_type": "free",
            }
        ],
        context="home",
    )

    assert result["state"] == "predicted"
    assert "Latte d'avena" in result["value"]
    assert "Cheesecake" in result["value"]
