from __future__ import annotations

from datetime import date
from typing import Any

from backend.services.legacy_meal_events import (
    LegacyMealEventService,
)


class MealCandidateService:
    """
    Assemble a source-agnostic candidate pool for the ranking engine.

    Sources:
    - meal prep inventory;
    - learned routine prediction;
    - available recipes;
    - historical logged meals;
    - known takeaway/delivery candidates.
    """

    def build(
        self,
        *,
        day_date: date,
        meal_type: str,
        meal_prep_items: list[dict],
        routine_prediction: dict | None,
        recipes: list[dict],
        order_candidates: list[dict] | None = None,
        historical_meals: list[dict] | None = None,
    ) -> list[dict]:
        candidates: list[dict] = []

        for batch in meal_prep_items:
            if (
                batch.get("status") != "available"
                or self._number(batch.get("portions_remaining")) <= 0
            ):
                continue

            expires_at = self._parse_date(batch.get("expires_at"))

            if expires_at is not None and expires_at < day_date:
                continue

            candidates.append(
                {
                    "id": f"meal_prep:{batch.get('id')}",
                    "source": "meal_prep",
                    "source_id": batch.get("id"),
                    "name": batch.get("name"),
                    "meal_type": meal_type,
                    "calories": self._number(
                        batch.get("calories_per_portion")
                    ),
                    "protein_g": self._number(
                        batch.get("protein_per_portion")
                    ),
                    "carbs_g": self._number(
                        batch.get("carbs_per_portion")
                    ),
                    "fat_g": self._number(
                        batch.get("fat_per_portion")
                    ),
                    "taste_score": self._taste(
                        batch.get("taste_score")
                    ),
                    "waste_risk": self._waste_risk(
                        day_date=day_date,
                        expires_at=expires_at,
                    ),
                    "portions_remaining": int(
                        self._number(
                            batch.get("portions_remaining")
                        )
                    ),
                    "expires_at": (
                        str(expires_at)
                        if expires_at is not None
                        else None
                    ),
                }
            )

        prediction = routine_prediction or {}
        if (
            prediction.get("state") == "predicted"
            and prediction.get("value")
        ):
            candidates.append(
                {
                    "id": (
                        "routine:"
                        f"{meal_type}:"
                        f"{prediction.get('value')}"
                    ),
                    "source": "routine",
                    "source_id": None,
                    "name": prediction.get("value"),
                    "meal_type": meal_type,
                    "calories": self._number(
                        prediction.get("estimated_calories")
                    ),
                    "protein_g": self._number(
                        prediction.get("estimated_protein_g")
                    ),
                    "carbs_g": self._number(
                        prediction.get("estimated_carbs_g")
                    ),
                    "fat_g": self._number(
                        prediction.get("estimated_fat_g")
                    ),
                    "taste_score": self._taste(
                        prediction.get("taste_score")
                    ),
                    "waste_risk": None,
                    "confidence_level": prediction.get(
                        "confidence_level"
                    ),
                }
            )

        for recipe in recipes:
            recipe_meal_type = recipe.get("meal_type")
            if (
                recipe_meal_type
                and recipe_meal_type != meal_type
            ):
                continue

            candidates.append(
                {
                    "id": f"recipe:{recipe.get('id')}",
                    "source": "recipe",
                    "source_id": recipe.get("id"),
                    "name": recipe.get("name"),
                    "meal_type": meal_type,
                    "calories": self._number(
                        recipe.get("calories")
                    ),
                    "protein_g": self._number(
                        recipe.get("protein")
                    ),
                    "carbs_g": self._number(
                        recipe.get("carbs")
                    ),
                    "fat_g": self._number(
                        recipe.get("fat")
                    ),
                    "taste_score": self._taste(
                        recipe.get("taste_score")
                    ),
                    "waste_risk": None,
                }
            )

        historical_events = (
            LegacyMealEventService().build(
                meals=historical_meals or [],
                meal_type=meal_type,
            )
        )

        historical_by_name: dict[
            str,
            list[dict],
        ] = {}

        for event in historical_events:
            name = str(
                event.get("name") or ""
            ).strip()

            if not name:
                continue

            normalized_name = " ".join(
                name.lower().split()
            )

            historical_by_name.setdefault(
                normalized_name,
                [],
            ).append(event)

        for normalized_name, events in (
            historical_by_name.items()
        ):
            latest = events[0]

            name = str(
                latest.get("name") or ""
            ).strip()

            candidates.append(
                {
                    "id": (
                        "meal_history:"
                        f"{normalized_name}"
                    ),
                    "source": "meal_history",
                    "source_id": None,
                    "name": name,
                    "meal_type": meal_type,
                    "calories": self._average(
                        events,
                        "calories",
                    ),
                    "protein_g": self._average(
                        events,
                        "protein",
                    ),
                    "carbs_g": self._average(
                        events,
                        "carbs",
                    ),
                    "fat_g": self._average(
                        events,
                        "fat",
                    ),
                    "taste_score": 5.0,
                    "waste_risk": None,
                    "occurrences": len(events),
                    "components": latest.get(
                        "components",
                        [],
                    ),
                }
            )

        for order in order_candidates or []:
            if order.get("meal_type") != meal_type:
                continue
            candidates.append(dict(order))

        return self._deduplicate(candidates)

    @staticmethod
    def _deduplicate(
        candidates: list[dict],
    ) -> list[dict]:
        seen = set()
        result = []

        for item in candidates:
            key = (
                str(item.get("source")),
                str(item.get("source_id")),
                str(item.get("name")),
            )
            if key in seen:
                continue

            seen.add(key)
            result.append(item)

        return result

    @classmethod
    def _average(
        cls,
        items: list[dict],
        field_name: str,
    ) -> float:
        values = []

        for item in items:
            value = item.get(field_name)

            if value in (None, ""):
                continue

            try:
                values.append(
                    max(0.0, float(value))
                )
            except (TypeError, ValueError):
                continue

        if not values:
            return 0.0

        return round(
            sum(values) / len(values),
            2,
        )

    @staticmethod
    def _number(value: Any) -> float:
        try:
            return max(0.0, float(value or 0))
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _taste(value: Any) -> float:
        try:
            score = float(value)
        except (TypeError, ValueError):
            return 5.0

        return min(10.0, max(0.0, score))

    @staticmethod
    def _parse_date(value: Any) -> date | None:
        if not value:
            return None

        try:
            return date.fromisoformat(str(value))
        except ValueError:
            return None

    @staticmethod
    def _waste_risk(
        *,
        day_date: date,
        expires_at: date | None,
    ) -> str:
        if expires_at is None:
            return "low"

        days_left = (expires_at - day_date).days

        if days_left <= 1:
            return "high"
        if days_left <= 3:
            return "medium"
        return "low"
