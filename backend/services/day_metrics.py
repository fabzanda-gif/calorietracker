from __future__ import annotations

from datetime import date
from typing import Any

from backend.repositories.activities import ActivitiesRepository
from backend.repositories.meals import MealsRepository


def _safe_number(value: Any) -> float:
    if value in (None, ""):
        return 0.0

    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


class DayMetricsService:
    """
    Aggregate actual nutrition and activity for one SanoSync day.

    This is an adapter between the existing repositories and the new
    Budget Engine. It deliberately contains no profile / goal logic.

    Actual food:
      meals.calories -> consumed_kcal
      meals.protein  -> protein_consumed_g

    Actual activity:
      activities.burned_calories -> actual_activity_kcal

    Missing numeric values are treated as zero within an existing row.
    An empty list simply means that no matching records have been logged.
    """

    def __init__(
        self,
        meals_repo: MealsRepository,
        activities_repo: ActivitiesRepository,
    ):
        self.meals_repo = meals_repo
        self.activities_repo = activities_repo

    def for_day(
        self,
        user_id: str,
        day_date: date,
    ) -> dict:
        meals = self.meals_repo.list_for_date_compatible(
            user_id=user_id,
            log_date=day_date,
        )

        activities = self.activities_repo.list_for_date(
            user_id=user_id,
            log_date=day_date,
        )

        consumed_kcal = sum(
            _safe_number(item.get("calories"))
            for item in meals
        )

        protein_consumed_g = sum(
            _safe_number(item.get("protein"))
            for item in meals
        )

        actual_activity_kcal = sum(
            _safe_number(item.get("burned_calories"))
            for item in activities
        )

        return {
            "date": str(day_date),
            "consumed_kcal": round(consumed_kcal, 2),
            "protein_consumed_g": round(protein_consumed_g, 2),
            "actual_activity_kcal": round(actual_activity_kcal, 2),
            "meal_count": len(meals),
            "activity_count": len(activities),
        }
