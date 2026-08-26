from __future__ import annotations

from typing import Any


class ConversationalMealLoggingService:
    """
    Build a safe, reviewable preview from structured meal items.

    This service deliberately does not:
    - call an AI provider
    - write to the database
    - confirm or create meals

    Interpretation happens upstream. Persistence happens only after
    explicit user confirmation.
    """

    def build_preview(
        self,
        *,
        text: str,
        meal_type: str,
        interpreted_items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        items = [
            dict(item)
            for item in interpreted_items
        ]

        if not items:
            return {
                "status": "needs_input",
                "meal_type": meal_type,
                "original_text": text,
                "items": [],
                "totals": {
                    "calories": 0,
                    "protein": 0,
                    "carbs": 0,
                    "fat": 0,
                },
                "needs_review": True,
                "requires_confirmation": False,
            }

        totals = {
            nutrient: round(
                sum(
                    self._number(item.get(nutrient))
                    for item in items
                ),
                2,
            )
            for nutrient in (
                "calories",
                "protein",
                "carbs",
                "fat",
            )
        }

        needs_review = any(
            bool(item.get("uncertainty"))
            for item in items
        )

        return {
            "status": "preview",
            "meal_type": meal_type,
            "original_text": text,
            "items": items,
            "totals": totals,
            "needs_review": needs_review,
            "requires_confirmation": True,
        }

    @staticmethod
    def _number(value: Any) -> float:
        if value is None:
            return 0.0

        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
