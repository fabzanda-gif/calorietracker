from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from backend.repositories.daily_logs import DailyLogsRepository
from backend.repositories.weekly_schedule import WeeklyScheduleRepository
from backend.services.memory import MemoryService


MEAL_SLOTS = {
    "breakfast": "Colazione",
    "lunch": "Pranzo",
    "dinner": "Cena",
}


def _known_value(value: Any) -> dict:
    if value is None or value == "":
        return {
            "value": None,
            "state": "unknown",
            "source": None,
            "confidence": None,
        }

    return {
        "value": value,
        "state": "confirmed",
        "source": "user",
        "confidence": 1.0,
    }


def _unknown_context() -> dict:
    return {
        "value": None,
        "state": "unknown",
        "source": None,
    }


def _unknown_meal(meal_type: str) -> dict:
    return {
        "meal_type": meal_type,
        "value": None,
        "state": "unknown",
        "source": None,
        "confidence": None,
        "confidence_level": None,
        "day_context": None,
        "estimated_calories": None,
        "estimated_protein_g": None,
        "estimated_carbs_g": None,
        "estimated_fat_g": None,
        "evidence": {
            "observations": 0,
            "matches": 0,
            "recent_observations": 0,
            "recent_matches": 0,
        },
    }


class DayService:
    """
    Product-level representation of a SanoSync day.

    Explicit planning remains authoritative. Meal predictions are optional and
    remain predictions until the user explicitly confirms them.
    """

    def __init__(
        self,
        daily_logs_repo: DailyLogsRepository,
        memory_service: MemoryService | None = None,
        meal_memory_service=None,
        weekly_schedule_repo: WeeklyScheduleRepository | None = None,
    ):
        self.daily_logs_repo = daily_logs_repo
        self.memory_service = memory_service or MemoryService(daily_logs_repo)
        self.meal_memory_service = meal_memory_service
        self.weekly_schedule_repo = weekly_schedule_repo

    def _weekly_schedule_context(
        self,
        user_id: str,
        day_date: date,
    ) -> dict:
        """
        Use the user's weekly schedule as the primary
        prediction source for the day context.
        """
        if self.weekly_schedule_repo is None:
            return _unknown_context()

        week_start = day_date - timedelta(
            days=day_date.weekday()
        )

        rows = self.weekly_schedule_repo.list_for_week(
            user_id=user_id,
            week_start=week_start,
        )

        # weekly_schedule persists ISO-style values:
        # Monday = 1 ... Sunday = 7
        target_day = day_date.weekday() + 1

        for row in rows:
            if row.get("day_of_week") != target_day:
                continue

            value = row.get("context")

            if value is None:
                return _unknown_context()

            value = str(value).strip()

            if not value:
                return _unknown_context()

            return {
                "value": value,
                "state": "predicted",
                "source": "weekly_schedule",
            }

        return _unknown_context()

    def build_day(self, user_id: str, day_date: date) -> dict:
        row = self.daily_logs_repo.get_for_date_compatible(
            user_id=user_id,
            log_date=day_date,
        )
        row = row or {}

        # Explicit daily choice remains authoritative.
        context = _known_value(row.get("day_type"))

        # If the user has not explicitly chosen today's context,
        # use the weekly schedule from the profile as the primary
        # prediction source. The weekly schedule already distinguishes
        # home / office / free.
        if context["state"] == "unknown":
            context = self._weekly_schedule_context(
                user_id=user_id,
                day_date=day_date,
            )

        # Fall back to historical memory only when the weekly schedule
        # cannot provide a usable value.
        if context["state"] == "unknown":
            prediction = self.memory_service.predict_context(
                user_id=user_id,
                day_date=day_date,
            )
            if prediction["state"] == "predicted":
                context = prediction

        activity_plan = _known_value(row.get("activity_plan"))
        if activity_plan["state"] == "unknown":
            prediction = self.memory_service.predict_activity_plan(
                user_id=user_id,
                day_date=day_date,
            )
            if prediction["state"] == "predicted":
                activity_plan = prediction

        meals = {
            slot: _unknown_meal(meal_type)
            for slot, meal_type in MEAL_SLOTS.items()
        }

        if self.meal_memory_service is not None:
            for slot, meal_type in MEAL_SLOTS.items():
                meals[slot] = self.meal_memory_service.predict_meal(
                    user_id=user_id,
                    day_date=day_date,
                    meal_type=meal_type,
                    day_context=context.get("value"),
                )

        return {
            "date": str(day_date),
            "context": context,
            "activity_plan": activity_plan,
            "meals": meals,
            "actual": {
                "weight": row.get("weight"),
                "steps": row.get("steps"),
            },
        }
