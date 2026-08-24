from datetime import date

from backend.services.meal_decision import MealDecisionService


DAY = date(2026, 9, 5)


def item(
    batch_id,
    expires_at,
    *,
    kcal=500,
):
    return {
        "id": batch_id,
        "recipe_id": f"r-{batch_id}",
        "name": f"Meal {batch_id}",
        "status": "available",
        "portions_remaining": 2,
        "expires_at": expires_at,
        "calories_per_portion": kcal,
        "protein_per_portion": 30,
        "carbs_per_portion": 50,
        "fat_per_portion": 15,
    }


def test_expired_inventory_is_never_recommended():
    result = MealDecisionService().decide(
        day_date=DAY,
        meal_type="Pranzo",
        available_inventory=[
            item("expired", "2026-09-04"),
        ],
        available_kcal=800,
        routine_prediction=None,
    )

    assert result["recommended"] is None
    assert result["inventory_candidates"] == []
    assert result["inventory_warnings"][0]["type"] == "expired_inventory"


def test_expiring_today_is_high_waste_risk():
    result = MealDecisionService().decide(
        day_date=DAY,
        meal_type="Pranzo",
        available_inventory=[
            item("today", "2026-09-05"),
        ],
        available_kcal=800,
        routine_prediction=None,
    )

    recommended = result["recommended"]
    assert recommended["waste_risk"] == "high"
    assert recommended["priority"] == "high"
    assert recommended["reason"] == "use_soon"


def test_expiring_tomorrow_is_high_waste_risk():
    result = MealDecisionService().decide(
        day_date=DAY,
        meal_type="Pranzo",
        available_inventory=[
            item("tomorrow", "2026-09-06"),
        ],
        available_kcal=800,
        routine_prediction=None,
    )

    assert result["recommended"]["waste_risk"] == "high"


def test_expiring_in_three_days_is_medium_risk():
    result = MealDecisionService().decide(
        day_date=DAY,
        meal_type="Pranzo",
        available_inventory=[
            item("later", "2026-09-08"),
        ],
        available_kcal=800,
        routine_prediction=None,
    )

    assert result["recommended"]["waste_risk"] == "medium"


def test_no_expiry_date_is_low_waste_risk():
    result = MealDecisionService().decide(
        day_date=DAY,
        meal_type="Pranzo",
        available_inventory=[
            item("unknown", None),
        ],
        available_kcal=800,
        routine_prediction=None,
    )

    assert result["recommended"]["waste_risk"] == "low"
