from datetime import date

from backend.services.future_training_nutrition import (
    FutureTrainingNutritionService,
)


def test_strength_workout_tomorrow_creates_moderate_context():
    result = FutureTrainingNutritionService().build(
        day_date=date(2026, 9, 5),
        planned_activities=[],
        strength_workouts=[
            {
                "id": "strength-1",
                "strength_plan_id": "plan-1",
                "scheduled_date": "2026-09-06",
                "status": "planned",
                "title": "Upper A",
                "focus": "upper",
                "training_week": 2,
                "estimated_duration_minutes": 50,
            }
        ],
    )

    assert result["level"] == "moderate"
    assert result["carb_focus"] is True

    primary = result["primary_session"]

    assert primary["id"] == "strength-1"
    assert primary["training_type"] == "strength"
    assert primary["focus"] == "upper"
    assert primary["duration_minutes"] == 50


def test_long_strength_workout_creates_high_context():
    result = FutureTrainingNutritionService().build(
        day_date=date(2026, 9, 5),
        planned_activities=[],
        strength_workouts=[
            {
                "id": "strength-2",
                "strength_plan_id": "plan-1",
                "scheduled_date": "2026-09-06",
                "status": "planned",
                "title": "Full Body",
                "focus": "full_body",
                "estimated_duration_minutes": 80,
            }
        ],
    )

    assert result["level"] == "high"
    assert result["carb_focus"] is True


def test_strength_workout_not_tomorrow_is_ignored():
    result = FutureTrainingNutritionService().build(
        day_date=date(2026, 9, 5),
        planned_activities=[],
        strength_workouts=[
            {
                "id": "strength-3",
                "strength_plan_id": "plan-1",
                "scheduled_date": "2026-09-07",
                "status": "planned",
                "estimated_duration_minutes": 60,
            }
        ],
    )

    assert result["level"] == "none"
    assert result["carb_focus"] is False


def test_running_and_strength_choose_higher_load():
    result = FutureTrainingNutritionService().build(
        day_date=date(2026, 9, 5),
        planned_activities=[
            {
                "id": "run-1",
                "training_plan_id": "run-plan",
                "scheduled_date": "2026-09-06",
                "status": "planned",
                "title": "Facile",
                "session_kind": "easy",
                "duration_minutes": 30,
            }
        ],
        strength_workouts=[
            {
                "id": "strength-4",
                "strength_plan_id": "strength-plan",
                "scheduled_date": "2026-09-06",
                "status": "planned",
                "title": "Lower A",
                "focus": "lower",
                "estimated_duration_minutes": 55,
            }
        ],
    )

    assert result["level"] == "moderate"
    assert (
        result["primary_session"]["id"]
        == "strength-4"
    )
