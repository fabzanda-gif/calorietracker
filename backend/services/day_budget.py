from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from typing import Any, Mapping

from backend.repositories.activities import ActivitiesRepository
from backend.repositories.daily_logs import DailyLogsRepository
from backend.repositories.meals import MealsRepository
from backend.services.budget import BudgetInput, BudgetService
from backend.services.day_metrics import DayMetricsService
from backend.services.day_history import DayHistoryService
from backend.services.memory import MemoryService
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
        daily_logs_repo: DailyLogsRepository,
        *,
        metrics_service: DayMetricsService | None = None,
        history_service: DayHistoryService | None = None,
        profile_goal_service: ProfileGoalService | None = None,
        budget_service: BudgetService | None = None,
    ):
        self.metrics_service = metrics_service or DayMetricsService(
            meals_repo=meals_repo,
            activities_repo=activities_repo,
        )
        self.history_service = history_service or DayHistoryService(
            daily_logs_repo=daily_logs_repo,
            activities_repo=activities_repo,
        )
        self.daily_logs_repo = daily_logs_repo
        self.memory_service = MemoryService(daily_logs_repo)
        self.profile_goal_service = (
            profile_goal_service or ProfileGoalService()
        )
        self.budget_service = budget_service or BudgetService()

    @staticmethod
    def _activity_buffer_kcal(activity_level: Any) -> float:
        normalized = " ".join(
            str(activity_level or "")
            .strip()
            .casefold()
            .replace("_", " ")
            .split()
        )

        if normalized in {
            "riposo",
            "rest",
            "poco attiva",
            "poco attivo",
            "low",
        }:
            return 0.0

        if normalized in {
            "moderata",
            "moderato",
            "moderatamente attiva",
            "moderatamente attivo",
            "moderate",
        }:
            return 150.0

        if normalized in {
            "attiva",
            "attivo",
            "molto attiva",
            "molto attivo",
            "very active",
        }:
            return 300.0

        return 0.0

    def _activity_level(
        self,
        *,
        user_id: str,
        day_date: date,
    ) -> str | None:
        row = self.daily_logs_repo.get_for_date_compatible(
            user_id=user_id,
            log_date=day_date,
        ) or {}

        explicit = row.get("activity_plan")

        if explicit is not None and str(explicit).strip():
            return str(explicit).strip()

        prediction = self.memory_service.predict_activity_plan(
            user_id=user_id,
            day_date=day_date,
        )

        if prediction.get("state") == "predicted":
            value = prediction.get("value")
            if value is not None and str(value).strip():
                return str(value).strip()

        return None

    def build(
        self,
        *,
        user_id: str,
        day_date: date,
        metadata: Mapping[str, Any],
        current_weight: float | None,
    ) -> dict:
        # These reads are independent and I/O-bound.
        # Execute them concurrently so Supabase round-trips overlap.
        with ThreadPoolExecutor(max_workers=3) as executor:
            metrics_future = executor.submit(
                self.metrics_service.for_day,
                user_id=user_id,
                day_date=day_date,
            )

            activity_history_future = executor.submit(
                self.history_service.average_activity_kcal,
                user_id=user_id,
                end_date=day_date - timedelta(days=1),
                lookback_days=7,
            )

            activity_level_future = executor.submit(
                self._activity_level,
                user_id=user_id,
                day_date=day_date,
            )

            metrics = metrics_future.result()
            activity_history = activity_history_future.result()
            activity_level = activity_level_future.result()

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

        average_activity_kcal = float(
            activity_history["average_burned_calories"]
        )

        activity_buffer_kcal = self._activity_buffer_kcal(
            activity_level
        )

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
                activity_kcal=(
                    average_activity_kcal
                    + activity_buffer_kcal
                ),
                baseline_activity_factor=1.0,
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
            "energy_baseline": {
                "average_activity_kcal_7d": average_activity_kcal,
                "activity_level": activity_level,
                "activity_buffer_kcal": activity_buffer_kcal,
                "activity_kcal_for_budget": (
                    average_activity_kcal
                    + activity_buffer_kcal
                ),
                "baseline_activity_factor": 1.0,
                "history": activity_history,
            },
        }
