from __future__ import annotations

from datetime import date
from typing import Any


class MealDecisionService:
    """
    Deterministic meal decision layer.

    v0.2 adds food-waste intelligence:
    - expired inventory is never recommended;
    - stale "available" expired batches are surfaced as cleanup warnings;
    - use-soon batches receive explicit waste-risk levels;
    - nearest valid expiry still wins among budget-compatible inventory.
    """

    def decide(
        self,
        *,
        day_date: date,
        meal_type: str,
        available_inventory: list[dict],
        available_kcal: float | None,
        routine_prediction: dict | None,
    ) -> dict:
        candidates = []
        warnings = []

        for batch in available_inventory:
            remaining = self._number(batch.get("portions_remaining"))
            if remaining <= 0 or batch.get("status") != "available":
                continue

            expires_at = self._parse_date(batch.get("expires_at"))

            if (
                expires_at is not None
                and expires_at < day_date
            ):
                warnings.append(
                    {
                        "batch_id": batch.get("id"),
                        "name": batch.get("name"),
                        "type": "expired_inventory",
                        "message": "Inventory is past its expiry date",
                    }
                )
                continue

            calories = self._number(
                batch.get("calories_per_portion")
            )

            if (
                available_kcal is not None
                and calories > float(available_kcal)
            ):
                continue

            waste_risk = self._waste_risk(
                day_date=day_date,
                expires_at=expires_at,
            )

            candidates.append(
                {
                    "source": "meal_prep",
                    "batch_id": batch.get("id"),
                    "recipe_id": batch.get("recipe_id"),
                    "name": batch.get("name"),
                    "meal_type": meal_type,
                    "calories": calories,
                    "protein_g": self._number(
                        batch.get("protein_per_portion")
                    ),
                    "carbs_g": self._number(
                        batch.get("carbs_per_portion")
                    ),
                    "fat_g": self._number(
                        batch.get("fat_per_portion")
                    ),
                    "portions_remaining": int(remaining),
                    "expires_at": (
                        str(expires_at)
                        if expires_at is not None
                        else None
                    ),
                    "priority": self._priority(
                        day_date,
                        expires_at,
                    ),
                    "waste_risk": waste_risk,
                    "reason": (
                        "use_soon"
                        if waste_risk == "high"
                        else "available_inventory"
                    ),
                    "_sort_key": self._sort_key(
                        day_date,
                        expires_at,
                    ),
                }
            )

        candidates.sort(key=lambda item: item["_sort_key"])

        recommendation = None
        if candidates:
            recommendation = self._public_candidate(
                candidates[0]
            )

        prediction = routine_prediction or {
            "meal_type": meal_type,
            "value": None,
            "state": "unknown",
        }

        if (
            recommendation is None
            and prediction.get("state") == "predicted"
        ):
            recommendation = {
                "source": "routine",
                "batch_id": None,
                "recipe_id": None,
                "name": prediction.get("value"),
                "meal_type": meal_type,
                "calories": prediction.get(
                    "estimated_calories"
                ),
                "protein_g": prediction.get(
                    "estimated_protein_g"
                ),
                "carbs_g": prediction.get(
                    "estimated_carbs_g"
                ),
                "fat_g": prediction.get(
                    "estimated_fat_g"
                ),
                "portions_remaining": None,
                "expires_at": None,
                "priority": "normal",
                "waste_risk": None,
                "reason": "routine_prediction",
            }

        return {
            "meal_type": meal_type,
            "available_kcal": available_kcal,
            "recommended": recommendation,
            "prediction": prediction,
            "inventory_candidates": [
                self._public_candidate(item)
                for item in candidates
            ],
            "inventory_warnings": warnings,
        }

    @staticmethod
    def _public_candidate(item: dict) -> dict:
        result = dict(item)
        result.pop("_sort_key", None)
        return result

    @staticmethod
    def _number(value: Any) -> float:
        try:
            return max(0.0, float(value or 0))
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _parse_date(value: Any) -> date | None:
        if not value:
            return None
        try:
            return date.fromisoformat(str(value))
        except ValueError:
            return None

    @staticmethod
    def _priority(
        day_date: date,
        expires_at: date | None,
    ) -> str:
        if expires_at is None:
            return "normal"

        days_left = (expires_at - day_date).days

        if days_left <= 1:
            return "high"
        if days_left <= 3:
            return "medium"
        return "normal"

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

    @staticmethod
    def _sort_key(
        day_date: date,
        expires_at: date | None,
    ) -> tuple[int, int]:
        if expires_at is None:
            return (1, 999999)

        return (
            0,
            (expires_at - day_date).days,
        )
