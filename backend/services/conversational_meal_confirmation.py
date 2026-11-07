from __future__ import annotations

from typing import Any

from backend.repositories.ingredients import IngredientsRepository
from backend.repositories.meal_ingredients import MealIngredientsRepository
from backend.repositories.meals import MealsRepository
from backend.repositories.pantry import PantryRepository
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
        pantry_repo: PantryRepository | None = None,
    ) -> None:
        self.meals_repo = meals_repo
        self.ingredients_repo = ingredients_repo
        self.meal_ingredients_repo = meal_ingredients_repo
        self.pantry_repo = pantry_repo

    @staticmethod
    def _pantry_available_grams(
        item: dict[str, Any],
    ) -> float:
        quantity = max(
            0.0,
            float(item.get("quantity") or 0),
        )

        mode = str(
            item.get("quantity_mode")
            or "weight"
        )

        if mode == "portion":
            grams_per_portion = max(
                0.0,
                float(
                    item.get("grams_per_portion")
                    or 0
                ),
            )
            return quantity * grams_per_portion

        unit = str(
            item.get("unit")
            or "g"
        ).strip().lower()

        if unit in {"kg", "kilogram", "kilograms"}:
            return quantity * 1000.0

        # Pantry V1 stores weight-mode ingredients
        # primarily in grams. Unknown units are not
        # consumed automatically because conversion
        # would be unsafe.
        if unit in {"g", "gr", "gram", "grams"}:
            return quantity

        return 0.0


    @staticmethod
    def _pantry_quantity_from_grams(
        item: dict[str, Any],
        grams: float,
    ) -> float | None:
        grams = max(0.0, grams)

        mode = str(
            item.get("quantity_mode")
            or "weight"
        )

        if mode == "portion":
            grams_per_portion = max(
                0.0,
                float(
                    item.get("grams_per_portion")
                    or 0
                ),
            )

            if grams_per_portion <= 0:
                return None

            return grams / grams_per_portion

        unit = str(
            item.get("unit")
            or "g"
        ).strip().lower()

        if unit in {"kg", "kilogram", "kilograms"}:
            return grams / 1000.0

        if unit in {"g", "gr", "gram", "grams"}:
            return grams

        return None


    def _consume_pantry(
        self,
        *,
        user_id: str,
        components: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if self.pantry_repo is None:
            return []

        pantry_items = self.pantry_repo.list_for_user(
            user_id
        )

        consumed: list[dict[str, Any]] = []

        for component in components:
            ingredient_id = str(
                component["ingredient_id"]
            )
            remaining_grams = max(
                0.0,
                float(
                    component.get("quantity_g")
                    or 0
                ),
            )

            if remaining_grams <= 0:
                continue

            matches = [
                item
                for item in pantry_items
                if str(
                    item.get("ingredient_id")
                ) == ingredient_id
            ]

            for pantry_item in matches:
                if remaining_grams <= 0:
                    break

                available_grams = (
                    self._pantry_available_grams(
                        pantry_item
                    )
                )

                if available_grams <= 0:
                    continue

                used_grams = min(
                    remaining_grams,
                    available_grams,
                )

                grams_left = max(
                    0.0,
                    available_grams - used_grams,
                )

                item_id = pantry_item.get("id")

                if item_id is None:
                    continue

                if grams_left <= 0.001:
                    self.pantry_repo.delete(
                        item_id,
                        user_id,
                    )
                else:
                    new_quantity = (
                        self._pantry_quantity_from_grams(
                            pantry_item,
                            grams_left,
                        )
                    )

                    if (
                        new_quantity is None
                        or new_quantity <= 0
                    ):
                        continue

                    self.pantry_repo.update(
                        item_id,
                        user_id,
                        {
                            "quantity": round(
                                new_quantity,
                                4,
                            )
                        },
                    )

                    pantry_item["quantity"] = (
                        new_quantity
                    )

                consumed.append(
                    {
                        "pantry_item_id": str(
                            item_id
                        ),
                        "ingredient_id": ingredient_id,
                        "consumed_g": round(
                            used_grams,
                            2,
                        ),
                    }
                )

                remaining_grams -= used_grams

        return consumed


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

        result = StructuredMealService(
            meals_repo=self.meals_repo,
            ingredients_repo=self.ingredients_repo,
            meal_ingredients_repo=self.meal_ingredients_repo,
        ).create(
            user_id=user_id,
            meal_payload=meal_payload,
            structured_ingredients=components,
        )

        pantry_consumption = self._consume_pantry(
            user_id=user_id,
            components=components,
        )

        return {
            **result,
            "pantry_consumption": pantry_consumption,
        }
