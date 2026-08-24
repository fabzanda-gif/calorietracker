from datetime import date

from backend.services.meal_decision import MealDecisionService


DAY = date(2026, 9, 1)


def routine():
    return {
        "meal_type": "Pranzo",
        "value": "Pranzo Ufficio",
        "state": "predicted",
        "source": "routine",
        "estimated_calories": 650,
        "estimated_protein_g": 35,
        "estimated_carbs_g": 70,
        "estimated_fat_g": 18,
    }


def batch(
    batch_id,
    name,
    kcal,
    expires_at=None,
    remaining=2,
    status="available",
):
    return {
        "id": batch_id,
        "recipe_id": f"recipe-{batch_id}",
        "name": name,
        "status": status,
        "portions_remaining": remaining,
        "expires_at": expires_at,
        "calories_per_portion": kcal,
        "protein_per_portion": 35,
        "carbs_per_portion": 50,
        "fat_per_portion": 15,
    }


def test_inventory_is_preferred_over_routine_when_compatible():
    result = MealDecisionService().decide(
        day_date=DAY,
        meal_type="Pranzo",
        available_inventory=[
            batch("b1", "Chili", 600, "2026-09-03")
        ],
        available_kcal=800,
        routine_prediction=routine(),
    )
    assert result["recommended"]["source"] == "meal_prep"
    assert result["recommended"]["name"] == "Chili"
    assert result["prediction"]["value"] == "Pranzo Ufficio"


def test_inventory_over_budget_falls_back_to_routine():
    result = MealDecisionService().decide(
        day_date=DAY,
        meal_type="Pranzo",
        available_inventory=[batch("b1", "Large Chili", 900)],
        available_kcal=700,
        routine_prediction=routine(),
    )
    assert result["recommended"]["source"] == "routine"
    assert result["inventory_candidates"] == []


def test_earliest_expiry_wins_and_is_high_priority():
    result = MealDecisionService().decide(
        day_date=DAY,
        meal_type="Pranzo",
        available_inventory=[
            batch("later", "Later", 500, "2026-09-05"),
            batch("soon", "Soon", 550, "2026-09-02"),
        ],
        available_kcal=800,
        routine_prediction=routine(),
    )
    assert result["recommended"]["batch_id"] == "soon"
    assert result["recommended"]["priority"] == "high"


def test_finished_and_empty_batches_are_ignored():
    result = MealDecisionService().decide(
        day_date=DAY,
        meal_type="Pranzo",
        available_inventory=[
            batch("finished", "Finished", 500, status="finished"),
            batch("empty", "Empty", 500, remaining=0),
        ],
        available_kcal=800,
        routine_prediction=routine(),
    )
    assert result["inventory_candidates"] == []
    assert result["recommended"]["source"] == "routine"


def test_unknown_budget_keeps_inventory_eligible():
    result = MealDecisionService().decide(
        day_date=DAY,
        meal_type="Pranzo",
        available_inventory=[batch("b1", "Chili", 600)],
        available_kcal=None,
        routine_prediction=None,
    )
    assert result["recommended"]["source"] == "meal_prep"


def test_no_inventory_and_no_prediction_returns_none():
    result = MealDecisionService().decide(
        day_date=DAY,
        meal_type="Pranzo",
        available_inventory=[],
        available_kcal=800,
        routine_prediction={
            "meal_type": "Pranzo",
            "value": None,
            "state": "unknown",
        },
    )
    assert result["recommended"] is None
