from __future__ import annotations

from typing import Any

from backend.repositories.ingredients import IngredientsRepository
from backend.repositories.meal_ingredients import MealIngredientsRepository
from backend.repositories.meals import MealsRepository
from backend.services.ingredient_names import normalize_ingredient_name
from backend.services.structured_meal import StructuredMealService


class ConversationalMealConfirmationService:
    """Persist a reviewed conversational preview as a structured meal."""

    def __init__(
        self,
        *,
        meals_repo: MealsRepository,
        ingredients_repo: IngredientsRepository,
        meal_ingredients_repo: MealIngredientsRepository,
    ) -> None:
        self.meals_repo = meals_repo
        self.ingredients_repo = ingredients_repo
        self.meal_ingredients_repo = meal_ingredients_repo

    def confirm(
        self,
        *,
        user_id: str,
        meal_payload: dict[str, Any],
        items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        components = []

        for item in items:
            name = str(item["name"]).strip()
            quantity_g = float(item["quantity_g"])
            normalized_name = normalize_ingredient_name(name)

            ingredient = self.ingredients_repo.get_by_normalized_name(
                normalized_name,
                user_id,
            )

            if ingredient is None:
                factor = 100.0 / quantity_g
                ingredient = self.ingredients_repo.create(
                    {
                        "user_id": user_id,
                        "name": name,
                        "normalized_name": normalized_name,
                        "calories_per_100g": round(
                            float(item.get("calories") or 0) * factor,
                            2,
                        ),
                        "protein_per_100g": round(
                            float(item.get("protein") or 0) * factor,
                            2,
                        ),
                        "carbs_per_100g": round(
                            float(item.get("carbs") or 0) * factor,
                            2,
                        ),
                        "fat_per_100g": round(
                            float(item.get("fat") or 0) * factor,
                            2,
                        ),
                        "default_unit": "g",
                        "default_quantity": quantity_g,
                    }
                )

            if ingredient is None or ingredient.get("id") is None:
                raise ValueError(f"Unable to resolve ingredient: {name}")

            components.append(
                {
                    "ingredient_id": str(ingredient["id"]),
                    "quantity": quantity_g,
                    "unit": "g",
                    "quantity_g": quantity_g,
                }
            )

        return StructuredMealService(
            meals_repo=self.meals_repo,
            ingredients_repo=self.ingredients_repo,
            meal_ingredients_repo=self.meal_ingredients_repo,
        ).create(
            user_id=user_id,
            meal_payload=meal_payload,
            structured_ingredients=components,
        )
