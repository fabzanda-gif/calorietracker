from __future__ import annotations

from datetime import date, datetime, time
from typing import Any


MEAL_ORDER = (
    "Colazione",
    "Pranzo",
    "Snack",
    "Cena",
)


class DayContextService:
    """
    Build one deterministic snapshot of the current day.

    This service intentionally does not read repositories itself. Callers
    provide already-fetched day, budget, meal and training data so the same
    context can later be reused by Home, briefings and recommendation engines
    without duplicating interpretation logic.
    """

    def build(
        self,
        *,
        day_date: date,
        day: dict[str, Any] | None,
        budget_result: dict[str, Any] | None,
        meals: list[dict[str, Any]] | None,
        planned_activities: list[dict[str, Any]] | None,
        actual_activities: list[dict[str, Any]] | None,
        training_nutrition: dict[str, Any] | None,
        weight: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        day = day or {}
        budget_result = budget_result or {}
        meals = meals or []
        planned_activities = planned_activities or []
        actual_activities = actual_activities or []
        training_nutrition = training_nutrition or {}
        now = now or datetime.now()

        budget = budget_result.get("budget") or {}
        actual = budget_result.get("actual") or {}

        current_planned = [
            item
            for item in planned_activities
            if (
                str(item.get("scheduled_date") or "") == str(day_date)
                and str(item.get("status") or "planned").lower() == "planned"
            )
        ]

        linked_completed_ids = {
            str(item.get("planned_activity_id"))
            for item in actual_activities
            if item.get("planned_activity_id") is not None
        }

        completed_planned = [
            item
            for item in planned_activities
            if str(item.get("id")) in linked_completed_ids
        ]

        meal_types = [
            str(item.get("meal_type") or "").strip()
            for item in meals
            if str(item.get("meal_type") or "").strip()
        ]

        next_meal = next(
            (
                meal_type
                for meal_type in MEAL_ORDER
                if meal_type not in meal_types
            ),
            None,
        )

        consumed_kcal = self._number(
            budget.get("consumed_kcal"),
            actual.get("consumed_kcal"),
        )
        maintenance_kcal = self._number(
            budget.get("maintenance_kcal")
        )
        available_kcal = self._optional_number(
            budget.get("available_kcal")
        )
        protein_remaining_g = self._optional_number(
            budget.get("protein_remaining_g")
        )

        burned_kcal = self._number(
            actual.get("actual_activity_kcal"),
            budget_result.get("energy_baseline", {}).get(
                "actual_activity_kcal"
            ),
        )

        balance_kcal = (
            consumed_kcal - maintenance_kcal
            if maintenance_kcal > 0
            else None
        )

        training_context = (
            training_nutrition.get("context")
            if isinstance(training_nutrition, dict)
            and "context" in training_nutrition
            else training_nutrition
        ) or {}

        signals: list[str] = []

        if current_planned:
            signals.append("training_today")

        if completed_planned or actual_activities:
            signals.append("activity_recorded")

        phase = str(
            training_context.get("phase") or "normal"
        )

        if phase == "pre_training":
            signals.append("pre_training")
        elif phase == "pre_race":
            signals.append("pre_race")
        elif phase == "recovery":
            signals.append("recovery")
        elif phase == "tomorrow_prep":
            signals.append("training_tomorrow")

        if (
            protein_remaining_g is not None
            and protein_remaining_g >= 20
        ):
            signals.append("protein_below_target")

        if (
            available_kcal is not None
            and available_kcal <= 250
        ):
            signals.append("low_calorie_margin")

        if balance_kcal is not None:
            if balance_kcal < -100:
                signals.append("currently_below_maintenance")
            elif balance_kcal > 100:
                signals.append("currently_above_maintenance")
            else:
                signals.append("currently_near_maintenance")

        if not meals:
            signals.append("no_meals_logged")
        elif next_meal is not None:
            signals.append("day_in_progress")
        else:
            signals.append("all_meal_slots_logged")

        return {
            "date": str(day_date),
            "generated_at": now.isoformat(),
            "moment": self._moment(now.time()),
            "routine": {
                "day_type": self._prediction(day.get("context")),
                "activity_plan": self._prediction(
                    day.get("activity_plan")
                ),
            },
            "food": {
                "logged_meal_count": len(meals),
                "logged_meal_types": meal_types,
                "next_meal_type": next_meal,
                "consumed_kcal": round(consumed_kcal),
                "protein_consumed_g": self._optional_number(
                    actual.get("protein_consumed_g")
                ),
                "protein_remaining_g": protein_remaining_g,
            },
            "energy": {
                "maintenance_kcal": (
                    round(maintenance_kcal)
                    if maintenance_kcal > 0
                    else None
                ),
                "available_kcal": (
                    round(available_kcal)
                    if available_kcal is not None
                    else None
                ),
                "burned_activity_kcal": round(burned_kcal),
                "current_balance_kcal": (
                    round(balance_kcal)
                    if balance_kcal is not None
                    else None
                ),
                "budget_status": budget_result.get("status"),
                "budget_source": (
                    budget_result.get("energy_baseline", {})
                    .get("activity_budget_source")
                ),
            },
            "training": {
                "planned_today": current_planned,
                "planned_count": len(current_planned),
                "completed_planned": completed_planned,
                "actual_today": actual_activities,
                "actual_count": len(actual_activities),
                "nutrition": training_context,
            },
            "weight": {
                "kg": self._optional_number(
                    (weight or {}).get("weight")
                ),
                "date": (weight or {}).get("date"),
            },
            "signals": signals,
        }

    @staticmethod
    def _prediction(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return {
                "value": value.get("value"),
                "state": value.get("state"),
                "source": value.get("source"),
                "confidence": value.get("confidence"),
            }

        return {
            "value": value,
            "state": None,
            "source": None,
            "confidence": None,
        }

    @staticmethod
    def _moment(value: time) -> str:
        if value < time(12, 0):
            return "morning"
        if value < time(18, 0):
            return "afternoon"
        return "evening"

    @staticmethod
    def _optional_number(value: Any) -> float | None:
        if value is None:
            return None

        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _number(
        cls,
        *values: Any,
    ) -> float:
        for value in values:
            parsed = cls._optional_number(value)
            if parsed is not None:
                return parsed
        return 0.0
