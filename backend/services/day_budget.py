from __future__ import annotations

from datetime import date
from typing import Any, Mapping

from backend.repositories.activities import ActivitiesRepository
from backend.repositories.meals import MealsRepository
from backend.services.budget import BudgetInput, BudgetService
from backend.services.day_metrics import DayMetricsService
from backend.services.profile_goal import ProfileGoalService


class DayBudgetService:
    """
    Assemble SanoSync's profile, actual food and actual activity into one
    deterministic daily budget.

    v0.1 inputs:
    - profile metadata supplied by the caller;
    - current weight supplied by the caller;
    - actual meals from MealsRepository;
    - actual activities from ActivitiesRepository.

    Planned food is intentionally still zero in this version. It will be wired
    in when SanoSync gains persisted meal planning.
    """

    def __init__(
        self,
        meals_repo: MealsRepository,
        activities_repo: ActivitiesRepository,
        *,
        metrics_service: DayMetricsService | None = None,
        profile_goal_service: ProfileGoalService | None = None,
        budget_service: BudgetService | None = None,
    ):
        self.metrics_service = metrics_service or DayMetricsService(
            meals_repo=meals_repo,
            activities_repo=activities_repo,
        )
        self.profile_goal_service = (
            profile_goal_service or ProfileGoalService()
        )
        self.budget_service = budget_service or BudgetService()

    def build(
        self,
        *,
        user_id: str,
        day_date: date,
        metadata: Mapping[str, Any],
        current_weight: float | None,
    ) -> dict:
        metrics = self.metrics_service.for_day(
            user_id=user_id,
            day_date=day_date,
        )

        profile = self.profile_goal_service.build(
            metadata,
            current_weight=current_weight,
            on_date=day_date,
        )

        if not profile["profile_complete_for_budget"]:
            return {
                "date": str(day_date),
                "status": "profile_incomplete",
                "budget": None,
                "actual": metrics,
                "profile": profile,
            }

        logged_meal_types = {
            str(value).strip().casefold()
            for value in metrics.get("logged_meal_types", [])
        }
        dinner_logged = bool(
            logged_meal_types.intersection({"cena", "dinner"})
        )
        dinner_reserve = (
            0.0
            if dinner_logged
            else min(750.0, max(600.0, float(profile["bmr"]) * 0.4))
        )

        budget = self.budget_service.calculate(
            BudgetInput(
                bmr=profile["bmr"],
                activity_kcal=metrics["actual_activity_kcal"],
                baseline_activity_factor=1.2,
                consumed_kcal=metrics["consumed_kcal"],
                planned_kcal=0.0,
                protein_consumed_g=metrics["protein_consumed_g"],
                protein_target_g=profile["protein_target_g"],
                goal_mode=profile["goal_mode"],
                goal_adjustment_kcal=profile["goal_adjustment_kcal"],
                remaining_meal_reserve_kcal=dinner_reserve,
            )
        )

        return {
            "date": str(day_date),
            "status": "ok",
            "budget": budget,
            "actual": metrics,
            "profile": profile,
        }
