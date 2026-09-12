from __future__ import annotations

from datetime import date
from typing import Any

from backend.repositories.ingredients import IngredientsRepository
from backend.repositories.meal_ingredients import MealIngredientsRepository
from backend.repositories.meals import MealsRepository
from backend.repositories.pantry import PantryRepository


class PantryMealLoggingError(ValueError):
    pass


class PantryMealItemNotFoundError(PantryMealLoggingError):
    pass


class PantryMealUnavailableError(PantryMealLoggingError):
    pass


class PantryMealLoggingService:
    """
    One Home action logs a real meal and consumes the exact pantry row
    selected by the user.

    This keeps pantry provenance explicit instead of matching by name.
    """

    def __init__(
        self,
        *,
        pantry_repo: PantryRepository,
        ingredients_repo: IngredientsRepository,
        meals_repo: MealsRepository,
        meal_ingredients_repo: MealIngredientsRepository,
    ):
        self.pantry_repo = pantry_repo
        self.ingredients_repo = ingredients_repo
        self.meals_repo = meals_repo
        self.meal_ingredients_repo = meal_ingredients_repo

    @staticmethod
    def _number(value: Any) -> float:
        try:
            return max(0.0, float(value or 0))
        except (TypeError, ValueError):
            return 0.0

    def _available_grams(
        self,
        item: dict,
        fallback_grams_per_portion: float | None = None,
    ) -> float:
        quantity = self._number(item.get("quantity"))
        mode = str(item.get("quantity_mode") or "weight").lower()
        unit = str(item.get("unit") or "").strip().lower()

        if mode == "portion":
            grams_per_portion = self._number(
                item.get("grams_per_portion")
            )

            if grams_per_portion <= 0:
                grams_per_portion = self._number(
                    fallback_grams_per_portion
                )

            if grams_per_portion <= 0:
                raise PantryMealUnavailableError(
                    "Pantry portion has no gram weight"
                )

            return quantity * grams_per_portion

        if unit in {"g", "gr", "gram", "grams"}:
            return quantity

        if unit in {"kg", "kilogram", "kilograms"}:
            return quantity * 1000.0

        raise PantryMealUnavailableError(
            f"Unsupported pantry unit for food logging: {unit or 'unknown'}"
        )

    def _remaining_quantity(
        self,
        item: dict,
        consumed_grams: float,
        fallback_grams_per_portion: float | None = None,
    ) -> float:
        quantity = self._number(item.get("quantity"))
        mode = str(item.get("quantity_mode") or "weight").lower()
        unit = str(item.get("unit") or "").strip().lower()

        if mode == "portion":
            grams_per_portion = self._number(
                item.get("grams_per_portion")
            )

            if grams_per_portion <= 0:
                grams_per_portion = self._number(
                    fallback_grams_per_portion
                )

            if grams_per_portion <= 0:
                raise PantryMealUnavailableError(
                    "Pantry portion has no gram weight"
                )

            return quantity - (
                consumed_grams / grams_per_portion
            )

        if unit in {"g", "gr", "gram", "grams"}:
            return quantity - consumed_grams

        if unit in {"kg", "kilogram", "kilograms"}:
            return quantity - (consumed_grams / 1000.0)

        raise PantryMealUnavailableError(
            f"Unsupported pantry unit for food logging: {unit or 'unknown'}"
        )

    def log(
        self,
        *,
        user_id: str,
        pantry_item_id: Any,
        meal_date: date,
        meal_type: str,
        quantity_g: float,
    ) -> dict:
        if quantity_g <= 0:
            raise PantryMealLoggingError(
                "quantity_g must be greater than zero"
            )

        pantry_item = self.pantry_repo.get_by_id(
            pantry_item_id,
            user_id,
        )

        if pantry_item is None:
            raise PantryMealItemNotFoundError(
                "Pantry item not found"
            )

        ingredient_id = pantry_item.get("ingredient_id")

        ingredient = self.ingredients_repo.get_by_id(
            ingredient_id,
            user_id,
        )

        if ingredient is None:
            raise PantryMealItemNotFoundError(
                "Ingredient not found"
            )

        available_grams = self._available_grams(
            pantry_item,
            fallback_grams_per_portion=quantity_g,
        )

        if quantity_g > available_grams + 0.001:
            raise PantryMealUnavailableError(
                "Not enough pantry quantity available"
            )

        factor = quantity_g / 100.0

        calories = (
            self._number(
                ingredient.get("calories_per_100g")
            )
            * factor
        )
        protein = (
            self._number(
                ingredient.get("protein_per_100g")
            )
            * factor
        )
        carbs = (
            self._number(
                ingredient.get("carbs_per_100g")
            )
            * factor
        )
        fat = (
            self._number(
                ingredient.get("fat_per_100g")
            )
            * factor
        )

        payload = {
            "user_id": user_id,
            "date": str(meal_date),
            "meal_type": meal_type,
            "name": ingredient.get("name") or "Alimento",
            "base_name": ingredient.get("name") or "Alimento",
            "quantity": quantity_g,
            "is_per_100g": True,
            "base_calories": self._number(
                ingredient.get("calories_per_100g")
            ),
            "base_protein": self._number(
                ingredient.get("protein_per_100g")
            ),
            "base_carbs": self._number(
                ingredient.get("carbs_per_100g")
            ),
            "base_fat": self._number(
                ingredient.get("fat_per_100g")
            ),
            "calories": round(calories),
            "protein": round(protein),
            "carbs": round(carbs),
            "fat": round(fat),
            "category": "pantry",
            "notes": (
                f"Logged from pantry item: {pantry_item_id}"
            ),
        }

        compatible_creator = getattr(
            self.meals_repo,
            "create_compatible",
            None,
        )

        if callable(compatible_creator):
            meal_response = compatible_creator(
                payload
            )

            if isinstance(meal_response, dict):
                meal = meal_response
            else:
                meal_rows = (
                    getattr(
                        meal_response,
                        "data",
                        None,
                    )
                    or []
                )

                meal = (
                    meal_rows[0]
                    if meal_rows
                    else None
                )
        else:
            # Compatibility with repository implementations
            # that already normalize create() to a single row.
            meal = self.meals_repo.create(payload)

        if (
            not isinstance(meal, dict)
            or meal.get("id") is None
        ):
            raise PantryMealLoggingError(
                "Meal was created without an id"
            )

        meal_id = meal["id"]

        try:
            meal_ingredient = (
                self.meal_ingredients_repo.create(
                    {
                        "meal_id": meal_id,
                        "ingredient_id": ingredient["id"],
                        "name_snapshot": ingredient.get("name"),
                        "quantity": quantity_g,
                        "unit": "g",
                        "quantity_g": quantity_g,
                        "calories": calories,
                        "protein": protein,
                        "carbs": carbs,
                        "fat": fat,
                    }
                )
            )

            if meal_ingredient is None:
                raise PantryMealLoggingError(
                    "Meal ingredient link was not created"
                )

            remaining = self._remaining_quantity(
                pantry_item,
                quantity_g,
                fallback_grams_per_portion=quantity_g,
            )

            if remaining <= 0.001:
                self.pantry_repo.delete(
                    pantry_item_id,
                    user_id,
                )
                inventory = None
            else:
                inventory = self.pantry_repo.update(
                    pantry_item_id,
                    user_id,
                    {
                        "quantity": remaining,
                    },
                )

        except Exception:
            # Compensazione applicativa: rimuove ogni dato
            # parziale creato prima del fallimento.
            delete_components = getattr(
                self.meal_ingredients_repo,
                "delete_for_meal",
                None,
            )

            if callable(delete_components):
                try:
                    delete_components(meal_id)
                except Exception:
                    pass

            try:
                self.meals_repo.delete(
                    meal_id,
                    user_id,
                )
            except Exception:
                pass

            raise

        return {
            "logged": True,
            "meal": meal,
            "inventory": inventory,
            "consumed_grams": quantity_g,
        }
