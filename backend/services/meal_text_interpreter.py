from __future__ import annotations

from typing import Any


class MealInterpretationError(ValueError):
    pass


class MealTextInterpreter:
    """
    Validate and normalize structured output produced by a meal
    interpretation layer.

    This class does not call an AI provider.
    """

    def normalize(
        self,
        interpretation: dict[str, Any],
    ) -> dict[str, Any]:
        meal_type = str(
            interpretation.get("meal_type") or ""
        ).strip()

        raw_items = interpretation.get("items") or []

        if not isinstance(raw_items, list):
            raise MealInterpretationError(
                "items must be a list"
            )

        items = [
            self._normalize_item(item)
            for item in raw_items
        ]

        return {
            "meal_type": meal_type,
            "items": items,
        }

    def _normalize_item(
        self,
        item: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(item, dict):
            raise MealInterpretationError(
                "meal item must be an object"
            )

        name = str(item.get("name") or "").strip()

        if not name:
            raise MealInterpretationError(
                "meal item requires a name"
            )

        normalized = {
            "name": name,
            "quantity": self._number(
                item.get("quantity"),
                default=1.0,
            ),
            "unit": str(
                item.get("unit") or "porzione"
            ).strip(),
            "calories": self._nutrition_number(
                item.get("calories")
            ),
            "protein": self._nutrition_number(
                item.get("protein")
            ),
            "carbs": self._nutrition_number(
                item.get("carbs")
            ),
            "fat": self._nutrition_number(
                item.get("fat")
            ),
            "estimated": bool(
                item.get("estimated", False)
            ),
        }

        uncertainty = item.get("uncertainty")

        if uncertainty:
            normalized["uncertainty"] = str(
                uncertainty
            ).strip()

        return normalized

    @staticmethod
    def _number(
        value: Any,
        *,
        default: float,
    ) -> float:
        if value is None:
            return default

        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise MealInterpretationError(
                "invalid numeric value"
            ) from exc

        if number < 0:
            raise MealInterpretationError(
                "numeric values cannot be negative"
            )

        return number

    def _nutrition_number(
        self,
        value: Any,
    ) -> float:
        return self._number(
            value,
            default=0.0,
        )
