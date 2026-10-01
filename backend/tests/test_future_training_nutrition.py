from datetime import date

from backend.services.decision_ranking import (
    DecisionRankingService,
)
from backend.services.future_training_nutrition import (
    FutureTrainingNutritionService,
)


def test_long_run_tomorrow_creates_high_carb_focus():
    result = FutureTrainingNutritionService().build(
        day_date=date(2026, 9, 5),
        planned_activities=[
            {
                "id": "run-1",
                "training_plan_id": "plan-1",
                "scheduled_date": "2026-09-06",
                "status": "planned",
                "title": "Lungo 14 km",
                "session_kind": "long",
                "distance_meters": 14000,
                "duration_minutes": 90,
            }
        ],
    )

    assert result["level"] == "high"
    assert result["carb_focus"] is True
    assert result["primary_session"]["id"] == "run-1"


def test_short_easy_run_does_not_force_carb_focus():
    result = FutureTrainingNutritionService().build(
        day_date=date(2026, 9, 5),
        planned_activities=[
            {
                "training_plan_id": "plan-1",
                "scheduled_date": "2026-09-06",
                "status": "planned",
                "title": "Facile 5 km",
                "session_kind": "easy",
                "distance_meters": 5000,
                "duration_minutes": 32,
            }
        ],
    )

    assert result["level"] == "low"
    assert result["carb_focus"] is False


def test_manual_activity_is_ignored():
    result = FutureTrainingNutritionService().build(
        day_date=date(2026, 9, 5),
        planned_activities=[
            {
                "training_plan_id": None,
                "scheduled_date": "2026-09-06",
                "status": "planned",
                "title": "Passeggiata",
                "duration_minutes": 120,
            }
        ],
    )

    assert result["level"] == "none"
    assert result["carb_focus"] is False


def test_high_load_rewards_more_carbs():
    context = {
        "level": "high",
        "carb_focus": True,
    }

    low = (
        DecisionRankingService
        ._future_training_bonus(
            20,
            lens="balanced",
            context=context,
        )
    )

    high = (
        DecisionRankingService
        ._future_training_bonus(
            90,
            lens="balanced",
            context=context,
        )
    )

    assert high > low


def test_without_training_context_bonus_is_zero():
    bonus = (
        DecisionRankingService
        ._future_training_bonus(
            100,
            lens="balanced",
            context=None,
        )
    )

    assert bonus == 0.0
