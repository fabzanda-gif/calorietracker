from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from math import isfinite
from typing import Any

from backend.services.profile_goal import ProfileGoalService


class TrainingNutritionContextService:
    """Join existing training and meal facts; never rewrite nutrition targets.

    The protein goal comes solely from the user's existing explicit settings.
    No calories, carbohydrates or fats are added to a daily target in this view.
    """

    @staticmethod
    def _nonnegative(value: Any) -> float:
        try:
            result = float(value or 0)
            return max(0.0, result) if isfinite(result) else 0.0
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def _day(value: Any) -> str | None:
        try:
            return date.fromisoformat(str(value)[:10]).isoformat()
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _is_running(item: dict) -> bool:
        normalized = str(item.get("activity_type") or "").strip().casefold()
        return normalized in {"running", "corsa", "run", "jogging"}

    def build(
        self,
        *,
        start_date: date,
        days: int = 7,
        meals: list[dict],
        planned_running: list[dict],
        planned_strength: list[dict],
        actual_activities: list[dict],
        completed_strength: list[dict],
        metadata: dict,
        weight_kg: float | None = None,
    ) -> dict:
        if not 1 <= days <= 14:
            raise ValueError("Training nutrition covers 1–14 days.")
        profile = ProfileGoalService().build(
            metadata or {},
            current_weight=weight_kg,
            on_date=start_date,
        )
        # Configured goal only; inferred protein recommendations belong
        # to the later adaptive macro phase, not Phase 6.
        protein_goal = profile["protein_target_g"]

        meal_by_day = defaultdict(list)
        for meal in meals:
            key = self._day(meal.get("date"))
            if key:
                meal_by_day[key].append(meal)
        actual_by_day = defaultdict(list)
        completed_planned_ids = set()
        for activity in actual_activities:
            key = self._day(activity.get("date"))
            if key and self._is_running(activity):
                actual_by_day[key].append(activity)
                if activity.get("planned_activity_id"):
                    completed_planned_ids.add(str(activity["planned_activity_id"]))
        complete_by_day = defaultdict(list)
        completed_strength_ids = set()
        for log in completed_strength:
            if log.get("status") != "completed":
                continue
            key = self._day(log.get("performed_date"))
            if key:
                complete_by_day[key].append(log)
                if log.get("strength_workout_id"):
                    completed_strength_ids.add(str(log["strength_workout_id"]))

        planned_run_by_day = defaultdict(list)
        for item in planned_running:
            key = self._day(item.get("scheduled_date"))
            if (
                key and self._is_running(item)
                and item.get("status") == "planned"
                and str(item.get("id")) not in completed_planned_ids
            ):
                planned_run_by_day[key].append(item)
        planned_gym_by_day = defaultdict(list)
        for item in planned_strength:
            key = self._day(item.get("scheduled_date"))
            if (
                key and item.get("status") == "planned"
                and str(item.get("id")) not in completed_strength_ids
            ):
                planned_gym_by_day[key].append(item)

        result = []
        for offset in range(days):
            day = (start_date + timedelta(days=offset)).isoformat()
            logged = meal_by_day[day]
            running_done = actual_by_day[day]
            gym_done = complete_by_day[day]
            runs_scheduled = planned_run_by_day[day]
            gym_scheduled = planned_gym_by_day[day]
            totals = {
                "calories_kcal": round(sum(
                    self._nonnegative(x.get("calories")) for x in logged
                ), 1),
                "protein_g": round(sum(
                    self._nonnegative(x.get("protein")) for x in logged
                ), 1),
                "carbs_g": round(sum(
                    self._nonnegative(x.get("carbs")) for x in logged
                ), 1),
                "fat_g": round(sum(
                    self._nonnegative(x.get("fat")) for x in logged
                ), 1),
            }
            training = {
                "strength_completed": len(gym_done),
                "strength_planned": len(gym_scheduled),
                "running_completed": len(running_done),
                "running_planned": len(runs_scheduled),
            }
            completed = training["strength_completed"] + training["running_completed"]
            planned = training["strength_planned"] + training["running_planned"]
            focus = (
                "training_completed" if completed
                else "training_planned" if planned
                else "no_training_logged"
            )
            if not logged:
                protein_gap = None
            elif protein_goal is not None:
                protein_gap = round(max(0, protein_goal - totals["protein_g"]), 1)
            else:
                protein_gap = None
            result.append({
                "date": day,
                "training": training,
                "training_context": focus,
                "meal_count": len(logged),
                "logged_macros": totals,
                "protein_target_g": protein_goal,
                "protein_remaining_g": protein_gap,
                "protein_target_status": (
                    "not_configured" if protein_goal is None
                    else "not_logged" if not logged
                    else "met" if protein_gap == 0
                    else "below"
                ),
                "note_key": (
                    "training_and_food" if completed and logged
                    else "training_no_meals" if completed
                    else "planned_training" if planned
                    else "rest_or_unknown"
                ),
            })

        return {
            "start_date": start_date.isoformat(),
            "end_date": (start_date + timedelta(days=days-1)).isoformat(),
            "days": result,
            "summary": {
                "training_days": sum(
                    x["training_context"] != "no_training_logged" for x in result
                ),
                "completed_training_days": sum(
                    x["training_context"] == "training_completed" for x in result
                ),
                "days_with_meals": sum(x["meal_count"] > 0 for x in result),
                "days_with_meals_and_training": sum(
                    x["meal_count"] > 0
                    and x["training_context"] != "no_training_logged"
                    for x in result
                ),
                "protein_goal_configured": protein_goal is not None,
            },
            "policy": {
                "read_only": True,
                "calorie_target_changed": False,
                "macro_targets_changed": False,
                "planned_activity_calories_added": False,
                "source": "existing_training_and_meal_logs",
            },
            "disclaimer": (
                "Riepilogo descrittivo basato sui dati registrati. "
                "Una giornata senza allenamenti registrati non significa "
                "riposo certo; una giornata senza pasti registrati non "
                "significa assenza di alimentazione. Gli obiettivi "
                "nutrizionali non vengono modificati."
            ),
        }
