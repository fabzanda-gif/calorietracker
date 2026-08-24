from __future__ import annotations

from datetime import date, timedelta

from backend.repositories.daily_logs import DailyLogsRepository
from backend.repositories.meals import MealsRepository
from backend.services.meal_memory import MealMemoryService
from backend.services.memory import MemoryService


WEEKDAY_NAMES = {
    0: "Monday",
    1: "Tuesday",
    2: "Wednesday",
    3: "Thursday",
    4: "Friday",
    5: "Saturday",
    6: "Sunday",
}

MEAL_TYPES = (
    "Colazione",
    "Pranzo",
    "Cena",
)

CONFIDENCE_RANK = {
    None: 0,
    "low": 1,
    "medium": 2,
    "high": 3,
}


class LearnedInsightsService:
    """
    Build a structured representation of what SanoSync has learned.

    This service does not invent new inference rules. It orchestrates the
    existing deterministic MemoryService and MealMemoryService.

    v0.1 returns:
    - recurring day context by weekday;
    - recurring activity plan by weekday;
    - recurring meals by weekday and inferred context.

    Only medium/high-confidence patterns enter `learned`.
    Low-confidence observations remain in `learning`.
    """

    def __init__(
        self,
        *,
        daily_logs_repo: DailyLogsRepository,
        meals_repo: MealsRepository,
        memory_service: MemoryService | None = None,
        meal_memory_service: MealMemoryService | None = None,
    ):
        self.daily_logs_repo = daily_logs_repo
        self.meals_repo = meals_repo
        self.memory_service = memory_service or MemoryService(
            daily_logs_repo
        )
        self.meal_memory_service = (
            meal_memory_service
            or MealMemoryService(
                meals_repo=meals_repo,
                daily_logs_repo=daily_logs_repo,
            )
        )

    def build(
        self,
        *,
        user_id: str,
        on_date: date,
    ) -> dict:
        learned = []
        learning = []

        for weekday in range(7):
            target_date = self._next_weekday(
                on_date,
                weekday,
            )

            context = self.memory_service.predict_context(
                user_id=user_id,
                day_date=target_date,
            )

            activity = (
                self.memory_service.predict_activity_plan(
                    user_id=user_id,
                    day_date=target_date,
                )
            )

            self._append_memory_insight(
                learned=learned,
                learning=learning,
                kind="day_context",
                weekday=weekday,
                prediction=context,
            )

            self._append_memory_insight(
                learned=learned,
                learning=learning,
                kind="activity_plan",
                weekday=weekday,
                prediction=activity,
            )

            day_context = (
                context.get("value")
                if context.get("state") == "predicted"
                else None
            )

            for meal_type in MEAL_TYPES:
                meal = self.meal_memory_service.predict_meal(
                    user_id=user_id,
                    day_date=target_date,
                    meal_type=meal_type,
                    day_context=day_context,
                )

                self._append_meal_insight(
                    learned=learned,
                    learning=learning,
                    weekday=weekday,
                    prediction=meal,
                )

        return {
            "generated_for": str(on_date),
            "learned_count": len(learned),
            "learning_count": len(learning),
            "learned": learned,
            "learning": learning,
        }

    def _append_memory_insight(
        self,
        *,
        learned: list[dict],
        learning: list[dict],
        kind: str,
        weekday: int,
        prediction: dict,
    ) -> None:
        if prediction.get("state") != "predicted":
            return

        insight = {
            "kind": kind,
            "weekday": weekday,
            "weekday_name": WEEKDAY_NAMES[weekday],
            "value": prediction.get("value"),
            "confidence": prediction.get("confidence"),
            "confidence_level": prediction.get(
                "confidence_level"
            ),
            "evidence": prediction.get("evidence"),
        }

        self._bucket(
            insight=insight,
            learned=learned,
            learning=learning,
        )

    def _append_meal_insight(
        self,
        *,
        learned: list[dict],
        learning: list[dict],
        weekday: int,
        prediction: dict,
    ) -> None:
        if prediction.get("state") != "predicted":
            return

        insight = {
            "kind": "meal",
            "weekday": weekday,
            "weekday_name": WEEKDAY_NAMES[weekday],
            "meal_type": prediction.get("meal_type"),
            "day_context": prediction.get("day_context"),
            "value": prediction.get("value"),
            "confidence": prediction.get("confidence"),
            "confidence_level": prediction.get(
                "confidence_level"
            ),
            "estimated_calories": prediction.get(
                "estimated_calories"
            ),
            "estimated_protein_g": prediction.get(
                "estimated_protein_g"
            ),
            "evidence": prediction.get("evidence"),
        }

        self._bucket(
            insight=insight,
            learned=learned,
            learning=learning,
        )

    @staticmethod
    def _bucket(
        *,
        insight: dict,
        learned: list[dict],
        learning: list[dict],
    ) -> None:
        rank = CONFIDENCE_RANK.get(
            insight.get("confidence_level"),
            0,
        )

        if rank >= CONFIDENCE_RANK["medium"]:
            learned.append(insight)
        elif rank == CONFIDENCE_RANK["low"]:
            learning.append(insight)

    @staticmethod
    def _next_weekday(
        on_date: date,
        weekday: int,
    ) -> date:
        delta = (weekday - on_date.weekday()) % 7
        if delta == 0:
            delta = 7
        return on_date + timedelta(days=delta)
