from __future__ import annotations

from typing import Any


class RecipeNutritionError(ValueError):
    pass


class RecipeNutritionService:
    """
    Deterministically calculate recipe nutrition from structured ingredients.

    Ingredient nutrition is expressed per 100 g.
    Recipe quantities are converted through quantity_g.

    AI is never involved in nutritional arithmetic.
    """

    NUTRIENTS = (
        ("calories_per_100g", "calories"),
        ("protein_per_100g", "protein"),
        ("carbs_per_100g", "carbs"),
        ("fat_per_100g", "fat"),
    )

    def calculate(
        self,
        components: list[dict[str, Any]],
    ) -> dict:
        totals = {
            "calories": 0.0,
            "protein": 0.0,
            "carbs": 0.0,
            "fat": 0.0,
        }

        normalized = []

        for component in components:
            ingredient = component.get("ingredient") or {}
            quantity_g = self._positive_number(
                component.get("quantity_g"),
                field="quantity_g",
            )

            contribution = {}

            for source_field, target_field in self.NUTRIENTS:
                per_100g = self._non_negative_number(
                    ingredient.get(source_field)
                )

                value = per_100g * quantity_g / 100.0
                contribution[target_field] = round(value, 2)
                totals[target_field] += value

            normalized.append(
                {
                    "ingredient_id": ingredient.get("id"),
                    "name": ingredient.get("name"),
                    "quantity_g": quantity_g,
                    **contribution,
                }
            )

        return {
            "ingredients": normalized,
            "totals": {
                key: round(value, 2)
                for key, value in totals.items()
            },
        }

    @staticmethod
    def _positive_number(
        value: Any,
        *,
        field: str,
    ) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise RecipeNutritionError(
                f"{field} must be a positive number"
            )

        if number <= 0:
            raise RecipeNutritionError(
                f"{field} must be greater than zero"
            )

        return number

    @staticmethod
    def _non_negative_number(value: Any) -> float:
        try:
            number = float(value or 0)
        except (TypeError, ValueError):
            return 0.0

        return max(0.0, number)
