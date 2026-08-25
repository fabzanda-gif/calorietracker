from datetime import date

from backend.services.progress_nutrition import (
    ProgressNutritionService,
)


class MealsRepo:
    def list_date_range(
        self,
        user_id,
        start_date,
        end_date,
        columns=None,
    ):
        return [
            {
                "date": "2026-08-24",
                "meal_type": "Pranzo",
                "calories": 600,
                "protein": 40,
                "carbs": 70,
                "fat": 18,
            },
            {
                "date": "2026-08-24",
                "meal_type": "Cena",
                "calories": 400,
                "protein": 25,
                "carbs": 30,
                "fat": 12,
            },
            {
                "date": "2026-08-25",
                "meal_type": "Colazione",
                "calories": 700,
                "protein": 45,
                "carbs": 80,
                "fat": 18,
            },
            {
                "date": "2026-08-25",
                "meal_type": "Spuntino",
                "calories": 100,
                "protein": 5,
                "carbs": 10,
                "fat": 2,
            },
        ]


class ActivitiesRepo:
    def list_date_range(
        self,
        user_id,
        start_date,
        end_date,
    ):
        return [
            {
                "date": "2026-08-24",
                "burned_calories": 300,
            }
        ]


class ProfileService:
    def build(
        self,
        metadata,
        current_weight=None,
        on_date=None,
    ):
        return {
            "profile_complete_for_budget": True,
            "bmr": 1800,
            "protein_target_g": 150,
            "goal_mode": "loss",
            "goal_adjustment_kcal": 300,
        }


def test_builds_daily_progress():
    service = ProgressNutritionService(
        MealsRepo(),
        ActivitiesRepo(),
        profile_goal_service=ProfileService(),
    )

    result = service.build(
        user_id="user-1",
        start_date=date(2026, 8, 24),
        end_date=date(2026, 8, 25),
        metadata={},
        current_weight=80,
    )

    assert result["count"] == 2

    first = result["items"][0]

    assert first["consumed_kcal"] == 1000
    assert first["protein_g"] == 65
    assert first["carbs_g"] == 100
    assert first["fat_g"] == 30
    assert first["activity_kcal"] == 300

    assert first["breakfast_kcal"] == 0
    assert first["lunch_kcal"] == 600
    assert first["dinner_kcal"] == 400
    assert first["other_kcal"] == 0

    # 1800 BMR + 300 activity - 300 loss adjustment
    assert first["budget_kcal"] == 1800
    assert first["difference_kcal"] == -800

    second = result["items"][1]

    # 1800 BMR - 300 loss adjustment
    assert second["budget_kcal"] == 1500
    assert second["consumed_kcal"] == 800

    assert second["breakfast_kcal"] == 700
    assert second["lunch_kcal"] == 0
    assert second["dinner_kcal"] == 0
    assert second["other_kcal"] == 100

    assert result["summary"]["logged_days"] == 2
    assert result["summary"]["average_consumed_kcal"] == 900
    assert result["summary"]["days_within_budget"] == 2
