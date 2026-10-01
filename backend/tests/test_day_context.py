from datetime import date, datetime

from backend.services.day_context import DayContextService


def test_day_context_unifies_routine_food_energy_and_training():
    service = DayContextService()

    context = service.build(
        day_date=date(2026, 9, 24),
        now=datetime(2026, 9, 24, 16, 30),
        day={
            "context": {
                "value": "Ufficio",
                "state": "predicted",
                "source": "memory",
                "confidence": 0.86,
            },
            "activity_plan": {
                "value": "Attiva",
                "state": "confirmed",
                "source": "user",
                "confidence": 1.0,
            },
        },
        budget_result={
            "status": "ok",
            "actual": {
                "consumed_kcal": 1120,
                "protein_consumed_g": 61,
                "actual_activity_kcal": 0,
            },
            "budget": {
                "consumed_kcal": 1120,
                "maintenance_kcal": 2518,
                "available_kcal": 900,
                "protein_remaining_g": 42,
            },
            "energy_baseline": {
                "activity_budget_source": "expected_plus_planned",
            },
        },
        meals=[
            {
                "meal_type": "Colazione",
                "calories": 400,
            },
            {
                "meal_type": "Pranzo",
                "calories": 720,
            },
        ],
        planned_activities=[
            {
                "id": "run-1",
                "scheduled_date": "2026-09-24",
                "scheduled_time": "18:30",
                "title": "Corsa facile 6 km",
                "activity_type": "Corsa",
                "status": "planned",
            },
        ],
        actual_activities=[],
        training_nutrition={
            "phase": "pre_training",
            "carbs_target_g": {
                "min": 78,
                "max": 155,
            },
        },
        weight={
            "weight": 77.4,
            "date": "2026-09-24",
        },
    )

    assert context["moment"] == "afternoon"
    assert context["routine"]["day_type"] == {
        "value": "Ufficio",
        "state": "predicted",
        "source": "memory",
        "confidence": 0.86,
    }
    assert context["food"]["next_meal_type"] == "Snack"
    assert context["food"]["consumed_kcal"] == 1120
    assert context["energy"]["maintenance_kcal"] == 2518
    assert context["energy"]["current_balance_kcal"] == -1398
    assert context["training"]["planned_count"] == 1
    assert context["training"]["nutrition"]["phase"] == "pre_training"
    assert context["weight"]["kg"] == 77.4

    assert "training_today" in context["signals"]
    assert "pre_training" in context["signals"]
    assert "protein_below_target" in context["signals"]
    assert "currently_below_maintenance" in context["signals"]
    assert "day_in_progress" in context["signals"]


def test_day_context_recognizes_completed_planned_activity_and_recovery():
    service = DayContextService()

    context = service.build(
        day_date=date(2026, 9, 24),
        now=datetime(2026, 9, 24, 20, 15),
        day={},
        budget_result={
            "status": "ok",
            "actual": {
                "consumed_kcal": 2200,
                "protein_consumed_g": 125,
                "actual_activity_kcal": 540,
            },
            "budget": {
                "maintenance_kcal": 2600,
                "available_kcal": 100,
                "protein_remaining_g": 5,
            },
        },
        meals=[
            {"meal_type": "Colazione"},
            {"meal_type": "Pranzo"},
            {"meal_type": "Snack"},
            {"meal_type": "Cena"},
        ],
        planned_activities=[
            {
                "id": "run-1",
                "scheduled_date": "2026-09-24",
                "title": "Corsa",
                "status": "planned",
            },
        ],
        actual_activities=[
            {
                "id": "activity-1",
                "date": "2026-09-24",
                "activity_name": "Corsa",
                "burned_calories": 540,
                "planned_activity_id": "run-1",
            },
        ],
        training_nutrition={
            "phase": "recovery",
            "protein_target_g": {
                "min": 20,
                "max": 30,
            },
        },
    )

    assert context["moment"] == "evening"
    assert context["food"]["next_meal_type"] is None
    assert context["training"]["actual_count"] == 1
    assert context["training"]["completed_planned"][0]["id"] == "run-1"

    assert "activity_recorded" in context["signals"]
    assert "recovery" in context["signals"]
    assert "all_meal_slots_logged" in context["signals"]
    assert "low_calorie_margin" in context["signals"]
