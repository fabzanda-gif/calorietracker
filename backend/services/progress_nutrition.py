from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Mapping

from backend.repositories.activities import ActivitiesRepository
from backend.repositories.meals import MealsRepository
from backend.services.budget import BudgetInput, BudgetService
from backend.services.profile_goal import ProfileGoalService


def _number(value: Any) -> float:
    if value in (None, ""):
        return 0.0

    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


class ProgressNutritionService:
    """
    Build historical nutrition metrics for the Progress dashboard.

    Meals and activities are loaded once for the requested range.
    Budget calculation remains delegated to the existing BudgetService.
    """

    def __init__(
        self,
        meals_repo: MealsRepository,
        activities_repo: ActivitiesRepository,
        *,
        profile_goal_service: ProfileGoalService | None = None,
        budget_service: BudgetService | None = None,
    ):
        self.meals_repo = meals_repo
        self.activities_repo = activities_repo
        self.profile_goal_service = (
            profile_goal_service or ProfileGoalService()
        )
        self.budget_service = budget_service or BudgetService()

    def build(
        self,
        *,
        user_id: str,
        start_date: date,
        end_date: date,
        metadata: Mapping[str, Any],
        current_weight: float | None,
    ) -> dict:
        meals = self.meals_repo.list_date_range(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            columns=(
                "id,date,meal_type,calories,protein,carbs,fat"
            ),
        )

        activities = self.activities_repo.list_date_range(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
        )

        meals_by_date: dict[str, list[dict]] = defaultdict(list)
        activities_by_date: dict[str, list[dict]] = defaultdict(list)

        for meal in meals:
            meals_by_date[str(meal.get("date"))].append(meal)

        for activity in activities:
            activities_by_date[str(activity.get("date"))].append(
                activity
            )

        items: list[dict] = []

        current = start_date

        while current <= end_date:
            date_key = str(current)

            day_meals = meals_by_date.get(date_key, [])
            day_activities = activities_by_date.get(date_key, [])

            consumed_kcal = sum(
                _number(item.get("calories"))
                for item in day_meals
            )

            protein_g = sum(
                _number(item.get("protein"))
                for item in day_meals
            )

            carbs_g = sum(
                _number(item.get("carbs"))
                for item in day_meals
            )

            fat_g = sum(
                _number(item.get("fat"))
                for item in day_meals
            )

            activity_kcal = sum(
                _number(item.get("burned_calories"))
                for item in day_activities
            )

            meal_distribution = {
                "breakfast_kcal": 0.0,
                "lunch_kcal": 0.0,
                "dinner_kcal": 0.0,
                "other_kcal": 0.0,
            }

            for meal in day_meals:
                meal_type = str(
                    meal.get("meal_type") or ""
                ).strip().lower()

                calories = _number(
                    meal.get("calories")
                )

                if meal_type in {
                    "colazione",
                    "breakfast",
                }:
                    key = "breakfast_kcal"

                elif meal_type in {
                    "pranzo",
                    "lunch",
                }:
                    key = "lunch_kcal"

                elif meal_type in {
                    "cena",
                    "dinner",
                }:
                    key = "dinner_kcal"

                else:
                    key = "other_kcal"

                meal_distribution[key] += calories

            profile = self.profile_goal_service.build(
                metadata,
                current_weight=current_weight,
                on_date=current,
            )

            budget_kcal = None
            difference_kcal = None

            if profile["profile_complete_for_budget"]:
                budget = self.budget_service.calculate(
                    BudgetInput(
                        bmr=profile["bmr"],
                        activity_kcal=activity_kcal,
                        consumed_kcal=consumed_kcal,
                        planned_kcal=0.0,
                        protein_consumed_g=protein_g,
                        protein_target_g=profile[
                            "protein_target_g"
                        ],
                        goal_mode=profile["goal_mode"],
                        goal_adjustment_kcal=profile[
                            "goal_adjustment_kcal"
                        ],
                    )
                )

                budget_kcal = budget["daily_budget_kcal"]
                difference_kcal = round(
                    consumed_kcal - budget_kcal,
                    2,
                )

            items.append(
                {
                    "date": date_key,
                    "consumed_kcal": round(consumed_kcal, 2),
                    "budget_kcal": budget_kcal,
                    "difference_kcal": difference_kcal,
                    "protein_g": round(protein_g, 2),
                    "carbs_g": round(carbs_g, 2),
                    "fat_g": round(fat_g, 2),
                    "activity_kcal": round(activity_kcal, 2),
                    "breakfast_kcal": round(
                        meal_distribution["breakfast_kcal"],
                        2,
                    ),
                    "lunch_kcal": round(
                        meal_distribution["lunch_kcal"],
                        2,
                    ),
                    "dinner_kcal": round(
                        meal_distribution["dinner_kcal"],
                        2,
                    ),
                    "other_kcal": round(
                        meal_distribution["other_kcal"],
                        2,
                    ),
                    "meal_count": len(day_meals),
                    "activity_count": len(day_activities),
                }
            )

            current += timedelta(days=1)

        logged_items = [
            item
            for item in items
            if item["meal_count"] > 0
        ]

        average_consumed = (
            sum(
                item["consumed_kcal"]
                for item in logged_items
            ) / len(logged_items)
            if logged_items
            else 0.0
        )

        budget_items = [
            item
            for item in logged_items
            if item["budget_kcal"] is not None
        ]

        average_budget = (
            sum(
                float(item["budget_kcal"])
                for item in budget_items
            ) / len(budget_items)
            if budget_items
            else None
        )

        days_within_budget = sum(
            1
            for item in budget_items
            if item["consumed_kcal"]
            <= float(item["budget_kcal"])
        )

        return {
            "start_date": str(start_date),
            "end_date": str(end_date),
            "count": len(items),
            "summary": {
                "logged_days": len(logged_items),
                "average_consumed_kcal": round(
                    average_consumed,
                    2,
                ),
                "average_budget_kcal": (
                    round(average_budget, 2)
                    if average_budget is not None
                    else None
                ),
                "days_within_budget": days_within_budget,
                "days_with_budget": len(budget_items),
            },
            "items": items,
        }
