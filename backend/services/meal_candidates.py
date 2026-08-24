from __future__ import annotations

from datetime import date
from typing import Any


class MealCandidateService:
    """
    Assemble a source-agnostic candidate pool for the ranking engine.

    Sources in v0.1:
    - meal prep inventory;
    - learned routine prediction;
    - available recipes.

    The service does not rank. It only normalizes candidates.
    """

    def build(
        self,
        *,
        day_date: date,
        meal_type: str,
        meal_prep_items: list[dict],
        routine_prediction: dict | None,
        recipes: list[dict],
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
