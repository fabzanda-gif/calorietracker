from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
from typing import Any

from backend.repositories.daily_logs import DailyLogsRepository
from backend.repositories.meals import MealsRepository


LOW = "low"
MEDIUM = "medium"
HIGH = "high"


class MealMemoryService:
    """
    Deterministic meal-routine memory.

    v0.2 predicts a recurring meal for a given meal_type using:
    - same weekday;
    - optional day context;
    - recent history;
    - the same 3/4-week confidence philosophy used by Day Memory.

    Nutrition estimates are averages across matching historical occurrences.
    The service predicts only; it never writes meal data.
    """

    def __init__(
        self,
        meals_repo: MealsRepository,
        daily_logs_repo: DailyLogsRepository,
        *,
        lookback_weeks: int = 12,
        recent_window: int = 4,
    ):
        self.meals_repo = meals_repo
        self.daily_logs_repo = daily_logs_repo
        self.lookback_weeks = lookback_weeks
        self.recent_window = recent_window

    def predict_meal(
        self,
        *,
        user_id: str,
        day_date: date,
        meal_type: str,
        day_context: str | None = None,
    ) -> dict:
        start_date = day_date - timedelta(weeks=self.lookback_weeks)
        end_date = day_date - timedelta(days=1)

        meals = self.meals_repo.list_date_range(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
        )

        day_logs = self.daily_logs_repo.list_date_range(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
        )

        context_by_date = {
            str(row.get("date")): row.get("day_type")
            for row in day_logs
            if row.get("date")
        }

        candidates: list[dict[str, Any]] = []

        for meal in meals:
            raw_date = meal.get("date")
            name = meal.get("name")

            if not raw_date or not name:
                continue

            if meal.get("meal_type") != meal_type:
                continue

            try:
                meal_date = date.fromisoformat(str(raw_date))
            except ValueError:
                continue

            if meal_date.weekday() != day_date.weekday():
                continue

            if (
                day_context is not None
                and context_by_date.get(str(raw_date)) != day_context
            ):
                continue

            candidates.append(
                {
                    "date": meal_date,
                    "name": str(name),
                    "calories": self._safe_float(meal.get("calories")),
                    "protein": self._safe_float(meal.get("protein")),
                    "carbs": self._safe_float(meal.get("carbs")),
                    "fat": self._safe_float(meal.get("fat")),
                }
            )

        candidates.sort(key=lambda item: item["date"])

        if not candidates:
            return self._unknown(
                meal_type=meal_type,
                day_context=day_context,
            )

        names = [item["name"] for item in candidates]
        recent_names = names[-self.recent_window :]

        if (
            len(recent_names) >= self.recent_window
            and len(set(recent_names)) == 1
        ):
            winner = recent_names[-1]
            confidence_level = HIGH
        else:
            counts = Counter(names)
            winner, matches = counts.most_common(1)[0]
            probability = matches / len(names)

            if len(names) >= 3 and matches >= 3 and probability >= 0.75:
                confidence_level = MEDIUM
            else:
                confidence_level = LOW

        matches = names.count(winner)
        probability = matches / len(names)
        matching_items = [
            item for item in candidates
            if item["name"] == winner
        ]

        return {
            "meal_type": meal_type,
            "value": winner,
            "state": "predicted",
            "source": "routine",
            "confidence": round(probability, 4),
            "confidence_level": confidence_level,
            "day_context": day_context,
            "estimated_calories": self._average_field(
                matching_items, "calories"
            ),
            "estimated_protein_g": self._average_field(
                matching_items, "protein"
            ),
            "estimated_carbs_g": self._average_field(
                matching_items, "carbs"
            ),
            "estimated_fat_g": self._average_field(
                matching_items, "fat"
            ),
            "evidence": {
                "observations": len(names),
                "matches": matches,
                "recent_observations": len(recent_names),
                "recent_matches": recent_names.count(winner),
            },
        }

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _average_field(
        cls,
        items: list[dict[str, Any]],
        field_name: str,
    ) -> float | None:
        values = [
            item[field_name]
            for item in items
            if item.get(field_name) is not None
        ]
        if not values:
            return None
        return round(sum(values) / len(values), 2)

    @staticmethod
    def _unknown(
        *,
        meal_type: str,
        day_context: str | None,
    ) -> dict:
        return {
            "meal_type": meal_type,
            "value": None,
            "state": "unknown",
            "source": None,
            "confidence": None,
            "confidence_level": None,
            "day_context": day_context,
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
