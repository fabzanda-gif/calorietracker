from datetime import date

from backend.services.meal_candidates import (
    MealCandidateService,
)


DAY = date(2026, 9, 1)


def test_builds_candidates_from_all_sources():
    result = MealCandidateService().build(
        day_date=DAY,
        meal_type="Pranzo",
        meal_prep_items=[
            {
                "id": "b1",
                "name": "Chili",
                "status": "available",
                "portions_remaining": 2,
                "expires_at": "2026-09-02",
                "calories_per_portion": 500,
                "protein_per_portion": 35,
                "carbs_per_portion": 45,
                "fat_per_portion": 15,
            }
        ],
        routine_prediction={
            "state": "predicted",
            "value": "Pranzo Ufficio",
            "confidence_level": "high",
            "estimated_calories": 650,
            "estimated_protein_g": 35,
            "estimated_carbs_g": 70,
            "estimated_fat_g": 18,
        },
        recipes=[
            {
                "id": "r1",
                "name": "Chicken rice",
                "meal_type": "Pranzo",
                "calories": 600,
                "protein": 45,
                "carbs": 65,
                "fat": 15,
            }
        ],
    )

    assert {x["source"] for x in result} == {
        "meal_prep",
        "routine",
        "recipe",
    }


def test_expired_meal_prep_is_not_candidate():
    result = MealCandidateService().build(
        day_date=DAY,
        meal_type="Pranzo",
        meal_prep_items=[
            {
                "id": "b1",
                "name": "Old Chili",
                "status": "available",
                "portions_remaining": 2,
                "expires_at": "2026-08-31",
                "calories_per_portion": 500,
            }
        ],
        routine_prediction=None,
        recipes=[],
    )

    assert result == []


def test_recipe_with_other_meal_type_is_filtered():
    result = MealCandidateService().build(
        day_date=DAY,
        meal_type="Pranzo",
        meal_prep_items=[],
        routine_prediction=None,
        recipes=[
            {
                "id": "r1",
                "name": "Breakfast oats",
                "meal_type": "Colazione",
                "calories": 400,
            },
            {
                "id": "r2",
                "name": "Lunch bowl",
                "meal_type": "Pranzo",
                "calories": 550,
            },
        ],
    )

    assert len(result) == 1
    assert result[0]["name"] == "Lunch bowl"


def test_missing_taste_defaults_to_five():
    result = MealCandidateService().build(
        day_date=DAY,
        meal_type="Cena",
        meal_prep_items=[],
        routine_prediction=None,
        recipes=[
            {
                "id": "r1",
                "name": "Dinner",
                "meal_type": "Cena",
                "calories": 500,
            }
        ],
    )

    assert result[0]["taste_score"] == 5.0


def test_meal_prep_near_expiry_gets_high_waste_risk():
    result = MealCandidateService().build(
        day_date=DAY,
        meal_type="Pranzo",
        meal_prep_items=[
            {
                "id": "b1",
                "name": "Chili",
                "status": "available",
                "portions_remaining": 2,
                "expires_at": "2026-09-02",
                "calories_per_portion": 500,
            }
        ],
        routine_prediction=None,
        recipes=[],
    )

    assert result[0]["waste_risk"] == "high"


def test_small_historical_entries_are_not_meal_candidates():
    result = MealCandidateService().build(
        day_date=DAY,
        meal_type="Cena",
        meal_prep_items=[],
        routine_prediction=None,
        recipes=[],
        historical_meals=[
            {
                "meal_type": "Cena",
                "name": "Mela Verde",
                "calories": 52,
                "protein": 0,
            },
            {
                "meal_type": "Cena",
                "name": "Appel Partjes",
                "calories": 55,
                "protein": 0,
            },
            {
                "meal_type": "Cena",
                "name": "Chicken Rice Bowl",
                "calories": 520,
                "protein": 42,
            },
        ],
    )

    assert len(result) == 1
    assert result[0]["name"] == "Chicken Rice Bowl"
    assert result[0]["source"] == "meal_history"
    assert result[0]["calories"] == 520


def test_structured_historical_lunch_is_candidate():
    result = MealCandidateService().build(
        day_date=DAY,
        meal_type="Pranzo",
        meal_prep_items=[],
        routine_prediction=None,
        recipes=[],
        historical_meals=[
            {
                "meal_type": "Pranzo",
                "name": "Pasta al pomodoro",
                "calories": 450,
                "protein": 16,
            },
        ],
    )

    assert len(result) == 1
    assert result[0]["name"] == "Pasta al pomodoro"
