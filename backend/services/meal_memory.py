from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
from typing import Any

from backend.repositories.daily_logs import DailyLogsRepository
from backend.repositories.meals import MealsRepository
from backend.services.meal_routine_events import MealRoutineEventService


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

        events = MealRoutineEventService().build(
            meals=meals,
            meal_type=meal_type,
        )

        candidates: list[dict[str, Any]] = []

        for event in events:
            raw_date = event.get("date")

            try:
                meal_date = date.fromisoformat(
                    str(raw_date)
                )
            except ValueError:
                continue

            event_context = context_by_date.get(
                str(raw_date)
            )

            if day_context is None:
                if (
                    meal_date.weekday()
                    != day_date.weekday()
                ):
                    continue
            elif not self._contexts_match(
                day_context,
                event_context,
            ):
                continue

            candidates.append(
                {
                    **event,
                    "date": meal_date,
                    "name": str(
                        event.get("name") or ""
                    ).strip(),
                }
            )

        candidates.sort(
            key=lambda item: item["date"]
        )

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

        estimated_quantity = self._typical_quantity(
            matching_items
        )

        structured_items = self._structured_items_for_quantity(
            matching_items,
            estimated_quantity,
        )

        structured_nutrition = (
            estimated_quantity is not None
            and self._has_base_nutrition(
                structured_items
            )
        )

        if structured_nutrition:
            estimated_calories = self._scaled_base_average(
                structured_items,
                "base_calories",
                estimated_quantity,
            )
            estimated_protein = self._scaled_base_average(
                structured_items,
                "base_protein",
                estimated_quantity,
            )
            estimated_carbs = self._scaled_base_average(
                structured_items,
                "base_carbs",
                estimated_quantity,
            )
            estimated_fat = self._scaled_base_average(
                structured_items,
                "base_fat",
                estimated_quantity,
            )
        else:
            estimated_calories = self._average_field(
                matching_items,
                "calories",
            )
            estimated_protein = self._average_field(
                matching_items,
                "protein",
            )
            estimated_carbs = self._average_field(
                matching_items,
                "carbs",
            )
            estimated_fat = self._average_field(
                matching_items,
                "fat",
            )

        return {
            "meal_type": meal_type,
            "value": winner,
            "state": "predicted",
            "source": "routine",
            "confidence": round(probability, 4),
            "confidence_level": confidence_level,
            "day_context": day_context,
            "estimated_quantity": estimated_quantity,
            "estimated_calories": estimated_calories,
            "estimated_protein_g": estimated_protein,
            "estimated_carbs_g": estimated_carbs,
            "estimated_fat_g": estimated_fat,
            "components": (
                matching_items[-1].get(
                    "components",
                    [],
                )
                if matching_items
                else []
            ),
            "evidence": {
                "observations": len(names),
                "matches": matches,
                "recent_observations": len(recent_names),
                "recent_matches": recent_names.count(winner),
            },
        }

    @classmethod
    def _contexts_match(
        cls,
        expected: object,
        observed: object,
    ) -> bool:
        expected_value = cls._context_family(
            expected
        )
        observed_value = cls._context_family(
            observed
        )

        return (
            bool(expected_value)
            and expected_value == observed_value
        )

    @staticmethod
    def _context_family(
        value: object,
    ) -> str:
        normalized = " ".join(
            str(value or "")
            .strip()
            .casefold()
            .replace("_", " ")
            .split()
        )

        home_contexts = {
            "home",
            "free",
            "libero",
            "giornata libera",
            "lavoro da casa",
            "work from home",
            "wfh",
        }

        if normalized in home_contexts:
            return "home"

        return normalized


    @staticmethod
    def _meal_identity(meal: dict[str, Any]) -> str:
        """
        Return the stable identity used for routine learning.

        Structured meals use base_name so display/portion labels
        do not create separate routines. Legacy meals fall back
        to their historical name.
        """
        base_name = meal.get("base_name")

        if (
            base_name is not None
            and str(base_name).strip()
        ):
            return str(base_name).strip()

        return str(
            meal.get("name") or ""
        ).strip()

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _typical_quantity(
        cls,
        items: list[dict[str, Any]],
    ) -> float | None:
        quantities = [
            item.get("quantity")
            for item in items
            if item.get("quantity") is not None
            and float(item.get("quantity")) > 0
        ]

        if not quantities:
            return None

        counts = Counter(quantities)
        max_count = max(counts.values())

        tied = {
            quantity
            for quantity, count in counts.items()
            if count == max_count
        }

        for item in reversed(items):
            quantity = item.get("quantity")
            if quantity in tied:
                return float(quantity)

        return None

    @classmethod
    def _structured_items_for_quantity(
        cls,
        items: list[dict[str, Any]],
        quantity: float | None,
    ) -> list[dict[str, Any]]:
        if quantity is None:
            return []

        matching_quantity_items = [
            item
            for item in items
            if item.get("quantity") == quantity
        ]

        if not matching_quantity_items:
            return []

        # If we have explicit unit semantics, preserve them.
        # Portion-based and gram-based observations must not be mixed.
        explicit_units = [
            item.get("is_per_100g")
            for item in matching_quantity_items
            if item.get("is_per_100g") is not None
        ]

        if not explicit_units:
            return matching_quantity_items

        preferred_unit = explicit_units[-1]

        return [
            item
            for item in matching_quantity_items
            if item.get("is_per_100g") == preferred_unit
        ]

    @classmethod
    def _has_base_nutrition(
        cls,
        items: list[dict[str, Any]],
    ) -> bool:
        return any(
            item.get("base_calories") is not None
            for item in items
        )

    @classmethod
    def _scaled_base_average(
        cls,
        items: list[dict[str, Any]],
        field_name: str,
        quantity: float,
    ) -> float | None:
        values: list[float] = []

        for item in items:
            base = cls._safe_float(
                item.get(field_name)
            )

            if base is None:
                continue

            raw_is_per_100g = item.get("is_per_100g")
            is_per_100g = (
                raw_is_per_100g is True
                or str(raw_is_per_100g).strip().lower()
                in {"true", "1", "yes"}
            )

            if is_per_100g:
                scaled = base * quantity / 100.0
            else:
                scaled = base * quantity

            values.append(scaled)

        if not values:
            return None

        return round(
            sum(values) / len(values),
            2,
        )

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
            "estimated_quantity": None,
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
