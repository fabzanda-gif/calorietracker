from __future__ import annotations

from typing import Any

from backend.repositories.base import RepositoryError
from backend.repositories.ingredients import (
    IngredientsRepository,
)
from backend.repositories.meal_ingredients import (
    MealIngredientsRepository,
)
from backend.repositories.meals import MealsRepository
from backend.services.recipe_nutrition import (
    RecipeNutritionService,
)


class StructuredMealError(ValueError):
    pass


class StructuredMealService:
    """
    Create one meal event with zero or more structured components.

    Nutrition is derived from the component quantities.
    The meal row stores totals; meal_ingredients stores snapshots.
    """

    def __init__(
        self,
        *,
        meals_repo: MealsRepository,
        ingredients_repo: IngredientsRepository,
        meal_ingredients_repo: MealIngredientsRepository,
    ):
        self.meals_repo = meals_repo
        self.ingredients_repo = ingredients_repo
        self.meal_ingredients_repo = meal_ingredients_repo

    def create(
        self,
        *,
        user_id: str,
        meal_payload: dict[str, Any],
        structured_ingredients: list[dict[str, Any]],
    ) -> dict:
        if not structured_ingredients:
            raise StructuredMealError(
                "At least one structured ingredient is required"
            )

        components = []

        for component in structured_ingredients:
            ingredient_id = component.get(
                "ingredient_id"
            )

            ingredient = (
                self.ingredients_repo.get_by_id(
                    ingredient_id,
                    user_id,
                )
            )

            if ingredient is None:
                raise StructuredMealError(
                    f"Ingredient not found: {ingredient_id}"
                )

            components.append(
                {
                    "ingredient": ingredient,
                    "quantity": component.get(
                        "quantity"
                    ),
                    "unit": (
                        component.get("unit")
                        or "g"
                    ),
                    "quantity_g": component.get(
                        "quantity_g"
                    ),
                }
            )

        nutrition = (
            RecipeNutritionService().calculate(
                components
            )
        )

        payload = dict(meal_payload)
        payload["user_id"] = user_id
        payload.update(nutrition["totals"])

        meal = self.meals_repo.create(
            payload
        )

        if (
            meal is None
            or meal.get("id") is None
        ):
            raise StructuredMealError(
                "Meal was created without an id"
            )

        meal_id = meal["id"]
        saved_components = []

        try:
            for component, calculated in zip(
                components,
                nutrition["ingredients"],
            ):
                ingredient = component[
                    "ingredient"
                ]

                saved = (
                    self.meal_ingredients_repo.create(
                        {
                            "meal_id": meal_id,
                            "ingredient_id": ingredient[
                                "id"
                            ],
                            "name_snapshot": ingredient[
                                "name"
                            ],
                            "quantity": component[
                                "quantity"
                            ],
                            "unit": component[
                                "unit"
                            ],
                            "quantity_g": component[
                                "quantity_g"
                            ],
                            "calories": calculated[
                                "calories"
                            ],
                            "protein": calculated[
                                "protein"
                            ],
                            "carbs": calculated[
                                "carbs"
                            ],
                            "fat": calculated[
                                "fat"
                            ],
                        }
                    )
                )

                if saved is not None:
                    saved_components.append(
                        saved
                    )

        except Exception:
            # Best-effort rollback.
            try:
                self.meals_repo.delete(
                    meal_id,
                    user_id,
                )
            except RepositoryError:
                pass

            raise

        return {
            "meal": meal,
            "meal_ingredients": saved_components,
            "nutrition": nutrition,
        }
